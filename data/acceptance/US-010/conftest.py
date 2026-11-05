"""Fixtures for the hidden US-010 acceptance tests.

Points the app at a throwaway SQLite file *before* importing it, then
recreates the schema and seeds user "1" for every test.
"""

import os

os.environ["APP_DATABASE_URL"] = "sqlite+aiosqlite:///./.desmet_acceptance.db"

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.database import Base, async_session, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User  # noqa: E402


@pytest.fixture
async def client():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with async_session() as session:
        session.add(
            User(
                id="1",
                email="ada@example.com",
                display_name="Ada",
                bio="Original bio",
                avatar_url="https://example.com/ada.png",
            )
        )
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
