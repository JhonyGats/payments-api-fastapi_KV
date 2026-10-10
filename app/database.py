"""Настройки подключения к базе и фабрика сессий.

Деньги в проекте хранятся только целым числом в копейках, поэтому в моделях
для сумм стоит тип int, а не float или Decimal.
"""
import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# Строку подключения можно переопределить переменной окружения.
# По умолчанию файл базы лежит рядом с проектом.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./kvitto.db")


class Base(DeclarativeBase):
    """Базовый класс моделей SQLAlchemy."""


engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    """Зависимость FastAPI: выдаёт сессию базы на время запроса."""
    async with SessionLocal() as session:
        yield session


async def create_tables() -> None:
    """Создаёт таблицы, если их ещё нет.

    Миграции в задании не обязательны, поэтому схема поднимается этим вызовом
    при старте приложения.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
