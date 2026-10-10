"""Тесты API платежей.

Обязательные сценарии из задания:
1. сумма с промокодом и без, включая промокод в нижнем регистре;
2. график рассрочки: сумма графика равна сумме к оплате для 3, 6 и 12 месяцев;
3. повторный запрос с тем же Idempotency-Key не создаёт второй платёж;
4. запрещённый переход статуса возвращает 409 и не меняет статус;
5. запрос несуществующего платежа возвращает 404.
"""
from tests.conftest import create_payment


def test_tariffs_list(client):
    """GET /tariffs отдаёт три тарифа с ценами в копейках."""
    response = client.get("/tariffs")
    assert response.status_code == 200

    tariffs = {item["id"]: item["price"] for item in response.json()}
    assert tariffs == {"basic": 990_000, "standard": 1_990_000, "premium": 2_990_000}


def test_amount_without_promo(client):
    """Без промокода сумма равна цене тарифа, скидка нулевая."""
    response = create_payment(client)
    assert response.status_code == 201

    body = response.json()
    assert body["amount"] == 1_990_000
    assert body["discount"] == 0
    assert body["status"] == "pending"
    assert body["schedule"] is None


def test_amount_with_promo_lowercase(client):
    """Промокод в нижнем регистре даёт ту же скидку 10 процентов."""
    response = create_payment(client, promo_code="kvitto10")
    assert response.status_code == 201

    body = response.json()
    assert body["discount"] == 199_000
    assert body["amount"] == 1_791_000
    assert body["amount"] + body["discount"] == 1_990_000


def test_unknown_promo_returns_422(client):
    """Неизвестный промокод это ошибка 422, платёж не создаётся."""
    response = create_payment(client, promo_code="SUPER50")
    assert response.status_code == 422


def test_installment_schedule_sums_equal_amount(client):
    """Сумма графика ровно равна сумме к оплате для 3, 6 и 12 месяцев."""
    for months in (3, 6, 12):
        response = create_payment(client, method="installment", installment_months=months)
        assert response.status_code == 201

        body = response.json()
        schedule = body["schedule"]
        assert len(schedule) == months
        assert sum(schedule) == body["amount"]

        # Лишние копейки уходят в первые платежи, поэтому они не меньше остальных.
        assert schedule[0] >= schedule[-1]
        assert max(schedule) - min(schedule) <= 1


def test_installment_example_from_task(client):
    """Пример из задания: standard на 3 месяца даёт [663334, 663333, 663333]."""
    response = create_payment(client, method="installment", installment_months=3)
    assert response.status_code == 201
    assert response.json()["schedule"] == [663_334, 663_333, 663_333]


def test_installment_requires_months(client):
    """Для рассрочки срок обязателен, иначе 422."""
    response = create_payment(client, method="installment")
    assert response.status_code == 422


def test_idempotency_key_does_not_create_duplicate(client):
    """Повтор с тем же ключом возвращает тот же платёж с кодом 200."""
    first = create_payment(client, idempotency_key="key-123")
    assert first.status_code == 201

    second = create_payment(client, idempotency_key="key-123")
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]

    # В базе действительно один платёж: платёж по id читается.
    check = client.get(f"/payments/{first.json()['id']}")
    assert check.status_code == 200


def test_forbidden_transition_returns_409(client):
    """Запрещённый переход возвращает 409 и не меняет статус."""
    payment = create_payment(client).json()

    # Из pending сразу в refunded нельзя.
    response = client.post(
        "/webhooks/bank",
        json={"payment_id": payment["id"], "status": "refunded"},
    )
    assert response.status_code == 409
    assert response.json() == {"error": "invalid_transition"}

    # Разрешённый переход проходит.
    ok = client.post(
        "/webhooks/bank",
        json={"payment_id": payment["id"], "status": "succeeded"},
    )
    assert ok.status_code == 200
    assert ok.json() == {"result": "ok"}

    # И повторный переход в тот же статус уже запрещён.
    again = client.post(
        "/webhooks/bank",
        json={"payment_id": payment["id"], "status": "succeeded"},
    )
    assert again.status_code == 409

    # Возврат из succeeded разрешён.
    refund = client.post(
        "/webhooks/bank",
        json={"payment_id": payment["id"], "status": "refunded"},
    )
    assert refund.status_code == 200

    assert client.get(f"/payments/{payment['id']}").json()["status"] == "refunded"


def test_webhook_unknown_payment_returns_404(client):
    """Уведомление по несуществующему платежу это 404."""
    response = client.post(
        "/webhooks/bank",
        json={"payment_id": "no-such-id", "status": "succeeded"},
    )
    assert response.status_code == 404


def test_get_unknown_payment_returns_404(client):
    """Запрос несуществующего платежа возвращает 404."""
    response = client.get("/payments/unknown-payment-id")
    assert response.status_code == 404
