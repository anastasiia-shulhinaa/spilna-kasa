from datetime import date
from io import BytesIO

from openpyxl import load_workbook

from app.services.export import ExportOp, build_workbook

MEMBERS = [(1, "Іванна"), (2, "Софія"), (3, "Марина")]
OPS = [
    ExportOp(date(2026, 11, 10), "expense", "equal", "Продукти", "Продукти", 1, None, 60000, {1: 20000, 2: 20000, 3: 20000}),
    ExportOp(date(2026, 11, 12), "transfer", "equal", "Повернення боргу", None, 2, 1, 20000, {}),
]


def _wb():
    data = build_workbook("Квартира", MEMBERS, OPS, {1: 20000, 2: 0, 3: -20000}, [(3, 1, 20000)])
    return load_workbook(BytesIO(data))


def test_export_has_three_sheets():
    assert _wb().sheetnames == ["Операції", "Баланси", "Хто кому винен"]


def test_export_operations_rows_and_member_columns():
    ws = _wb()["Операції"]
    header = [c.value for c in ws[1]]
    assert header[-3:] == ["Частка: Іванна", "Частка: Софія", "Частка: Марина"]
    assert ws.cell(2, 2).value == "Витрата" and ws.cell(2, 8).value == 600
    assert ws.cell(3, 2).value == "Повернення боргу" and ws.cell(3, 7).value == "Іванна"


def test_export_total_formula_counts_only_expenses():
    ws = _wb()["Операції"]
    total = ws.cell(5, 8).value
    assert ws.cell(5, 1).value == "Витрати групи"
    assert total.startswith("=SUMIF(") and '"Витрата"' in total


def test_export_balances_and_debts():
    wb = _wb()
    assert [r for r in wb["Баланси"].iter_rows(min_row=2, values_only=True)] == [
        ("Іванна", 200, "вам винні"),
        ("Софія", 0, "розрахувались"),
        ("Марина", -200, "має повернути"),
    ]
    assert list(wb["Хто кому винен"].iter_rows(min_row=2, values_only=True)) == [("Марина", "Іванна", 200)]
