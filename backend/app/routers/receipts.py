from datetime import date
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import crud, schemas
from app.config import settings
from app.db import begin_write
from app.deps import CurrentUser, DbSession, MemberGroup
from app.models import ItemClaim, Operation, OperationShare, Receipt, ReceiptItem
from app.services.images import InvalidImage, inspect_image
from app.services.money import MAX_AMOUNT_KOP, format_kop
from app.services.receipts import split_by_items

router = APIRouter(prefix="/groups/{group_id}/receipts", tags=["Чеки"])

ERRORS = {
    400: {"model": schemas.ErrorOut, "description": "Некоректні дані"},
    403: {"model": schemas.ErrorOut, "description": "Немає прав"},
    404: {"model": schemas.ErrorOut, "description": "Чек не знайдено"},
    409: {"model": schemas.ErrorOut, "description": "Чек уже закрито"},
}


def upload_root() -> Path:
    root = Path(settings.upload_dir) / "receipts"
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_receipt(group_id: int, receipt_id: int, db: Session) -> Receipt:
    receipt = db.get(Receipt, receipt_id)
    if receipt is None or receipt.group_id != group_id:
        raise HTTPException(status_code=404, detail="Чек не знайдено")
    return receipt


def require_open(receipt: Receipt) -> None:
    if receipt.status != "open":
        raise HTTPException(status_code=409, detail="Чек уже закрито — витрату записано")


def require_manager(receipt: Receipt, user_id: int, action: str) -> None:
    if user_id not in (receipt.created_by, receipt.payer_id):
        raise HTTPException(status_code=403, detail=f"{action} може лише автор чека або платник")


@router.get("", response_model=list[schemas.ReceiptOut], summary="Чеки групи")
def list_receipts(group: MemberGroup, db: DbSession, status_filter: str | None = None) -> list[schemas.ReceiptOut]:
    q = select(Receipt).where(Receipt.group_id == group.id).order_by(Receipt.id.desc())
    if status_filter in ("open", "closed"):
        q = q.where(Receipt.status == status_filter)
    return [crud.receipt_out(r) for r in db.scalars(q).all()]


@router.post(
    "",
    response_model=schemas.ReceiptOut,
    status_code=status.HTTP_201_CREATED,
    summary="Створити чек із позиціями",
    responses=ERRORS,
)
def create_receipt(data: schemas.ReceiptCreate, group: MemberGroup, user: CurrentUser, db: DbSession) -> schemas.ReceiptOut:
    if data.payer_id not in crud.member_ids(group):
        raise HTTPException(status_code=400, detail="Платник має бути учасником групи")
    receipt = Receipt(
        group_id=group.id,
        title=data.title,
        category=data.category,
        payer_id=data.payer_id,
        created_by=user.id,
        op_date=data.op_date or date.today(),
        items=[ReceiptItem(name=i.name, price_kop=i.price_kop, position=n) for n, i in enumerate(data.items)],
    )
    db.add(receipt)
    db.commit()
    db.refresh(receipt)
    return crud.receipt_out(receipt)


@router.get("/{receipt_id}", response_model=schemas.ReceiptOut, summary="Чек з позиціями та підсумками", responses=ERRORS)
def read_receipt(receipt_id: int, group: MemberGroup, db: DbSession) -> schemas.ReceiptOut:
    return crud.receipt_out(get_receipt(group.id, receipt_id, db))


@router.patch(
    "/{receipt_id}",
    response_model=schemas.ReceiptOut,
    summary="Змінити платника або назву відкритого чека",
    responses=ERRORS,
)
def update_receipt(
    receipt_id: int, data: schemas.ReceiptUpdate, group: MemberGroup, user: CurrentUser, db: DbSession
) -> schemas.ReceiptOut:
    receipt = get_receipt(group.id, receipt_id, db)
    require_open(receipt)
    require_manager(receipt, user.id, "Змінити чек")
    if data.payer_id is not None:
        if data.payer_id not in crud.member_ids(group):
            raise HTTPException(status_code=400, detail="Платник має бути учасником групи")
        receipt.payer_id = data.payer_id
    if data.title is not None:
        receipt.title = data.title
    db.commit()
    return crud.receipt_out(receipt)


def _save_photo_metadata(db: Session, receipt: Receipt, name: str, content_type: str) -> None:
    """Підтвердити нове фото в БД. Винесено окремо, щоб тест міг змоделювати збій підтвердження."""
    receipt.photo_path, receipt.photo_type = name, content_type
    db.commit()


