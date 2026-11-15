from fastapi import APIRouter

from app import schemas
from app.deps import CurrentUser, DbSession

router = APIRouter(prefix="/users", tags=["Профіль"])


@router.get("/me", response_model=schemas.UserOut, summary="Мій профіль (F02)")
def me(user: CurrentUser) -> schemas.UserOut:
    return schemas.UserOut.model_validate(user)


@router.patch("/me", response_model=schemas.UserOut, summary="Змінити ім'я (F02)")
def update_me(data: schemas.UserUpdate, user: CurrentUser, db: DbSession) -> schemas.UserOut:
    user.display_name = data.display_name.strip()
    db.commit()
    return schemas.UserOut.model_validate(user)
