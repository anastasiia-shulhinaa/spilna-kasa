from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import configure_sqlite, create_schema, get_db, make_get_db
from app.main import app


def _client(engine, tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr("app.main.init_db", lambda: None)  # тести не чіпають робочу базу kasa.db
    configure_sqlite(engine)  # ті самі правила транзакцій, що й у робочому застосунку
    create_schema(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    app.dependency_overrides[get_db] = make_get_db(factory)
    return factory


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Окрема чиста БД у пам'яті та тимчасова тека для фото в кожному тесті."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    _client(engine, tmp_path, monkeypatch)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture()
def file_db(tmp_path, monkeypatch):
    """БД у файлі з окремими з'єднаннями — для перевірки одночасних запитів (D02)."""
    engine = create_engine(f"sqlite:///{tmp_path / 'race.db'}", connect_args={"check_same_thread": False})
    factory = _client(engine, tmp_path, monkeypatch)
    with TestClient(app) as c:
        yield c, factory
    app.dependency_overrides.clear()
    engine.dispose()


def png_bytes(color=(232, 69, 127), size=(64, 48)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


def register(client: TestClient, name: str) -> dict:
    """Реєструє користувача й повертає заголовки авторизації та id."""
    email = f"{name.lower()}@test.ua"
    r = client.post("/api/auth/register", json={"email": email, "password": "secret123", "display_name": name})
    assert r.status_code == 201, r.text
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    me = client.get("/api/users/me", headers=headers).json()
    return {"headers": headers, "id": me["id"], "email": email}


@pytest.fixture()
def trio(client):
    """Контрольний сценарій етапу 3: Іванна, Софія, Марина в групі «Квартира»."""
    ivanna, sofia, maryna = (register(client, n) for n in ("Ivanna", "Sofia", "Maryna"))
    g = client.post("/api/groups", json={"name": "Квартира", "emoji": "🏠"}, headers=ivanna["headers"]).json()
    for person in (sofia, maryna):
        r = client.post("/api/groups/join", json={"invite_code": g["invite_code"]}, headers=person["headers"])
        assert r.status_code == 200, r.text
    return {"group": g, "ivanna": ivanna, "sofia": sofia, "maryna": maryna}