@router.post("/{receipt_id}/photo", response_model=schemas.ReceiptOut, summary="Додати або замінити фото чека", responses=ERRORS)
async def upload_photo(
    receipt_id: int, file: UploadFile, group: MemberGroup, user: CurrentUser, db: DbSession
) -> schemas.ReceiptOut:
    group_id, user_id = group.id, user.id
    require_manager(get_receipt(group_id, receipt_id, db), user_id, "Додати фото")
    # Перевірка прав завершена: відпускаємо блокування БД на час роботи з файлом (D02/D06)
    db.rollback()

    max_bytes = settings.max_photo_mb * 1024 * 1024
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(status_code=400, detail=f"Фото завелике — максимум {settings.max_photo_mb} МБ")
    try:
        info = inspect_image(data, settings.max_photo_side_px)
    except InvalidImage as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    root = upload_root()
    new_name = f"{uuid4().hex}{info.extension}"
    new_path = root / new_name
    try:
        new_path.write_bytes(data)
    except OSError as e:
        new_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Не вдалося зберегти фото. Попереднє фото не змінено") from e

    try:
        begin_write(db)
        receipt = get_receipt(group_id, receipt_id, db)  # актуальний стан після очікування блокування
        require_manager(receipt, user_id, "Додати фото")
        old_name = receipt.photo_path
        _save_photo_metadata(db, receipt, new_name, info.content_type)
    except HTTPException:
        db.rollback()
        new_path.unlink(missing_ok=True)
        raise
    except Exception as e:
        db.rollback()
        new_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Не вдалося зберегти фото. Попереднє фото не змінено") from e

    if old_name and old_name != new_name:
        (root / old_name).unlink(missing_ok=True)  # старе фото прибираємо лише після підтвердження
    return crud.receipt_out(receipt)


@router.get(
    "/{receipt_id}/photo",
    summary="Фото чека (лише для учасників групи)",
    response_class=FileResponse,
    responses={**ERRORS, 200: {"content": {"image/jpeg": {}, "image/png": {}, "image/webp": {}}}},
)
def get_photo(receipt_id: int, group: MemberGroup, db: DbSession) -> FileResponse:
    receipt = get_receipt(group.id, receipt_id, db)
    path = upload_root() / receipt.photo_path if receipt.photo_path else None
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="Фото не завантажено")
    return FileResponse(path, media_type=receipt.photo_type or "image/jpeg", headers={"Cache-Control": "private, max-age=86400"})


@router.put(
    "/{receipt_id}/claims",
    response_model=schemas.ReceiptOut,
    summary="Зберегти свої позиції («що я замовляв»)",
    responses=ERRORS,
)
def set_my_claims(
    receipt_id: int, data: schemas.ClaimsIn, group: MemberGroup, user: CurrentUser, db: DbSession
) -> schemas.ReceiptOut:
    receipt = get_receipt(group.id, receipt_id, db)
    require_open(receipt)
    wanted = set(data.item_ids)
    if not wanted <= {i.id for i in receipt.items}:
        raise HTTPException(status_code=400, detail="Такої позиції немає в цьому чеку")
    for item in receipt.items:
        mine = next((c for c in item.claims if c.user_id == user.id), None)
        if item.id in wanted and mine is None:
            item.claims.append(ItemClaim(user_id=user.id))
        elif item.id not in wanted and mine is not None:
            item.claims.remove(mine)
    db.commit()
    db.refresh(receipt)
    return crud.receipt_out(receipt)


@router.post(
    "/{receipt_id}/finalize",
    response_model=schemas.OperationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Закрити чек і записати витрату за позиціями",
    responses=ERRORS,
)
def finalize_receipt(receipt_id: int, group: MemberGroup, user: CurrentUser, db: DbSession) -> schemas.OperationOut:
    # Транзакція почалася з BEGIN IMMEDIATE до першого читання, тож стан чека й позначок тут актуальний (D02)
    receipt = get_receipt(group.id, receipt_id, db)
    require_open(receipt)
    require_manager(receipt, user.id, "Закрити чек")
    members = set(crud.member_ids(group))
    spec = crud.receipt_items_spec(receipt)
    total = sum(price for price, _ in spec)
    if total > MAX_AMOUNT_KOP:
        raise HTTPException(status_code=400, detail=f"Сума чека {format_kop(total)} перевищує ліміт однієї витрати")
    try:
        shares = split_by_items(spec)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not set(shares) <= members or receipt.payer_id not in members:
        raise HTTPException(status_code=400, detail="У чеку є людина, яка вже не в групі")

    op = Operation(
        group_id=group.id,
        type="expense",
        split_mode="items",
        amount_kop=total,
        payer_id=receipt.payer_id,
        category=receipt.category,
        description=receipt.title,
        op_date=receipt.op_date,
        created_by=user.id,
        shares=[OperationShare(user_id=uid, share_kop=kop) for uid, kop in shares.items()],
    )
    db.add(op)
    db.flush()
    receipt.status, receipt.operation_id = "closed", op.id
    db.commit()  # витрата, частки й закриття чека — одним комітом
    db.refresh(op)
    return crud.operation_out(op)


@router.delete("/{receipt_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Видалити відкритий чек", responses=ERRORS)
def delete_receipt(receipt_id: int, group: MemberGroup, user: CurrentUser, db: DbSession) -> Response:
    receipt = get_receipt(group.id, receipt_id, db)
    require_open(receipt)
    require_manager(receipt, user.id, "Видалити чек")
    photo = receipt.photo_path
    db.delete(receipt)
    db.commit()
    if photo:
        (upload_root() / photo).unlink(missing_ok=True)  # файл прибираємо лише після видалення запису
    return Response(status_code=status.HTTP_204_NO_CONTENT)

