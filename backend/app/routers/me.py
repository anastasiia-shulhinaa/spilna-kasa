from typing import Literal

from fastapi import APIRouter, Query
from sqlalchemy import select

from app import crud, schemas
from app.deps import CurrentUser, DbSession
from app.models import Group, Membership, Operation, User
from app.services.balances import settle

router = APIRouter(tags=["Мої борги та історія"])


def _my_groups(db, user_id: int) -> list[Group]:
    return list(
        db.scalars(select(Group).join(Membership).where(Membership.user_id == user_id).order_by(Group.id)).all()
    )


def _ref(g: Group) -> schemas.GroupRef:
    return schemas.GroupRef(id=g.id, name=g.name, emoji=g.emoji)


@router.get("/me/debts", response_model=schemas.MyDebtsOut, summary="Хто мені винен і кому винен я — зараз")
def my_debts(user: CurrentUser, db: DbSession) -> schemas.MyDebtsOut:
    """Для кожної групи береться актуальний план переказів (той самий, що у вкладці «Баланси»),
    і з нього вибираються перекази за участю поточного користувача. Суми по людях підсумовуються
    з розбивкою по групах; між групами борги не взаємозараховуються, бо повертаються в межах групи."""
    owed: dict[int, dict] = {}
    owe: dict[int, dict] = {}
    for group in _my_groups(db, user.id):
        names = {m.user_id: m.user for m in group.memberships}
        plan, _ = settle(crud.group_balances(group))
        for d in plan:
            if d.to_id == user.id:
                bucket, other = owed, d.from_id
            elif d.from_id == user.id:
                bucket, other = owe, d.to_id
            else:
                continue
            entry = bucket.setdefault(other, {"user": names[other], "total": 0, "groups": []})
            entry["total"] += d.amount_kop
            entry["groups"].append(schemas.DebtInGroup(group=_ref(group), amount_kop=d.amount_kop))

    def pack(bucket: dict[int, dict]) -> list[schemas.CounterpartDebt]:
        rows = [
            schemas.CounterpartDebt(user=schemas.UserPublic.model_validate(e["user"]), total_kop=e["total"], groups=e["groups"])
            for e in bucket.values()
        ]
        return sorted(rows, key=lambda r: (-r.total_kop, r.user.id))

    owed_rows, owe_rows = pack(owed), pack(owe)
    return schemas.MyDebtsOut(
        owed_to_me=owed_rows,
        i_owe=owe_rows,
        owed_to_me_total_kop=sum(r.total_kop for r in owed_rows),
        i_owe_total_kop=sum(r.total_kop for r in owe_rows),
    )


@router.get("/history", response_model=list[schemas.HistoryItem], summary="Історія операцій у всіх моїх групах")
def history(
    user: CurrentUser,
    db: DbSession,
    kind: Literal["all", "transfers", "expenses"] = Query("all", description="transfers — лише повернення боргів"),
    group_id: int | None = Query(None, description="Лише одна група"),
    mine: bool = Query(False, description="Лише операції, де я платник, отримувач або учасник поділу"),
    limit: int = Query(200, ge=1, le=500),
) -> list[schemas.HistoryItem]:
    groups = {g.id: g for g in _my_groups(db, user.id)}
    if group_id is not None:
        groups = {group_id: groups[group_id]} if group_id in groups else {}
    if not groups:
        return []
    q = select(Operation).where(Operation.group_id.in_(groups)).order_by(Operation.op_date.desc(), Operation.id.desc())
    if kind == "transfers":
        q = q.where(Operation.type == "transfer")
    elif kind == "expenses":
        q = q.where(Operation.type == "expense")

    people = {u.id: schemas.UserPublic.model_validate(u) for u in db.scalars(select(User)).all()}
    result: list[schemas.HistoryItem] = []
    for op in db.scalars(q).all():
        my_share = next((s.share_kop for s in op.shares if s.user_id == user.id), None)
        involved = user.id in (op.payer_id, op.recipient_id) or my_share is not None
        if mine and not involved:
            continue
        result.append(
            schemas.HistoryItem(
                id=op.id,
                group=_ref(groups[op.group_id]),
                type=op.type,
                split_mode=op.split_mode or "equal",
                amount_kop=op.amount_kop,
                payer=people[op.payer_id],
                recipient=people.get(op.recipient_id) if op.recipient_id else None,
                category=op.category,
                description=op.description,
                op_date=op.op_date,
                created_at=op.created_at,
                receipt_id=op.receipt.id if op.receipt else None,
                my_share_kop=my_share,
            )
        )
        if len(result) >= limit:
            break
    return result
