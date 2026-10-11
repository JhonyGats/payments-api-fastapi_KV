"""Точка входа: приложение FastAPI, эндпоинты и создание тарифов."""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import create_tables, get_session
from app.models import Tariff, Payment
from app.schemas import PaymentCreate, PaymentOut, TariffOut, WebhookIn
from app.services import build_schedule, can_transition, calc_discount, promo_percent

# Тарифы создаются при старте приложения. Цены в копейках.
TARIFFS = [
    {"id": "basic", "title": "Базовый курс", "price": 990_000},        # 9 900 ₽
    {"id": "standard", "title": "Стандартный курс", "price": 1_990_000},  # 19 900 ₽
    {"id": "premium", "title": "Премиум курс", "price": 2_990_000},      # 29 900 ₽
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Создаёт таблицы и наполняет справочник тарифов при запуске."""
    await create_tables()
    from app.database import SessionLocal

    async with SessionLocal() as session:
        for item in TARIFFS:
            exists = await session.get(Tariff, item["id"])
            if exists is None:
                session.add(Tariff(**item))
        await session.commit()
    yield


app = FastAPI(title="Квитто: API платежей", version="1.0.0", lifespan=lifespan)


@app.get("/tariffs", response_model=list[TariffOut], summary="Список тарифов")
async def list_tariffs(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Tariff).order_by(Tariff.price))
    return list(result.scalars().all())


@app.post(
    "/payments",
    response_model=PaymentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Создать платёж",
)
async def create_payment(
    body: PaymentCreate,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_session),
):
    """Создаёт платёж, считает скидку и график рассрочки.

    Если передан заголовок Idempotency-Key и платёж с таким ключом уже есть,
    возвращается тот же платёж с кодом 200, второй не создаётся.
    """
    if idempotency_key:
        existing = await _find_by_idempotency_key(session, idempotency_key)
        if existing is not None:
            response.status_code = status.HTTP_200_OK
            return existing

    tariff = await session.get(Tariff, body.tariff_id)
    if tariff is None:
        # 422 как и для неизвестного промокода: тело запроса корректное,
        # но ссылается на то, чего нет.
        raise HTTPException(status_code=422, detail="unknown tariff_id")

    discount = 0
    if body.promo_code is not None:
        percent = promo_percent(body.promo_code)
        if percent is None:
            raise HTTPException(status_code=422, detail="unknown promo_code")
        discount = calc_discount(tariff.price, percent)

    amount = tariff.price - discount
    schedule = None
    if body.method == "installment":
        schedule = build_schedule(amount, body.installment_months)

    payment = Payment(
        tariff_id=tariff.id,
        amount=amount,
        discount=discount,
        method=body.method,
        installment_months=body.installment_months,
        schedule=schedule,
        email=str(body.email),
        idempotency_key=idempotency_key,
        status="pending",
    )
    session.add(payment)
    try:
        await session.commit()
    except IntegrityError:
        # Ключ идемпотентности занят: значит параллельный запрос успел первым.
        await session.rollback()
        existing = await _find_by_idempotency_key(session, idempotency_key)
        if existing is None:
            raise
        response.status_code = status.HTTP_200_OK
        return existing

    await session.refresh(payment)
    return payment


@app.get("/payments/{payment_id}", response_model=PaymentOut, summary="Платёж по id")
async def get_payment(payment_id: str, session: AsyncSession = Depends(get_session)):
    payment = await session.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payment not found")
    return payment


@app.post("/webhooks/bank", summary="Уведомление банка о смене статуса")
async def bank_webhook(body: WebhookIn, session: AsyncSession = Depends(get_session)):
    """Меняет статус платежа по уведомлению банка.

    Нет платежа: 404. Запрещённый переход: 409 и статус не меняется.
    """
    payment = await session.get(Payment, body.payment_id)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payment not found")

    if not can_transition(payment.status, body.status):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": "invalid_transition"},
        )

    payment.status = body.status
    await session.commit()
    return {"result": "ok"}


async def _find_by_idempotency_key(session: AsyncSession, key: str) -> Payment | None:
    """Ищет платёж по ключу идемпотентности."""
    result = await session.execute(select(Payment).where(Payment.idempotency_key == key))
    return result.scalar_one_or_none()
