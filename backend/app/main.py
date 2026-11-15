from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.config import settings, validate_settings
from app.db import init_db
from app.routers import auth, balances, export, groups, me, operations, receipts, users

DESCRIPTION = """
**Спільна каса** — вебзастосунок для спільного обліку фінансів у групах.

* Усі суми передаються **цілими числами в копійках** (`60000` = 600,00 ₴).
* Захищені ендпоінти потребують заголовка `Authorization: Bearer <token>` — натисніть **Authorize**.
* Дані групи доступні лише її учасникам (відповідь `403` для сторонніх).
"""


@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_settings(settings)  # у prod без власного секрету сервер не стартує (D08)
    init_db()
    yield


app = FastAPI(
    title="Спільна каса API",
    version="0.4.0",
    description=DESCRIPTION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

_FIELD_NAMES = {
    "amount_kop": "Сума",
    "email": "Email",
    "password": "Пароль",
    "display_name": "Ім'я",
    "name": "Назва",
    "participant_ids": "Учасники поділу",
    "invite_code": "Код запрошення",
    "title": "Назва чека",
    "items": "Позиції чека",
    "price_kop": "Ціна",
    "share_kop": "Частка",
    "kind": "Тип операцій",
}


def _humanize(err: dict) -> str:
    field = str(err.get("loc", ["", ""])[-1])
    label = _FIELD_NAMES.get(field, field)
    kind = err.get("type", "")
    if field == "amount_kop" and kind in {"greater_than", "int_parsing", "int_type"}:
        return "Сума має бути більшою за 0"
    if field == "price_kop" and kind in {"greater_than", "int_parsing", "int_type"}:
        return "Ціна позиції має бути більшою за 0"
    if field == "share_kop" and kind == "greater_than_equal":
        return "Частка не може бути від'ємною"
    if field == "amount_kop" and kind == "less_than_equal":
        return "Сума завелика"
    if kind == "missing":
        return f"Поле «{label}» обов'язкове"
    if kind in {"string_too_short", "too_short"}:
        return f"Поле «{label}» не може бути порожнім" if field != "password" else "Пароль має містити щонайменше 6 символів"
    if field == "email":
        return "Введіть коректний email"
    msg = str(err.get("msg", "Некоректні дані"))
    return msg.removeprefix("Value error, ")


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    detail = _humanize(errors[0]) if errors else "Некоректні дані"
    return JSONResponse(status_code=422, content={"detail": detail})


@app.exception_handler(OperationalError)
async def db_busy_handler(_: Request, exc: OperationalError) -> JSONResponse:
    """Блокування БД не дочекалися за відведений час — контрольована відповідь замість 500 (D02)."""
    if "locked" in str(exc.orig).lower() or "busy" in str(exc.orig).lower():
        return JSONResponse(status_code=503, content={"detail": "Сервер зараз зайнятий іншою зміною. Спробуйте ще раз за мить"})
    raise exc


for r in (
    auth.router,
    users.router,
    groups.router,
    operations.router,
    receipts.router,
    balances.router,
    export.router,
    me.router,
):
    app.include_router(r, prefix="/api")


@app.get("/api/health", tags=["Службове"], summary="Перевірка роботи сервера")
def health() -> dict[str, str]:
    return {"status": "ok"}
