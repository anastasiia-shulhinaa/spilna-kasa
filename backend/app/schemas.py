from datetime import date as Date
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator, model_validator

from app.services.money import MAX_AMOUNT_KOP, format_kop

CATEGORIES = ("Продукти", "Житло", "Транспорт", "Розваги", "Здоров'я", "Інше")


def Text(max_length: int) -> type[str]:
    """Рядок, у якого пробіли обрізаються ДО перевірки довжини: «   » → порожній → 422 (D03)."""
    return Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=max_length)]



# ---------- Користувачі ----------
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128, examples=["demo1234"])
    display_name: Text(80) = Field(examples=["Іванна"])


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    display_name: str


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str


class UserUpdate(BaseModel):
    display_name: Text(80)


# ---------- Групи ----------
class GroupCreate(BaseModel):
    name: Text(80) = Field(examples=["Квартира"])
    emoji: str = Field(default="💗", max_length=16, examples=["🏠"])


class JoinIn(BaseModel):
    invite_code: str = Field(min_length=4, max_length=16, examples=["K7M2QX"])


class MemberOut(BaseModel):
    id: int
    display_name: str
    role: str


class GroupSummary(BaseModel):
    id: int
    name: str
    emoji: str
    currency: str
    members: list[MemberOut]
    my_balance_kop: int


class GroupDetail(GroupSummary):
    invite_code: str
    total_expenses_kop: int


# ---------- Операції ----------
def _check_category(v: str) -> str:
    if v not in CATEGORIES:
        raise ValueError(f"Невідома категорія. Доступні: {', '.join(CATEGORIES)}")
    return v


class ShareIn(BaseModel):
    user_id: int
    share_kop: int = Field(ge=0, le=MAX_AMOUNT_KOP, description="Частка в копійках")


class ExpenseCreate(BaseModel):
    amount_kop: int = Field(gt=0, le=MAX_AMOUNT_KOP, description="Сума в копійках", examples=[150000])
    payer_id: int
    split_mode: Literal["equal", "exact"] = Field(
        default="equal", description="equal — порівну між participant_ids; exact — точні суми в shares"
    )
    participant_ids: list[int] = Field(default_factory=list, description="Між ким ділимо порівну (equal)")
    shares: list[ShareIn] = Field(default_factory=list, description="Хто скільки винен (exact)")
    category: str = Field(default="Інше", examples=["Розваги"])
    description: str = Field(default="", max_length=200, examples=["Ресторан"])
    op_date: Date | None = None

    _category = field_validator("category")(_check_category)

    @model_validator(mode="after")
    def check_mode(self) -> "ExpenseCreate":
        if self.split_mode == "equal" and not self.participant_ids:
            raise ValueError("Оберіть хоча б одного учасника поділу")
        if self.split_mode == "exact" and not self.shares:
            raise ValueError("Вкажіть, хто скільки винен")
        return self


class TransferCreate(BaseModel):
    from_user_id: int = Field(description="Хто повертає гроші")
    to_user_id: int = Field(description="Кому повертають")
    amount_kop: int = Field(gt=0, le=MAX_AMOUNT_KOP, examples=[20000])
    op_date: Date | None = None


class ShareOut(BaseModel):
    user_id: int
    share_kop: int


class OperationOut(BaseModel):
    id: int
    type: Literal["expense", "transfer"]
    split_mode: Literal["equal", "exact", "items"]
    created_by: int
    receipt_id: int | None
    amount_kop: int
    payer_id: int
    recipient_id: int | None
    category: str | None
    description: str
    op_date: Date
    created_at: datetime
    shares: list[ShareOut]


# ---------- Баланси ----------
class MemberBalance(BaseModel):
    user: UserPublic
    balance_kop: int


class DebtOut(BaseModel):
    from_user: UserPublic
    to_user: UserPublic
    amount_kop: int


class BalancesOut(BaseModel):
    members: list[MemberBalance]
    debts: list[DebtOut]
    debts_optimal: bool = Field(description="true — кількість переказів доведено мінімальна")
    total_expenses_kop: int


class ErrorOut(BaseModel):
    detail: str


# ---------- Чеки ----------
class ReceiptItemIn(BaseModel):
    name: Text(120) = Field(examples=["Бограч"])
    price_kop: int = Field(gt=0, le=MAX_AMOUNT_KOP, examples=[32000])


class ReceiptCreate(BaseModel):
    title: Text(120) = Field(examples=["Ресторан «Гуцульська хата»"])
    payer_id: int
    category: str = Field(default="Розваги")
    items: list[ReceiptItemIn] = Field(min_length=1, max_length=60)
    op_date: Date | None = None

    _category = field_validator("category")(_check_category)

    @model_validator(mode="after")
    def total_within_limit(self) -> "ReceiptCreate":
        total = sum(i.price_kop for i in self.items)
        if total > MAX_AMOUNT_KOP:
            raise ValueError(f"Загальна сума чека {format_kop(total)} перевищує ліміт {format_kop(MAX_AMOUNT_KOP)}")
        return self


class ReceiptUpdate(BaseModel):
    payer_id: int | None = Field(default=None, description="Хто оплатив весь чек")
    title: Text(120) | None = None


class ClaimsIn(BaseModel):
    item_ids: list[int] = Field(description="Позиції, які поточний користувач позначає як свої (повна заміна)")


class ReceiptItemOut(BaseModel):
    id: int
    name: str
    price_kop: int
    claimed_by: list[int]


class ReceiptOut(BaseModel):
    id: int
    group_id: int
    title: str
    category: str
    payer_id: int
    created_by: int
    status: Literal["open", "closed"]
    has_photo: bool
    photo_version: str | None = Field(description="Змінюється після кожної заміни фото — для оновлення кешу клієнта")
    operation_id: int | None
    op_date: Date
    created_at: datetime
    items: list[ReceiptItemOut]
    total_kop: int
    unclaimed_kop: int
    totals: list[ShareOut] = Field(description="Скільки вже припадає на кожного учасника")


# ---------- Мої борги та історія ----------
class GroupRef(BaseModel):
    id: int
    name: str
    emoji: str


class DebtInGroup(BaseModel):
    group: GroupRef
    amount_kop: int


class CounterpartDebt(BaseModel):
    user: UserPublic
    total_kop: int
    groups: list[DebtInGroup]


class MyDebtsOut(BaseModel):
    owed_to_me: list[CounterpartDebt] = Field(description="Хто мені скільки винен зараз")
    i_owe: list[CounterpartDebt] = Field(description="Кому я винен зараз")
    owed_to_me_total_kop: int
    i_owe_total_kop: int


class HistoryItem(BaseModel):
    id: int
    group: GroupRef
    type: Literal["expense", "transfer"]
    split_mode: Literal["equal", "exact", "items"]
    amount_kop: int
    payer: UserPublic
    recipient: UserPublic | None
    category: str | None
    description: str
    op_date: Date
    created_at: datetime
    receipt_id: int | None
    my_share_kop: int | None = Field(description="Моя частка у витраті, якщо я в ній беру участь")
