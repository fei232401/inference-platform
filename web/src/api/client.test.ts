import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { setApiKey } from "./apiKey";
import { buildQuery, request } from "./client";

function respond(status: number, body: unknown, statusText = "") {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    statusText,
    text: () => Promise.resolve(JSON.stringify(body)),
  } as unknown as Response);
}

let fetchMock: ReturnType<typeof vi.fn>;

function lastInit(): RequestInit {
  const call = fetchMock.mock.calls.at(-1);
  return (call?.[1] ?? {}) as RequestInit;
}

describe("request 的请求头", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    setApiKey("");
    fetchMock = vi.fn(() => respond(200, { status: "ok" }));
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("没配密钥时不带 X-API-Key，也不伪造空头", async () => {
    await request("/healthz");
    expect(lastInit().headers).toBeUndefined();
  });

  it("配了密钥时带上 X-API-Key", async () => {
    setApiKey("aip_testkey");
    await request("/api/v1/backends");
    expect(lastInit().headers).toEqual({ "X-API-Key": "aip_testkey" });
  });

  it("有请求体时 Content-Type 与 X-API-Key 同时在", async () => {
    setApiKey("aip_testkey");
    await request("/api/v1/backends", { method: "POST", body: { name: "b" } });
    expect(lastInit().headers).toEqual({
      "Content-Type": "application/json",
      "X-API-Key": "aip_testkey",
    });
    expect(lastInit().body).toBe(JSON.stringify({ name: "b" }));
  });

  it("清除密钥后立刻不再带该头", async () => {
    setApiKey("aip_testkey");
    await request("/healthz");
    expect(lastInit().headers).toEqual({ "X-API-Key": "aip_testkey" });

    setApiKey("");
    await request("/healthz");
    expect(lastInit().headers).toBeUndefined();
  });
});

describe("request 的错误归一", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    setApiKey("");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("401 的原样保留后端错误体，便于 UI 直接显示", async () => {
    fetchMock = vi.fn(() =>
      respond(
        401,
        { code: "unauthorized", message: "缺少 X-API-Key 请求头", detail: {} },
        "Unauthorized",
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(request("/api/v1/backends")).rejects.toMatchObject({
      status: 401,
      code: "unauthorized",
      message: "缺少 X-API-Key 请求头",
    });
  });

  it("网络层失败归一成 status=0 的 network_error", async () => {
    fetchMock = vi.fn(() => Promise.reject(new TypeError("Failed to fetch")));
    vi.stubGlobal("fetch", fetchMock);

    await expect(request("/healthz")).rejects.toMatchObject({
      status: 0,
      code: "network_error",
    });
  });

  it("204 返回 undefined 而不是去解析空 body", async () => {
    fetchMock = vi.fn(() =>
      Promise.resolve({
        ok: true,
        status: 204,
        statusText: "No Content",
        text: () => Promise.resolve(""),
      } as unknown as Response),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(request("/api/v1/backends/1", { method: "DELETE" })).resolves.toBeUndefined();
  });
});

describe("request 的 URL 组装", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    setApiKey("");
    fetchMock = vi.fn(() => respond(200, {}));
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("路径与查询串拼在一起，空值不进 URL", async () => {
    await request("/api/v1/backends", {
      query: { limit: 20, offset: 0, engine: "", state: "ready", name_like: null },
    });
    expect(String(fetchMock.mock.calls.at(-1)?.[0])).toBe(
      "/api/v1/backends?limit=20&offset=0&state=ready",
    );
  });

  it("没有查询参数时 URL 干净", async () => {
    await request("/readyz");
    expect(String(fetchMock.mock.calls.at(-1)?.[0])).toBe("/readyz");
  });
});

describe("buildQuery", () => {
  it("丢掉 undefined / null / 空串，保留 0 与 false", () => {
    expect(
      buildQuery({
        limit: 10,
        offset: 0,
        failures_only: false,
        model_name: "",
        session_id: null,
        status_value: undefined,
      }),
    ).toBe("?limit=10&offset=0&failures_only=false");
  });

  it("全空时返回空串", () => {
    expect(buildQuery({})).toBe("");
    expect(buildQuery(undefined)).toBe("");
  });
});
