from __future__ import annotations

import logging
import asyncio
import hashlib
import json
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException, Query, Response, Request
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app
from pydantic import BaseModel, Field

from .admission import AdmissionController, AdmissionRejected
from .config import get_settings
from .control_cache import ControlCache, ControlPlaneUnavailable
from .metrics import ADMISSION_REJECTIONS, CONTROL_LOOKUPS, UPSTREAM_TTFT, observe_record_failure, observe_route, observe_upstream_error
from .picking import POLICIES, normalize
from .ttft import TTFTWindow

logger = logging.getLogger("router")

@asynccontextmanager
async def lifespan(application):
    async with httpx.AsyncClient(timeout=None) as client, httpx.AsyncClient(timeout=None) as audit_client:
        application.state.http_client = client
        application.state.audit_client = audit_client
        try:
            yield
        finally:
            pending = list(application.state.audit_tasks)
            if pending:
                _, unfinished = await asyncio.wait(pending, timeout=get_settings().audit_timeout_seconds + .1)
                for task in unfinished:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
            del application.state.http_client
            del application.state.audit_client


app = FastAPI(title="ai-infra-platform-router", version="0.1.0", lifespan=lifespan)
app.mount("/metrics", make_asgi_app())
app.state.admission = AdmissionController()
app.state.ttft = TTFTWindow()
app.state.audit_tasks = set()
app.state.control_cache = ControlCache()


@asynccontextmanager
async def _http_client(name):
    existing = getattr(app.state, name, None)
    if existing is not None:
        yield existing
    else:
        async with httpx.AsyncClient(timeout=None) as client:
            yield client


async def _control_call(awaitable, seconds):
    try:
        async with asyncio.timeout(seconds):
            return await awaitable
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail={"code": "control_plane_timeout", "message": "控制面调用超时"}) from exc


async def _audit(client, base, headers, payload, seconds):
    try:
        async with asyncio.timeout(seconds):
            request_id = await _record(client, base, headers, payload)
    except Exception as exc:
        logger.warning("写入请求日志失败: %s", type(exc).__name__)
        request_id = None
    if request_id is None:
        observe_record_failure()
    return request_id


async def _finish_audit(task):
    cancellation = None
    while True:
        try:
            return await asyncio.shield(task), cancellation
        except asyncio.CancelledError as exc:
            if task.cancelled():
                raise
            cancellation = exc


def _control_unavailable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.RequestError):
        return True
    if isinstance(exc, HTTPException) and isinstance(exc.detail, dict):
        code = exc.detail.get("code")
        status = (exc.detail.get("detail") or {}).get("status", 0)
        return code == "control_plane_timeout" or code == "control_plane_error" and status >= 500
    return False


def _key_digest(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()


async def _cached_control(kind: str, key: tuple, loader, settings) -> tuple[Any, str]:
    cache = app.state.control_cache

    async def load():
        try:
            return await _control_call(loader(), settings.control_timeout_seconds)
        except HTTPException as exc:
            if exc.status_code == 401:
                cache.evict(lambda cached: cached[1] == key[0])
            if _control_unavailable(exc):
                raise ControlPlaneUnavailable(exc) from exc
            raise
        except httpx.RequestError as exc:
            raise ControlPlaneUnavailable(exc) from exc

    try:
        value, source = await cache.get(
            (kind, *key), load, settings.control_cache_seconds, settings.control_stale_seconds,
        )
    except ControlPlaneUnavailable as exc:
        CONTROL_LOOKUPS.labels(kind=kind, source="unavailable").inc()
        raise exc.original
    CONTROL_LOOKUPS.labels(kind=kind, source=source).inc()
    return value, source


@app.exception_handler(httpx.RequestError)
async def control_plane_unavailable(request: Request, exc: httpx.RequestError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": {"code": "control_plane_unavailable", "message": "控制面不可达"}})



class RouteIn(BaseModel):
    model_name: str = Field(min_length=1, max_length=200)
    prompt: str = Field(min_length=1)
    policy: str | None = None
    max_tokens: int | None = Field(default=None, gt=0, le=2048)
    engine_models: dict[str, str] = Field(default_factory=dict)


class BackendOut(BaseModel):
    id: int
    name: str
    engine: str
    url: str


class RouteOut(BaseModel):
    request_id: str | None
    recorded: bool
    backend: BackendOut
    decision: dict[str, Any]
    output: str
    usage: dict[str, Any]
    timings: dict[str, Any]


async def _fetch_candidates(
    client: httpx.AsyncClient, base: str, headers: dict[str, str], model_name: str, policy: str
) -> list[dict[str, Any]]:
    response = await client.get(
        f"{base}/api/v1/routing/candidates",
        params={"model_name": model_name, "policy": policy},
        headers=headers,
    )
    _raise_for_control_plane(response)
    return list(response.json().get("ranked") or [])


async def _fetch_backend(
    client: httpx.AsyncClient, base: str, headers: dict[str, str], backend_id: int
) -> dict[str, Any]:
    response = await client.get(
        f"{base}/api/v1/backends/{backend_id}", params={"with_models": False}, headers=headers
    )
    _raise_for_control_plane(response)
    return dict(response.json())


def _raise_for_control_plane(response: httpx.Response) -> None:
    if response.status_code == 401:
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthorized", "message": "控制层拒绝了这把 key", "detail": {}},
        )
    if response.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "control_plane_error",
                "message": "控制层返回错误",
                "detail": {"status": response.status_code, "body": response.text[:300]},
            },
        )


