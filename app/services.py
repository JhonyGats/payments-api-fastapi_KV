"""Бизнес-логика: скидка, график рассрочки, статусы.

Вся арифметика идёт в копейках целыми числами, поэтому результат всегда
сходится до копейки и не зависит от ошибок округления float.
"""
from app.schemas import PROMO_DISCOUNT_PERCENT, PROMO_CODE

# Разрешённые переходы статусов платежа.
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"succeeded", "failed"},
    "succeeded": {"refunded"},
    "failed": set(),
    "refunded": set(),
}


def promo_is_valid(promo_code: str) -> bool:
    """Промокод сравнивается без учёта регистра и лишних пробелов."""
    return promo_code.strip().upper() == PROMO_CODE


def calc_discount(price: int) -> int:
    """Скидка 10 процентов от цены тарифа, в копейках, с округлением вниз.

    Для тарифов из задания деление точное, но округление вниз оставлено
    на случай других сумм: клиент не должен получить скидку больше положенной.
    """
    return price * PROMO_DISCOUNT_PERCENT // 100


def build_schedule(amount: int, months: int) -> list[int]:
    """Делит сумму на months платежей в копейках.

    Сумма всех платежей ровно равна сумме к оплате. Лишние копейки, которые
    не делятся нацело, добавляются к первым платежам.

    Пример: 1990000 на 3 месяца даёт [663334, 663333, 663333].
    """
    base, remainder = divmod(amount, months)
    return [base + 1] * remainder + [base] * (months - remainder)


def can_transition(current: str, target: str) -> bool:
    """Проверяет, разрешён ли переход из текущего статуса в целевой."""
    return target in ALLOWED_TRANSITIONS.get(current, set())
