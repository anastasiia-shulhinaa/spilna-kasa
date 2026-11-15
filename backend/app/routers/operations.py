from datetime import date

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from app import crud, schemas
from app.deps import CurrentUser, DbSession, MemberGroup
from app.models import Operation, OperationShare
from app.services.money import split_equal, split_exact

router = APIRouter(prefix="/groups/{group_id}", tags=["Операції"])

ERRORS = {
    400: {"model": schemas.ErrorOut, "description": "Некоректні учасники або частки"},
    403: {"model": schemas.ErrorOut, "description": "Користувач не є учасником групи"},
}


@router.get("/operations", response_model=list[schemas.OperationOut], summary="Стрічка операцій групи")
def list_operations(group: MemberGroup, db: DbSession) -> list[schemas.OperationOut]:
    ops = db.scalars(
        select(Operation)
        .where(Operation.group_id == group.id)
        .order_by(Operation.op_date.desc(), Operation.id.desc())
    ).all()
    return [crud.operation_out(op) for op in ops]


@router.post(
    "/expenses",
    response_model=schemas.OperationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Додати витрату: порівну (F07) або точними сумами (F12)",
    responses=ERRORS,
)
def create_expense(
    data: schemas.ExpenseCreate, group: MemberGroup, user: CurrentUser, db: DbSession
) -> schemas.OperationOut:
    members = set(crud.member_ids(group))
    if data.payer_id not in members:
        raise HTTPException(status_code=400, detail="Платник має бути учасником групи")

    try:
        if data.split_mode == "equal":
            if not set(data.participant_ids) <= members:
                raise HTTPException(status_code=400, detail="Усі учасники поділу мають бути в групі")
            shares = split_equal(data.amount_kop, data.participant_ids)
        else:
            requested = {s.user_id: s.share_kop for s in data.shares}
            if len(requested) != len(data.shares):
                raise HTTPException(status_code=400, detail="Учасник не може мати дві частки")
            if not set(requested) <= members:
                raise HTTPException(status_code=400, detail="Усі учасники поділу мають бути в групі")
            shares = split_exact(data.amount_kop, requested)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    op = Operation(
        group_id=group.id,
        type="expense",
        split_mode=data.split_mode,
        amount_kop=data.amount_kop,
        payer_id=data.payer_id,
        category=data.category,
        description=data.description.strip(),
        op_date=data.op_date or date.today(),
        created_by=user.id,
        shares=[OperationShare(user_id=uid, share_kop=kop) for uid, kop in shares.items()],
    )
    db.add(op)
    db.commit()
    db.refresh(op)
    return crud.operation_out(op)


@router.post(
    "/transfers",
    response_model=schemas.OperationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Відмітити повернення боргу (F10)",
    responses=ERRORS,
)
def create_transfer(
    data: schemas.TransferCreate, group: MemberGroup, user: CurrentUser, db: DbSession
) -> schemas.OperationOut:
    members = set(crud.member_ids(group))
    if data.from_user_id not in members or data.to_user_id not in members:
        raise HTTPException(status_code=400, detail="Обидва учасники переказу мають бути в групі")
    if data.from_user_id == data.to_user_id:
        raise HTTPException(status_code=400, detail="Не можна переказати гроші самому собі")

    op = Operation(
        group_id=group.id,
        type="transfer",
        amount_kop=data.amount_kop,
        payer_id=data.from_user_id,
        recipient_id=data.to_user_id,
        category=None,
        description="Повернення боргу",
        op_date=data.op_date or date.today(),
        created_by=user.id,
    )
    db.add(op)
    db.commit()
    db.refresh(op)
    return crud.operation_out(op)


@router.delete(
    "/operations/{operation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Видалити помилкову операцію",
    description="Видалити може автор запису або платник. Якщо витрату створено з чека, чек знову відкривається для виправлення.",
    responses={**ERRORS, 404: {"model": schemas.ErrorOut, "description": "Операцію не знайдено"}},
)
def delete_operation(operation_id: int, group: MemberGroup, user: CurrentUser, db: DbSession) -> Response:
    op = db.get(Operation, operation_id)
    if op is None or op.group_id != group.id:
        raise HTTPException(status_code=404, detail="Операцію не знайдено")
    if user.id not in (op.created_by, op.payer_id):
        raise HTTPException(status_code=403, detail="Видалити запис може лише його автор або платник")
    receipt = op.receipt
    if receipt is not None:
        # Спершу відкриваємо чек і відв'язуємо операцію (позначки зберігаються), потім видаляємо операцію —
        # усе в одній транзакції; відкладений FK перевіряється на коміті (D01)
        receipt.status, receipt.operation_id = "open", None
        db.flush()
    db.delete(op)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
