from fastapi import APIRouter

from app import crud, schemas
from app.deps import MemberGroup
from app.services.balances import settle

router = APIRouter(prefix="/groups/{group_id}", tags=["Баланси"])


@router.get(
    "/balances",
    response_model=schemas.BalancesOut,
    summary="Баланси учасників і хто кому винен (F08, F09)",
    responses={403: {"model": schemas.ErrorOut, "description": "Користувач не є учасником групи"}},
)
def get_balances(group: MemberGroup) -> schemas.BalancesOut:
    users = {m.user_id: schemas.UserPublic.model_validate(m.user) for m in group.memberships}
    balances = crud.group_balances(group)
    debts, optimal = settle(balances)
    return schemas.BalancesOut(
        members=[schemas.MemberBalance(user=users[uid], balance_kop=balances.get(uid, 0)) for uid in users],
        debts=[
            schemas.DebtOut(from_user=users[d.from_id], to_user=users[d.to_id], amount_kop=d.amount_kop)
            for d in debts
        ],
        debts_optimal=optimal,
        total_expenses_kop=crud.group_total_expenses(group),
    )