async def _call_backend(
    client: httpx.AsyncClient,
    engine: str,
    url: str,
    engine_model: str,
    prompt: str,
    max_tokens: int,
    metric_model: str | None = None,
) -> tuple[str, int | None, int | None]:
    base = normalize(url)
    if engine == "ollama":
        response = await client.post(
            f"{base}/api/generate",
            json={
                "model": engine_model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": max_tokens},
            },
        )
        response.raise_for_status()
        data = response.json()
        return (
            str(data.get("response") or ""),
            data.get("prompt_eval_count"),
            data.get("eval_count"),
        )
    if get_settings().stream_openai:
        clock = time.perf_counter()
        first = None
        content = []
        usage = {}
        done = False
        async with client.stream("POST", f"{base}/v1/chat/completions", json={
            "model": engine_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens, "temperature": 0,
            "stream": True, "stream_options": {"include_usage": True},
        }) as response:
            if response.is_error:
                await response.aread()
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                value = line[5:].strip()
                if value == "[DONE]":
                    done = True
                    break
                event = json.loads(value)
                if event.get("error"):
                    raise ValueError("upstream stream error")
                for choice in event.get("choices") or []:
                    text = (choice.get("delta") or {}).get("content")
                    if text:
                        if first is None:
                            first = (time.perf_counter() - clock) * 1000
                        content.append(text)
                usage = event.get("usage") or usage
        if not done or first is None:
            raise ValueError("incomplete or empty upstream stream")
        app.state.ttft.observe(metric_model or engine_model, first)
        UPSTREAM_TTFT.labels(model=metric_model or engine_model).observe(first / 1000)
        return "".join(content), usage.get("prompt_tokens"), usage.get("completion_tokens")
    response = await client.post(
        f"{base}/v1/chat/completions",
        json={
            "model": engine_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0,
        },
    )
    response.raise_for_status()
    data = response.json()
    choice = (data.get("choices") or [{}])[0]
    usage = data.get("usage") or {}
    return (
        str((choice.get("message") or {}).get("content") or ""),
        usage.get("prompt_tokens"),
        usage.get("completion_tokens"),
    )


async def _record(
    client: httpx.AsyncClient, base: str, headers: dict[str, str], payload: dict[str, Any]
) -> str | None:
    response = await client.post(f"{base}/api/v1/requests", json=payload, headers=headers)
    if response.status_code >= 400:
        logger.warning("写入请求日志失败: HTTP %s %s", response.status_code, response.text[:200])
        return None
    return str(response.json().get("request_id") or "")


@app.get("/healthz", summary="存活探针")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ttft_p95")
async def ttft_p95(response: Response, model: str | None = Query(default=None, min_length=1, max_length=200)):
    settings = get_settings()
    model = model or settings.ttft_model
    if not model:
        raise HTTPException(status_code=503, detail="TTFT_MODEL is not configured and no model was requested")
    result = app.state.ttft.snapshot(model, settings.ttft_window_seconds)
    response.headers["Cache-Control"] = "no-store"
    if not result["sample_count"]:
        response.status_code = 503
    return result


@app.get("/readyz", summary="就绪探针")
async def readyz(response: Response) -> dict[str, Any]:
    settings = get_settings()
    base = normalize(settings.control_plane_url)
    failed: list[str] = []
    try:
        async with _http_client("http_client") as client:
            probe = await _control_call(client.get(f"{base}/readyz"), settings.control_timeout_seconds)
            if probe.status_code != 200:
                failed.append("control_plane")
    except Exception as exc:
        logger.warning("控制层探活失败: %r", exc)
        failed.append("control_plane")
    if failed:
        response.status_code = 503
    return {
        "status": "ok" if not failed else "degraded",
        "control_plane": base,
        "failed": failed,
    }


