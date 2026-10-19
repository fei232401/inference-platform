from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
import pytest

from src.api.deps import SessionDep


class Database:
    def __init__(self, fail=False):
        self.committed = False
        self.fail = fail

    @asynccontextmanager
    async def transaction(self):
        yield object()
        await asyncio.sleep(0)
        if self.fail:
            raise RuntimeError("commit failed")
        self.committed = True


@pytest.mark.asyncio
@pytest.mark.parametrize("fail", [False, True])
async def test_commit_precedes_successful_http_response(fail):
    app = FastAPI()
    database = Database(fail)
    app.state.database = database

    @app.get("/write")
    async def write(session: SessionDep):
        return {"saved": True}

    responses = []

    async def send(message):
        if message["type"] == "http.response.start":
            responses.append((message["status"], database.committed))

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    scope = {"type": "http", "method": "GET", "path": "/write", "root_path": "", "query_string": b"",
             "headers": [], "http_version": "1.1", "scheme": "http", "server": ("test", 80), "client": ("test", 1)}
    if fail:
        with pytest.raises(RuntimeError, match="commit failed"):
            await app(scope, receive, send)
        assert responses == [(500, False)]
    else:
        await app(scope, receive, send)
        assert responses == [(200, True)]
