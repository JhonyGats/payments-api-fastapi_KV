# Квитто: тестовое задание, API платежей (Junior Python / FastAPI)

Сервис принимает оплату курса онлайн-школы: три эндпоинта для клиента и вебхук от банка.
Тестовое задание выполнено на Python 3.11+ (проверено на 3.14), FastAPI, Pydantic v2,
SQLAlchemy 2.0 в асинхронном режиме, база SQLite, тесты на pytest.

## Запуск

```bash
python -m venv .venv
# Windows
.venv\Scripts\python -m pip install -r requirements.txt
# Linux и macOS
# .venv/bin/python -m pip install -r requirements.txt

# запуск сервера
.venv\Scripts\python -m uvicorn app.main:app --reload
# документация: http://127.0.0.1:8000/docs
```

Таблицы создаются и тарифы наполняются при старте приложения, отдельная команда не нужна.
Файл базы `kvitto.db` создаётся в корне проекта, путь можно переопределить переменной
`DATABASE_URL`, например для PostgreSQL:

```bash
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/kvitto
```

## Тесты

```bash
.venv\Scripts\python -m pytest -q
```

Тесты поднимают приложение целиком через `TestClient` (в его основе httpx) и работают
с отдельной временной базой, рабочая база не затрагивается.

```
11 passed
```

## Примеры запросов

Список тарифов:

```bash
curl http://127.0.0.1:8000/tariffs
```

```json
[{"id":"basic","title":"Базовый курс","price":990000},
 {"id":"standard","title":"Стандартный курс","price":1990000},
 {"id":"premium","title":"Премиум курс","price":2990000}]
```

Создание платежа с рассрочкой и промокодом в нижнем регистре:

```bash
curl -X POST http://127.0.0.1:8000/payments \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: order-42" \
  -d '{"tariff_id":"standard","email":"student@example.com",
       "method":"installment","installment_months":3,"promo_code":"kvitto10"}'
```

```json
{"id":"151db9c0-04bf-409e-8fed-6cfb9ace6595","status":"pending","tariff_id":"standard",
 "amount":1791000,"discount":199000,"method":"installment","installment_months":3,
 "schedule":[597000,597000,597000],"email":"student@example.com",
 "created_at":"2026-10-10T11:43:21.369571"}
```

Тот же запрос с тем же `Idempotency-Key` вернёт **тот же платёж с кодом 200** и второй не создаст.

Платёж по id и вебхук банка:

```bash
curl http://127.0.0.1:8000/payments/<id>

curl -X POST http://127.0.0.1:8000/webhooks/bank \
  -H "Content-Type: application/json" \
  -d '{"payment_id":"<id>","status":"succeeded"}'
```

```json
{"result":"ok"}
```

Запрещённый переход, например `pending` сразу в `refunded`, возвращает код 409 и статус не меняет:

```json
{"error":"invalid_transition"}
```

## Структура

```
app/
  database.py  подключение к базе, сессия, создание таблиц
  models.py    модели Tariff и Payment
  schemas.py   схемы Pydantic v2 (запросы, ответы, допустимые значения)
  services.py  бизнес-логика: скидка, график рассрочки, переходы статусов
  main.py      приложение FastAPI, эндпоинты, наполнение тарифов при старте
tests/
  conftest.py       фикстуры: клиент API и отдельная база для тестов
  test_payments.py  11 тестов по сценариям задания
```

## Решения, важные для денег

- **Все суммы целым числом в копейках.** В моделях для сумм стоит `int`, float не используется,
  поэтому копейки не теряются при округлении.
- **Скидка считается целочисленно** как `price * 10 // 100`, с округлением вниз: клиент
  не должен получить скидку больше положенной.
- **График рассрочки** строится делением с остатком: `divmod(amount, months)`, остаток
  распределяется по одному копеечному довеску в первые платежи. Сумма графика всегда
  ровно равна сумме к оплате, пример из задания воспроизводится: 1 990 000 на 3 месяца
  даёт [663334, 663333, 663333].
- **Идемпотентность** держится на уникальном индексе по ключу: при повторном запросе платёж
  находится по ключу и возвращается с кодом 200. Если два одинаковых запроса придут
  одновременно, гонку отсечёт база по уникальному индексу, а не проверка в коде.
- **Статусы** описаны таблицей переходов в `services.py`: `pending → succeeded`,
  `pending → failed`, `succeeded → refunded`. Любой другой переход это 409 без изменения статуса.

## Что не делал

Бонусные пункты задания не реализованы, чтобы сдать небольшую, но надёжную работу:
Docker Compose, проверка подписи вебхука через HMAC, миграции Alembic, расширенные фильтры
в списке платежей, GitHub Actions, файл правил для ассистента.