@app.post("/v1/route", response_model=RouteOut, summary="按控制层的决策选一个真实后端并执行一次生成")
async def route(
    payload: RouteIn,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> RouteOut:
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthorized", "message": "缺少 X-API-Key 请求头", "detail": {}},
        )

    settings = get_settings()
    policy = payload.policy or settings.default_policy
    if policy not in POLICIES:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_policy",
                "message": "policy 取值非法",
                "detail": {"policy": policy, "allowed": sorted(POLICIES)},
            },
        )

    base = normalize(settings.control_plane_url)
    headers = {"X-API-Key": x_api_key}
    key_digest = _key_digest(x_api_key)
    control_sources = {}
    max_tokens = payload.max_tokens or settings.default_max_tokens
    started = datetime.now(timezone.utc)
    clock = time.perf_counter()

    backend = None
    output = ""
    prompt_tokens = completion_tokens = None
    error_code = None
    cancellation = None
    async with _http_client("http_client") as client, _http_client("audit_client") as audit_client:
        try:
            async with asyncio.timeout(settings.request_timeout_seconds - settings.audit_timeout_seconds):
                candidates, control_sources["candidates"] = await _cached_control(
                    "candidates", (key_digest, payload.model_name, policy),
                    lambda: _fetch_candidates(client, base, headers, payload.model_name, policy), settings,
                )
                with app.state.admission.reserve(
                    candidates, policy, settings.backend_max_inflight, settings.backend_inflight_limits,
                ) as reservation:
                    chosen = reservation.chosen
                    candidates = reservation.ranked
                    backend, control_sources["backend"] = await _cached_control(
                        "backend", (key_digest, int(chosen["backend_id"])),
                        lambda: _fetch_backend(client, base, headers, int(chosen["backend_id"])), settings,
                    )
                    engine_model = payload.engine_models.get(str(backend["name"])) or payload.model_name
                    try:
                        async with asyncio.timeout(settings.upstream_timeout_seconds):
                            output, prompt_tokens, completion_tokens = await _call_backend(
                                client, str(backend["engine"]), str(backend["url"]), engine_model,
                                payload.prompt, max_tokens, metric_model=payload.model_name,
                            )
                    except TimeoutError:
                        error_code = "backend_timeout"
                    except httpx.HTTPStatusError as exc:
                        error_code = f"backend_http_{exc.response.status_code}"
                    except httpx.RequestError:
                        error_code = "backend_unavailable"
                    except ValueError:
                        error_code = "backend_protocol_error"
                    except Exception as exc:
                        error_code = "backend_error"
                        logger.warning("后端调用失败: %s", type(exc).__name__)
        except TimeoutError as exc:
            if backend is None:
                raise HTTPException(status_code=504, detail={"code": "request_timeout", "message": "请求执行超时"}) from exc
            error_code = "request_timeout"
        except asyncio.CancelledError as exc:
            if backend is None:
                raise
            error_code = "request_cancelled"
            cancellation = exc
        except AdmissionRejected as exc:
            ADMISSION_REJECTIONS.labels(policy=policy, reason=exc.code).inc()
            saturated = exc.code == "backend_capacity_exhausted"
            raise HTTPException(
                status_code=429 if saturated else 503,
                headers={"Retry-After": "1"} if saturated else None,
                detail={
                    "code": exc.code,
                    "message": "可用后端已满载，请稍后重试" if saturated else "没有可用后端",
                    "detail": {"model_name": payload.model_name, "scope": "router_process", "candidates": exc.ranked},
                },
            ) from exc

        status = "success" if error_code is None else "error"
        total_ms = round((time.perf_counter() - clock) * 1000, 2)
        observe_route(str(backend["name"]), str(backend["engine"]), policy,
                      status, total_ms / 1000, len(candidates), payload.model_name)
        if error_code is not None:
            observe_upstream_error(error_code)
        decision = {
            "policy": policy,
            "candidate_ids": [int(item["backend_id"]) for item in candidates],
            "chosen_id": int(chosen["backend_id"]),
            "score_snapshot": {
                "ranked": candidates,
                "admission": {
                    "scope": "router_process",
                    "selection": "least_inflight_random_tie" if policy == "least_inflight" else policy,
                    "selected_inflight_before": chosen["inflight"],
                    "selected_limit": chosen["max_inflight"],
                },
            },
            "fallback_reason": "control_plane_stale_snapshot" if "stale" in control_sources.values() else None,
            "control_sources": control_sources,
        }
        audit_started = time.perf_counter()
        task = asyncio.create_task(_audit(audit_client, base, headers, {
            "model_name": payload.model_name,
            "status": status,
            "started_at": started.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "backend_id": int(chosen["backend_id"]),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_ms": total_ms,
            "error_code": error_code,
            "decision": decision,
        }, settings.audit_timeout_seconds))
        app.state.audit_tasks.add(task)
        task.add_done_callback(app.state.audit_tasks.discard)
        request_id, audit_cancellation = await _finish_audit(task)
        cancellation = cancellation or audit_cancellation
        recorded = request_id is not None
        audit_ms = round((time.perf_counter() - audit_started) * 1000, 2)
        if cancellation is not None:
            raise cancellation

    if error_code is not None:
        raise HTTPException(
            status_code=504 if error_code in {"backend_timeout", "request_timeout"} else 502,
            detail={
                "code": error_code,
                "message": "后端生成失败",
                "detail": {"backend": backend["name"], "request_id": request_id, "recorded": recorded},
            },
        )

    return RouteOut(
        request_id=request_id,
        recorded=recorded,
        backend=BackendOut(
            id=int(backend["id"]),
            name=str(backend["name"]),
            engine=str(backend["engine"]),
            url=str(backend["url"]),
        ),
        decision=decision,
        output=output,
        usage={"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
        timings={"total_ms": total_ms, "audit_ms": audit_ms, "response_ms": round((time.perf_counter() - clock) * 1000, 2), "engine_model": engine_model},
    )
