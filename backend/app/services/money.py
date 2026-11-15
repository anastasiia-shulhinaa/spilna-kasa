"""Робота з грошима. Усі суми зберігаються цілими числами в копійках, щоб уникнути помилок округлення."""

import re
from collections.abc import Sequence

MAX_AMOUNT_KOP = 100_000_000_00  # 100 млн грн — верхня межа для однієї операції

_AMOUNT_RE = re.compile(r"^\d{1,12}([.,]\d{1,2})?$")


def split_equal(amount_kop: int, participant_ids: Sequence[int]) -> dict[int, int]:
    """Рівний поділ суми між учасниками.

    Залишок від ділення (копійки, що не діляться порівну) отримують перші учасники
    за зростанням id — по одній копійці. Сума часток завжди дорівнює початковій сумі:
    10000 / 3 -> 3334 + 3333 + 3333.
    """
    if amount_kop <= 0:
        raise ValueError("Сума має бути більшою за 0")
    if not participant_ids:
        raise ValueError("Оберіть хоча б одного учасника поділу")
    if len(set(participant_ids)) != len(participant_ids):
        raise ValueError("Учасники поділу не можуть повторюватися")

    ordered = sorted(participant_ids)
    base, remainder = divmod(amount_kop, len(ordered))
    return {uid: base + (1 if i < remainder else 0) for i, uid in enumerate(ordered)}


def split_exact(amount_kop: int, shares: dict[int, int]) -> dict[int, int]:
    """Довільний поділ: кожен учасник має конкретну суму (хто скільки з'їв).

    Сума часток має точно дорівнювати сумі витрати. Нульові частки відкидаються.
    """
    if amount_kop <= 0:
        raise ValueError("Сума має бути більшою за 0")
    if any(v < 0 for v in shares.values()):
        raise ValueError("Частка не може бути від'ємною")
    result = {uid: v for uid, v in sorted(shares.items()) if v > 0}
    if not result:
        raise ValueError("Вкажіть частку хоча б для одного учасника")
    total = sum(result.values())
    if total != amount_kop:
        diff = amount_kop - total
        hint = f"залишилось розподілити {format_kop(diff)}" if diff > 0 else f"перевищено на {format_kop(-diff)}"
        raise ValueError(f"Сума часток {format_kop(total)} не дорівнює сумі витрати {format_kop(amount_kop)}: {hint}")
    return result


def parse_amount(text: str) -> int:
    """Перетворює введений рядок («600», «33,34», «0.5») на копійки."""
    cleaned = text.strip().replace(" ", "").replace(" ", "")
    if not _AMOUNT_RE.match(cleaned):
        raise ValueError("Введіть суму числом, наприклад 250 або 99,90")
    whole, _, frac = cleaned.replace(",", ".").partition(".")
    kop = int(whole) * 100 + int(frac.ljust(2, "0") or 0)
    if kop <= 0:
        raise ValueError("Сума має бути більшою за 0")
    return kop


def format_kop(kop: int) -> str:
    """Форматує копійки для показу: 123456 -> «1 234,56 ₴»."""
    sign = "−" if kop < 0 else ""
    whole, frac = divmod(abs(kop), 100)
    grouped = f"{whole:,}".replace(",", " ")
    return f"{sign}{grouped},{frac:02d} ₴"
