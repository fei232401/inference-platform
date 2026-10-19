import logging

from fastapi import APIRouter, Response, status

from ...repository import SchemaRepository
from ..deps import DatabaseDep, SettingsDep
from ..schemas import PoolStatusOut, ReadyOut

logger = logging.getLogger("app.health")

router = APIRouter(tags=["health"])


@router.get("/healthz", summary="存活探针")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz", response_model=ReadyOut, summary="就绪探针")
async def readyz(response: Response, database: DatabaseDep, settings: SettingsDep) -> ReadyOut:
    failed: list[str] = []
    schema_version: int | None = None
    pool: PoolStatusOut | None = None

    try:
        await database.ping()
        database_state = "up"
    except Exception as exc:
        logger.warning("database ping failed: %r", exc)
        database_state = "down"
        failed.append("database")

    if database_state == "up":
        try:
            async with database.transaction() as session:
                schema_version = await SchemaRepository(session).current_version()
        except Exception as exc:
            logger.warning("schema version lookup failed: %r", exc)
            failed.append("schema_migration")

        try:
            pool = PoolStatusOut(**await database.pool_status())
        except Exception as exc:
            logger.warning("pool status lookup failed: %r", exc)

    if database_state == "up" and schema_version != settings.expected_schema_version:
        failed.append("schema_version_mismatch")

    if failed:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadyOut(
        status="ok" if not failed else "degraded",
        database=database_state,
        schema_version=schema_version,
        pool=pool,
        failed=failed,
    )
