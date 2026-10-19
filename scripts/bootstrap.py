import asyncio
import hashlib
import os
from pathlib import Path
import secrets

import asyncpg

ROOT = Path(__file__).resolve().parents[1]


async def main():
    dsn = os.environ["DATABASE_DSN"].replace("postgresql+asyncpg://", "postgresql://")
    pepper = os.environ["SECRET_PEPPER"]
    connection = await asyncpg.connect(dsn)
    try:
        async with connection.transaction():
            await connection.execute("SELECT pg_advisory_xact_lock(71620418)")
            if not await connection.fetchval("SELECT to_regclass('public.schema_migration')"):
                await connection.execute((ROOT / "db/migrations/001_init.sql").read_text())
            token_path = ROOT / ".state/admin-key"
            token_path.parent.mkdir(mode=0o700, exist_ok=True)
            token = token_path.read_text().strip() if token_path.exists() else "aip_" + secrets.token_urlsafe(32)
            digest = hashlib.sha256((pepper + token).encode()).hexdigest()
            await connection.execute(
                "INSERT INTO api_key(key_prefix,key_hash,name,scopes) VALUES($1,$2,'local-admin',ARRAY['admin','infer']) ON CONFLICT(key_hash) DO NOTHING",
                token[:8], digest,
            )
            token_path.touch(mode=0o600, exist_ok=True)
            token_path.write_text(token)
            token_path.chmod(0o600)
        print("Schema initialized; local admin key saved in .state/admin-key")
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
