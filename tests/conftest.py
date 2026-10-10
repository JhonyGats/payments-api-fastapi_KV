"""Общие фикстуры тестов.

Каждый тест работает со своей временной базой SQLite, поэтому тесты
не зависят друг от друга и не трогают рабочую базу приложения.
"""
import os
import tempfile
import time
from pathlib import Path

import pytest

# Строку подключения нужно задать до импорта приложения: движок создаётся
# на уровне модуля database.py.
_tmp_db = Path(tempfile.gettempdir()) / "kvitto_test.sqlite3"
if _tmp_db.exists():
    _tmp_db.unlink()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_tmp_db.as_posix()}"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    """Клиент API. TestClient построен на httpx и поднимает приложение целиком."""
    with TestClient(app) as test_client:
        yield test_client

    # После закрытия приложения освобождаем файл базы: на Windows он занят,
    # пока живо соединение движка.
    from app.database import engine

    try:
        import asyncio

        asyncio.run(engine.dispose())
    except Exception:  # pragma: no cover - уборка не должна ломать прогон
        pass

    for _ in range(10):
        try:
            if _tmp_db.exists():
                _tmp_db.unlink()
            break
        except PermissionError:
            time.sleep(0.2)


def create_payment(client, **overrides):
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
    return client.post("/payments", json=payload, headers=headers)
