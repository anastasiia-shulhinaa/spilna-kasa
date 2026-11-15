"""Допоміжні функції, які перетворюють записи БД на відповіді API."""

from app import schemas
from app.models import Group, Operation, Receipt
from app.services.balances import OpView, compute_balances, total_expenses
from app.services.receipts import preview_split


def to_opview(op: Operation) -> OpView:
    return OpView(
        type=op.type,
        amount_kop=op.amount_kop,
        payer_id=op.payer_id,
        recipient_id=op.recipient_id,
        shares={s.user_id: s.share_kop for s in op.shares},
    )


def member_ids(group: Group) -> list[int]:
    return [m.user_id for m in group.memberships]


def group_balances(group: Group) -> dict[int, int]:
    return compute_balances((to_opview(op) for op in group.operations), member_ids(group))


def group_total_expenses(group: Group) -> int:
    return total_expenses(to_opview(op) for op in group.operations)


def members_out(group: Group) -> list[schemas.MemberOut]:
    return [
        schemas.MemberOut(id=m.user.id, display_name=m.user.display_name, role=m.role) for m in group.memberships
    ]


def group_summary(group: Group, user_id: int) -> schemas.GroupSummary:
    return schemas.GroupSummary(
        id=group.id,
        name=group.name,
        emoji=group.emoji,
        currency=group.currency,
        members=members_out(group),
        my_balance_kop=group_balances(group).get(user_id, 0),
    )


def group_detail(group: Group, user_id: int) -> schemas.GroupDetail:
    summary = group_summary(group, user_id)
    return schemas.GroupDetail(
        **summary.model_dump(),
        invite_code=group.invite_code,
        total_expenses_kop=group_total_expenses(group),
    )


def operation_out(op: Operation) -> schemas.OperationOut:
    return schemas.OperationOut(
        id=op.id,
        type=op.type,
        split_mode=op.split_mode or "equal",
        created_by=op.created_by,
        receipt_id=op.receipt.id if op.receipt else None,
        amount_kop=op.amount_kop,
        payer_id=op.payer_id,
        recipient_id=op.recipient_id,
        category=op.category,
        description=op.description,
        op_date=op.op_date,
        created_at=op.created_at,
        shares=[schemas.ShareOut(user_id=s.user_id, share_kop=s.share_kop) for s in op.shares],
    )


def receipt_items_spec(receipt: Receipt) -> list[tuple[int, list[int]]]:
    return [(item.price_kop, [c.user_id for c in item.claims]) for item in receipt.items]


def receipt_out(receipt: Receipt) -> schemas.ReceiptOut:
    totals, unclaimed = preview_split(receipt_items_spec(receipt))
    return schemas.ReceiptOut(
        id=receipt.id,
        group_id=receipt.group_id,
        title=receipt.title,
        category=receipt.category,
        payer_id=receipt.payer_id,
        created_by=receipt.created_by,
        status=receipt.status,
        has_photo=receipt.photo_path is not None,
        photo_version=receipt.photo_path.split(".")[0][:12] if receipt.photo_path else None,
        operation_id=receipt.operation_id,
        op_date=receipt.op_date,
        created_at=receipt.created_at,
        items=[
            schemas.ReceiptItemOut(
                id=i.id, name=i.name, price_kop=i.price_kop, claimed_by=[c.user_id for c in i.claims]
            )
            for i in receipt.items
        ],
        total_kop=sum(i.price_kop for i in receipt.items),
        unclaimed_kop=unclaimed,
        totals=[schemas.ShareOut(user_id=u, share_kop=k) for u, k in totals.items()],
    )
