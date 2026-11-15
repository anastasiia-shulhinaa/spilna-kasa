from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app import schemas
from app.deps import DbSession
from app.models import User
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Автентифікація"])


@router.post(
    "/register",
    response_model=schemas.TokenOut,
    status_code=status.HTTP_201_CREATED,
    summary="Реєстрація (F01)",
    responses={409: {"model": schemas.ErrorOut, "description": "Email уже зареєстровано"}},
)
def register(data: schemas.RegisterIn, db: DbSession) -> schemas.TokenOut:
    email = data.email.lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=409, detail="Цей email уже зареєстровано")
    user = User(email=email, display_name=data.display_name, password_hash=hash_password(data.password))
    db.add(user)
    db.commit()
    return schemas.TokenOut(access_token=create_access_token(user.id))


@router.post(
    "/login",
    response_model=schemas.TokenOut,
    summary="Вхід (F01)",
    responses={401: {"model": schemas.ErrorOut, "description": "Невірний email або пароль"}},
)
def login(data: schemas.LoginIn, db: DbSession) -> schemas.TokenOut:
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Невірний email або пароль")
    return schemas.TokenOut(access_token=create_access_token(user.id))
