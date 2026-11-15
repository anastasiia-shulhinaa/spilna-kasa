from collections.abc import Callable, Iterator

from fastapi import Request
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

# Номер версії схеми БД. Збільшується при зміні таблиць або обмежень;
# стара база тоді не запуститься мовчки з неправильною схемою.
SCHEMA_VERSION = 2

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
IMMEDIATE = "kasa_begin_immediate"


class Base(DeclarativeBase):
    pass


class SchemaOutdated(RuntimeError):
    pass


def configure_sqlite(engine: Engine) -> None:
    """Транзакції SQLite під повним контролем застосунку.

    * зовнішні ключі увімкнено (SQLite за замовчуванням їх не перевіряє);
    * драйвер не відкриває транзакції сам — BEGIN надсилаємо ми;
    * запити на запис починаються з BEGIN IMMEDIATE ще до першого читання,
      тож два одночасні запити до одного чека виконуються строго по черзі (D02).
    """

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_conn, _):
        dbapi_conn.isolation_level = None
        dbapi_conn.execute("PRAGMA foreign_keys=ON")
        dbapi_conn.execute(f"PRAGMA busy_timeout={int(settings.db_lock_timeout_s * 1000)}")

    @event.listens_for(engine, "begin")
    def _on_begin(conn):
        conn.exec_driver_sql("BEGIN IMMEDIATE" if conn.get_execution_options().get(IMMEDIATE) else "BEGIN")


def make_engine(url: str) -> Engine:
    is_sqlite = url.startswith("sqlite")
    engine = create_engine(url, connect_args={"check_same_thread": False} if is_sqlite else {})
    if is_sqlite:
        configure_sqlite(engine)
    return engine


engine = make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def begin_write(session: Session) -> None:
    """Відкрити транзакцію запису (BEGIN IMMEDIATE) до будь-якого читання."""
    session.connection(execution_options={IMMEDIATE: True})


def make_get_db(factory: Callable[[], Session]):
    def get_db(request: Request) -> Iterator[Session]:
        db = factory()
        try:
            if request.method in WRITE_METHODS:
                begin_write(db)
            yield db
        finally:
            db.close()

    return get_db


get_db = make_get_db(SessionLocal)


def create_schema(bind: Engine) -> None:
    from app import models  # noqa: F401  реєструє таблиці

    Base.metadata.create_all(bind=bind)
    with bind.begin() as conn:
        conn.exec_driver_sql(f"PRAGMA user_version={SCHEMA_VERSION}")


def init_db(bind: Engine | None = None) -> None:
    bind = bind or engine
    has_tables = bool(inspect(bind).get_table_names())
    if not has_tables:
        create_schema(bind)
        return
    with bind.connect() as conn:
        version = conn.exec_driver_sql("PRAGMA user_version").scalar()
    if version != SCHEMA_VERSION:
        raise SchemaOutdated(
            "Схема бази даних застаріла. Створіть базу заново: "
            "python -m app.seed (або .\\dev.ps1 -Reset). Демо-дані буде перезаписано."
        )
