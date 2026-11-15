"""Демо-дані для показу. Запуск: python -m app.seed  (УВАГА: очищає базу)."""

import shutil
from datetime import date, timedelta
from pathlib import Path

from app.db import Base, SessionLocal, create_schema, engine
from app.models import Group, ItemClaim, Membership, Operation, OperationShare, Receipt, ReceiptItem, User
from app.routers.receipts import upload_root
from app.security import hash_password
from app.services.money import split_equal

DEMO_PHOTO = Path(__file__).parent / "demo_assets" / "receipt_demo.png"

PASSWORD = "demo1234"
PEOPLE = [
    ("ivanna@demo.ua", "Іванна"),
    ("sofia@demo.ua", "Софія"),
    ("maryna@demo.ua", "Марина"),
    ("viktoria@demo.ua", "Вікторія"),
    ("anastasiia@demo.ua", "Анастасія"),
]


def run() -> None:
    from app import models  # noqa: F401

    Base.metadata.drop_all(bind=engine)
    create_schema(engine)

    with SessionLocal() as db:
        pw = hash_password(PASSWORD)
        users = {name: User(email=email, display_name=name, password_hash=pw) for email, name in PEOPLE}
        db.add_all(users.values())
        db.flush()

        # Група для живого демо: без операцій — 600 грн вносимо наживо
        flat = Group(name="Квартира", emoji="🏠", invite_code="KASA26", created_by=users["Іванна"].id)
        flat.memberships = [
            Membership(user_id=users["Іванна"].id, role="owner"),
            Membership(user_id=users["Софія"].id),
            Membership(user_id=users["Марина"].id),
        ]

        # Група з історією — для гарної картинки
        trip = Group(name="Карпати 2026", emoji="🏔️", invite_code="KARP26", created_by=users["Вікторія"].id)
        trip.memberships = [Membership(user_id=users["Вікторія"].id, role="owner")] + [
            Membership(user_id=users[n].id) for n in ("Анастасія", "Іванна", "Софія", "Марина")
        ]
        db.add_all([flat, trip])
        db.flush()

        everyone = [users[n].id for n in ("Вікторія", "Анастасія", "Іванна", "Софія", "Марина")]
        today = date.today()

        def expense(payer: str, amount_kop: int, category: str, text: str, ids: list[int], days_ago: int):
            shares = split_equal(amount_kop, ids)
            return Operation(
                group_id=trip.id,
                type="expense",
                amount_kop=amount_kop,
                payer_id=users[payer].id,
                category=category,
                description=text,
                op_date=today - timedelta(days=days_ago),
                created_by=users[payer].id,
                shares=[OperationShare(user_id=u, share_kop=k) for u, k in shares.items()],
            )

        db.add_all(
            [
                expense("Вікторія", 480000, "Житло", "Будиночок у Яремчі", everyone, 6),
                expense("Марина", 125000, "Транспорт", "Квитки на потяг", everyone, 6),
                expense("Іванна", 90050, "Продукти", "Продукти на два дні", everyone[:4], 5),
                expense("Марина", 36000, "Розваги", "Канатна дорога", [users["Марина"].id, users["Софія"].id], 4),
                Operation(
                    group_id=trip.id,
                    type="transfer",
                    amount_kop=50000,
                    payer_id=users["Софія"].id,
                    recipient_id=users["Вікторія"].id,
                    description="Повернення боргу",
                    op_date=today - timedelta(days=2),
                    created_by=users["Софія"].id,
                ),
            ]
        )
        # Відкритий чек із ресторану: Іванна й Марина вже позначили свої страви,
        # Анастасія позначає свої наживо на демо → виходить 600 / 300 / 600.
        photo = upload_root() / "demo_receipt.png"
        shutil.copyfile(DEMO_PHOTO, photo)
        items = [
            ("Банош з бринзою", 28000, ["Марина"]),
            ("Бограч", 32000, ["Іванна"]),
            ("Деруни зі сметаною", 19000, ["Іванна"]),
            ("Вареники з картоплею", 16000, []),
            ("Сирна тарілка", 27000, ["Іванна", "Марина"]),
            ("Пляцок гуцульський", 13000, ["Марина"]),
            ("Глінтвейн", 10000, ["Марина"]),
            ("Чай трав'яний", 5000, []),
        ]
        db.add(
            Receipt(
                group_id=trip.id,
                title="Колиба «Смерековий дим»",
                category="Розваги",
                payer_id=users["Марина"].id,
                created_by=users["Марина"].id,
                photo_path=photo.name,
                photo_type="image/png",
                op_date=today - timedelta(days=1),
                items=[
                    ReceiptItem(
                        name=name,
                        price_kop=price,
                        position=n,
                        claims=[ItemClaim(user_id=users[who].id) for who in owners],
                    )
                    for n, (name, price, owners) in enumerate(items)
                ],
            )
        )
        db.commit()

    print("Демо-дані створено. Пароль для всіх акаунтів:", PASSWORD)
    for email, name in PEOPLE:
        print(f"  {name:<10} {email}")
    print("Коди запрошення: Квартира — KASA26, Карпати 2026 — KARP26")
    print(f"Фото демо-чека для завантаження вручну: {DEMO_PHOTO}")


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")  # кирилиця в консолі Windows
    run()
