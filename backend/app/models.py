from datetime import date, datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
    and_,
)
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    memberships: Mapped[list["Membership"]] = relationship(back_populates="user")


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    emoji: Mapped[str] = mapped_column(String(16), default="💗")
    currency: Mapped[str] = mapped_column(String(3), default="UAH")
    invite_code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="group", cascade="all, delete-orphan", order_by="Membership.id"
    )
    operations: Mapped[list["Operation"]] = relationship(back_populates="group", cascade="all, delete-orphan")


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("group_id", "user_id", name="uq_membership"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(10), default="member")  # owner | member
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    group: Mapped[Group] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="memberships")


class Operation(Base):
    """Фінансова операція групи: витрата (expense) або переказ між учасниками (transfer)."""

    __tablename__ = "operations"
    __table_args__ = (
        CheckConstraint("amount_kop > 0", name="ck_amount_positive"),
        CheckConstraint("type IN ('expense', 'transfer')", name="ck_operation_type"),
        # Батьківський ключ для складеного FK з чеків: чек може посилатися лише на операцію своєї групи (D01)
        UniqueConstraint("group_id", "id", name="uq_operation_group_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(10))
    split_mode: Mapped[str] = mapped_column(String(10), default="equal")  # equal | exact | items
    amount_kop: Mapped[int] = mapped_column(Integer)
    payer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    recipient_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    description: Mapped[str] = mapped_column(String(200), default="")
    op_date: Mapped[date] = mapped_column(Date)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    group: Mapped[Group] = relationship(back_populates="operations")
    shares: Mapped[list["OperationShare"]] = relationship(
        back_populates="operation", cascade="all, delete-orphan", order_by="OperationShare.user_id"
    )
    receipt: Mapped["Receipt | None"] = relationship(
        primaryjoin=lambda: and_(foreign(Receipt.operation_id) == Operation.id, Receipt.group_id == Operation.group_id),
        uselist=False,
        viewonly=True,
    )


class OperationShare(Base):
    __tablename__ = "operation_shares"
    __table_args__ = (CheckConstraint("share_kop >= 0", name="ck_share_non_negative"),)

    operation_id: Mapped[int] = mapped_column(ForeignKey("operations.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    share_kop: Mapped[int] = mapped_column(Integer)

    operation: Mapped[Operation] = relationship(back_populates="shares")


class Receipt(Base):
    """Чек: платник вносить позиції (і фото), кожен учасник позначає, що замовляв.
    Після закриття чек перетворюється на витрату з частками за позиціями."""

    __tablename__ = "receipts"
    __table_args__ = (
        CheckConstraint("status IN ('open', 'closed')", name="ck_receipt_status"),
        # Відкритий чек не має операції, закритий — обов'язково має (D01)
        CheckConstraint(
            "(status = 'open' AND operation_id IS NULL) OR (status = 'closed' AND operation_id IS NOT NULL)",
            name="ck_receipt_status_operation",
        ),
        # Одна операція — щонайбільше один чек
        UniqueConstraint("operation_id", name="uq_receipt_operation"),
        # Операція з тієї самої групи. NO ACTION + відкладена перевірка: API спершу відкриває чек
        # і відв'язує операцію, а потім видаляє її в тій самій транзакції.
        ForeignKeyConstraint(
            ["group_id", "operation_id"],
            ["operations.group_id", "operations.id"],
            name="fk_receipt_operation_same_group",
            deferrable=True,
            initially="DEFERRED",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(40), default="Розваги")
    payer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(10), default="open")
    photo_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    photo_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    operation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    op_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    items: Mapped[list["ReceiptItem"]] = relationship(
        back_populates="receipt", cascade="all, delete-orphan", order_by="ReceiptItem.position"
    )
    operation: Mapped[Operation | None] = relationship(
        primaryjoin=lambda: and_(foreign(Receipt.operation_id) == Operation.id, Receipt.group_id == Operation.group_id),
        viewonly=True,
    )


class ReceiptItem(Base):
    __tablename__ = "receipt_items"
    __table_args__ = (CheckConstraint("price_kop > 0", name="ck_item_price_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    receipt_id: Mapped[int] = mapped_column(ForeignKey("receipts.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    price_kop: Mapped[int] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer, default=0)

    receipt: Mapped[Receipt] = relationship(back_populates="items")
    claims: Mapped[list["ItemClaim"]] = relationship(
        back_populates="item", cascade="all, delete-orphan", order_by="ItemClaim.user_id"
    )


class ItemClaim(Base):
    """Учасник позначив позицію чека як свою. Спільну позицію ділять порівну між усіма, хто її позначив."""

    __tablename__ = "item_claims"

    item_id: Mapped[int] = mapped_column(ForeignKey("receipt_items.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)

    item: Mapped[ReceiptItem] = relationship(back_populates="claims")
