from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Response

from app import crud
from app.deps import MemberGroup
from app.services.balances import settle
from app.services.export import ExportOp, build_workbook

router = APIRouter(prefix="/groups/{group_id}", tags=["Експорт"])

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get(
    "/export.xlsx",
    summary="Експорт групи в Excel",
    response_class=Response,
    responses={200: {"content": {XLSX: {}}, "description": "Файл .xlsx: операції, баланси, хто кому винен"}},
)
def export_group(group: MemberGroup) -> Response:
    members = [(m.user_id, m.user.display_name) for m in group.memberships]
    ops = [
        ExportOp(
            op_date=op.op_date,
            type=op.type,
            split_mode=op.split_mode or "equal",
            description=op.description,
            category=op.category,
            payer_id=op.payer_id,
            recipient_id=op.recipient_id,
            amount_kop=op.amount_kop,
            shares={s.user_id: s.share_kop for s in op.shares},
        )
        for op in group.operations
    ]
    balances = crud.group_balances(group)
    plan, optimal = settle(balances)  # та сама функція, що й в API балансів
    debts = [(d.from_id, d.to_id, d.amount_kop) for d in plan]
    content = build_workbook(group.name, members, ops, balances, debts, debts_optimal=optimal)

    filename = f"Спільна каса — {group.name} — {date.today():%d.%m.%Y}.xlsx"
    ascii_name = f"spilna-kasa-{group.id}.xlsx"
    return Response(
        content=content,
        media_type=XLSX,
        headers={"Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"},
    )
