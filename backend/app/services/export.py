"""Експорт групи в Excel (.xlsx): операції з частками, баланси, хто кому винен."""

from dataclasses import dataclass
from datetime import date
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

MONEY = '#,##0.00 "₴";[Red]-#,##0.00 "₴"'
PINK = "E8457F"
HEADER_FILL = PatternFill("solid", fgColor=PINK)
TOTAL_FILL = PatternFill("solid", fgColor="FDE8F0")
HEADER_FONT = Font(bold=True, color="FFFFFF")
THIN = Side(style="thin", color="F7D9E6")

TYPE_LABELS = {"expense": "Витрата", "transfer": "Повернення боргу"}
SPLIT_LABELS = {"equal": "порівну", "exact": "точні суми", "items": "за чеком"}


@dataclass
class ExportOp:
    op_date: date
    type: str
    split_mode: str
    description: str
    category: str | None
    payer_id: int
    recipient_id: int | None
    amount_kop: int
    shares: dict[int, int]


def _header(ws, titles: list[str]) -> None:
    ws.append(titles)
    for cell in ws[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 30
    ws.freeze_panes = "A2"


def _widths(ws, widths: list[int]) -> None:
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def build_workbook(
    group_name: str,
    members: list[tuple[int, str]],
    ops: list[ExportOp],
    balances: dict[int, int],
    debts: list[tuple[int, int, int]],
    debts_optimal: bool = True,
) -> bytes:
    names = dict(members)
    wb = Workbook()

    # --- Аркуш 1: операції ---
    ws = wb.active
    ws.title = "Операції"
    fixed = ["Дата", "Тип", "Поділ", "Опис", "Категорія", "Хто платив", "Кому", "Сума"]
    _header(ws, fixed + [f"Частка: {n}" for _, n in members])
    for op in sorted(ops, key=lambda o: o.op_date):
        row = [
            op.op_date,
            TYPE_LABELS.get(op.type, op.type),
            SPLIT_LABELS.get(op.split_mode, "") if op.type == "expense" else "",
            op.description,
            op.category or "",
            names.get(op.payer_id, "?"),
            names.get(op.recipient_id, "") if op.recipient_id else "",
            op.amount_kop / 100,
        ] + [(op.shares[uid] / 100 if uid in op.shares else None) for uid, _ in members]
        ws.append(row)
    last = ws.max_row
    amount_col = get_column_letter(len(fixed))
    ws.append([])
    total_row = last + 2
    ws.cell(total_row, 1, "Витрати групи")
    ws.cell(total_row, len(fixed), f'=SUMIF(B2:B{last},"Витрата",{amount_col}2:{amount_col}{last})')
    for i in range(len(members)):
        col = get_column_letter(len(fixed) + 1 + i)
        ws.cell(total_row, len(fixed) + 1 + i, f"=SUM({col}2:{col}{last})")
    for cell in ws[total_row]:
        cell.font = Font(bold=True)
        cell.fill = TOTAL_FILL
    for row in ws.iter_rows(min_row=2, max_row=total_row):
        row[0].number_format = "DD.MM.YYYY"
        for cell in row[len(fixed) - 1 :]:
            cell.number_format = MONEY
        for cell in row:
            cell.border = Border(bottom=THIN)
    _widths(ws, [12, 18, 12, 30, 14, 14, 14, 14] + [16] * len(members))

    # --- Аркуш 2: баланси ---
    wb2 = wb.create_sheet("Баланси")
    _header(wb2, ["Учасник", "Баланс", "Стан"])
    for uid, name in members:
        b = balances.get(uid, 0)
        state = "вам винні" if b > 0 else "має повернути" if b < 0 else "розрахувались"
        wb2.append([name, b / 100, state])
        wb2.cell(wb2.max_row, 2).number_format = MONEY
    _widths(wb2, [20, 16, 20])

    # --- Аркуш 3: хто кому винен ---
    wb3 = wb.create_sheet("Хто кому винен")
    _header(wb3, ["Хто", "Кому", "Сума"])
    for frm, to, kop in debts:
        wb3.append([names.get(frm, "?"), names.get(to, "?"), kop / 100])
        wb3.cell(wb3.max_row, 3).number_format = MONEY
    if not debts:
        wb3.append(["Усе чисто, ніхто нікому не винен!"])
    elif not debts_optimal:
        wb3.append([])
        wb3.append(["Група велика: план переказів правильний, але мінімальність кількості переказів не доведено"])
    _widths(wb3, [20, 20, 16])

    wb.properties.title = f"Спільна каса — {group_name}"
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
