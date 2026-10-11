"""Общие фикстуры тестов.

Тесты ходят в приложение асинхронным клиентом httpx через ASGITransport:
запрос идёт прямо в ASGI-приложение, сервер на порту не поднимается.
База своя, временная, рабочая база приложения не затрагивается.
"""
import os
import tempfile
import time
from pathlib import Path

import httpx
import pytest

# Строку подключения нужно задать до импорта приложения: движок создаётся
# на уровне модуля database.py.
_tmp_db = Path(tempfile.gettempdir()) / "kvitto_test.sqlite3"
if _tmp_db.exists():
    _tmp_db.unlink()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_tmp_db.as_posix()}"

from app.database import SessionLocal, create_tables, engine  # noqa: E402
from app.main import TARIFFS, app  # noqa: E402
from app.models import Tariff  # noqa: E402


@pytest.fixture(scope="session")
def anyio_backend():
    """Тесты идут только на asyncio, trio в проекте не используется."""
    return "asyncio"


async def _prepare_database():
    """Создаёт таблицы и наполняет справочник тарифов.

    При ASGITransport событие lifespan приложения не выполняется, поэтому
    подготовку базы делаем теми же вызовами, что и приложение при старте.
    """
    await create_tables()
    async with SessionLocal() as session:
        for item in TARIFFS:
            if await session.get(Tariff, item["id"]) is None:
                session.add(Tariff(**item))
        await session.commit()


@pytest.fixture
async def client():
    """Асинхронный клиент httpx, направленный прямо в ASGI-приложение."""
    await _prepare_database()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
    # Закрываем соединения: на Windows файл базы занят, пока живо соединение движка.
    await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def _cleanup_database():
    """Убирает временный файл базы после прогона тестов."""
    yield
    for _ in range(10):
        try:
            if _tmp_db.exists():
                _tmp_db.unlink()
            break
        except PermissionError:
            time.sleep(0.2)


async def create_payment(client, **overrides):
    """Вспомогательная функция: создаёт платёж с разумными значениями по умолчанию."""
    payload = {
        "tariff_id": "standard",
        "email": "student@example.com",
        "method": "card",
    }
    payload.update(overrides)
    headers = {}
    if "idempotency_key" in payload:
        headers["Idempotency-Key"] = payload.pop("idempotency_key")
    return await client.post("/payments", json=payload, headers=headers)
