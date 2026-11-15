from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app import crud, schemas
from app.deps import CurrentUser, DbSession, MemberGroup
from app.models import Group, Membership
from app.services.invites import normalize_code, unique_code

router = APIRouter(prefix="/groups", tags=["Групи"])

FORBIDDEN = {403: {"model": schemas.ErrorOut, "description": "Користувач не є учасником групи"}}


@router.get("", response_model=list[schemas.GroupSummary], summary="Мої групи (F05)")
def list_groups(user: CurrentUser, db: DbSession) -> list[schemas.GroupSummary]:
    groups = db.scalars(
        select(Group).join(Membership).where(Membership.user_id == user.id).order_by(Group.id)
    ).all()
    return [crud.group_summary(g, user.id) for g in groups]


@router.post(
    "",
    response_model=schemas.GroupDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Створити групу (F03)",
)
def create_group(data: schemas.GroupCreate, user: CurrentUser, db: DbSession) -> schemas.GroupDetail:
    code = unique_code(lambda c: db.scalar(select(Group.id).where(Group.invite_code == c)) is not None)
    group = Group(name=data.name.strip(), emoji=data.emoji or "💗", invite_code=code, created_by=user.id)
    group.memberships.append(Membership(user_id=user.id, role="owner"))
    db.add(group)
    db.commit()
    db.refresh(group)
    return crud.group_detail(group, user.id)


@router.post(
    "/join",
    response_model=schemas.GroupDetail,
    summary="Вступити за кодом запрошення (F04)",
    responses={
        404: {"model": schemas.ErrorOut, "description": "Код не знайдено"},
        409: {"model": schemas.ErrorOut, "description": "Користувач уже в групі"},
    },
)
def join_group(data: schemas.JoinIn, user: CurrentUser, db: DbSession) -> schemas.GroupDetail:
    group = db.scalar(select(Group).where(Group.invite_code == normalize_code(data.invite_code)))
    if group is None:
        raise HTTPException(status_code=404, detail="Групу з таким кодом не знайдено")
    if any(m.user_id == user.id for m in group.memberships):
        raise HTTPException(status_code=409, detail="Ви вже в цій групі")
    group.memberships.append(Membership(user_id=user.id, role="member"))
    db.commit()
    db.refresh(group)
    return crud.group_detail(group, user.id)


@router.get(
    "/{group_id}",
    response_model=schemas.GroupDetail,
    summary="Група з учасниками (F05)",
    responses=FORBIDDEN,
)
def get_group(group: MemberGroup, user: CurrentUser) -> schemas.GroupDetail:
    return crud.group_detail(group, user.id)
