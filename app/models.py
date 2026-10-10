"""Модели базы: тарифы и платежи."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def new_id() -> str:
    """Идентификатор платежа: строка UUID."""
    return str(uuid.uuid4())


def utcnow() -> datetime:
    """Текущее время в UTC без зоны, чтобы одинаково хранилось в SQLite и PostgreSQL."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Tariff(Base):
    """Тариф курса. Создаётся при старте приложения."""

    __tablename__ = "tariffs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    # Цена в копейках: 19 900 ₽ это 1990000.
    price: Mapped[int] = mapped_column(Integer, nullable=False)


class Payment(Base):
    """Платёж по тарифу."""

    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    tariff_id: Mapped[str] = mapped_column(ForeignKey("tariffs.id"), nullable=False)

    # Сумма к оплате и размер скидки, обе в копейках.
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    discount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    method: Mapped[str] = mapped_column(String(16), nullable=False)
    installment_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # График рассрочки: список сумм в копейках, для обычной оплаты null.
    schedule: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)

    email: Mapped[str] = mapped_column(String(254), nullable=False)

    # Ключ идемпотентности из заголовка запроса. Уникальный индекс не даёт
    # создать второй платёж с тем же ключом даже при одновременных запросах.
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128), nullable=True, unique=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
