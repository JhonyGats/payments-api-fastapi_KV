"""Схемы запросов и ответов (Pydantic v2)."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

# Допустимые способы оплаты.
PaymentMethod = Literal["card", "sbp", "installment"]
# Допустимые сроки рассрочки.
InstallmentMonths = Literal[3, 6, 12]
# Промокод, который даёт скидку 10 процентов.
PROMO_CODE = "KVITTO10"
PROMO_DISCOUNT_PERCENT = 10


class TariffOut(BaseModel):
    """Тариф в ответе GET /tariffs."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    price: int


class PaymentCreate(BaseModel):
    """Тело запроса POST /payments."""

    tariff_id: str = Field(min_length=1, max_length=32)
    email: EmailStr
    method: PaymentMethod
    installment_months: InstallmentMonths | None = None
    promo_code: str | None = None

    @model_validator(mode="after")
    def check_installment(self):
        """Срок рассрочки обязателен только для способа installment."""
        if self.method == "installment" and self.installment_months is None:
            raise ValueError("installment_months обязателен для способа installment")
        if self.method != "installment" and self.installment_months is not None:
            raise ValueError("installment_months передаётся только для способа installment")
        return self


class PaymentOut(BaseModel):
    """Платёж в ответах API."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    tariff_id: str
    amount: int
    discount: int
    method: str
    installment_months: int | None = None
    schedule: list[int] | None = None
    email: str
    created_at: datetime


class WebhookIn(BaseModel):
    """Тело запроса POST /webhooks/bank."""

    payment_id: str
    status: Literal["succeeded", "failed", "refunded"]
