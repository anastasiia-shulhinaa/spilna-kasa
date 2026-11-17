import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ArrowLeft, CheckCircle2, ImageOff, Maximize2, ReceiptText, RotateCcw, Save, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { Receipt } from "../api/types";
import { Avatar } from "../components/Avatar";
import { PhotoPicker } from "../components/PhotoPicker";
import { invalidateGroupData } from "../components/RepayModal";
import { useToast } from "../components/Toast";
import { Button, Chip, ErrorNote, SectionTitle, Spinner, cn } from "../components/ui";
import { useAuth } from "../hooks/useAuth";
import { dateLabel } from "../lib/categories";
import { formatKop, splitEqual } from "../lib/money";

type NavState = { photoError?: string; photoFile?: File } | null;

const sameSet = (a: number[], b: number[]) => a.length === b.length && a.every((x) => b.includes(x));

export function ReceiptPage() {
  const groupId = Number(useParams().id);
  const receiptId = Number(useParams().rid);
  const { user } = useAuth();
  const qc = useQueryClient();
  const nav = useNavigate();
  const location = useLocation();
  const toast = useToast();
  const key = ["receipt", groupId, receiptId];

  const navState = (location.state as NavState) ?? null;
  const [photoError, setPhotoError] = useState<string | null>(navState?.photoError ?? null);
  const [retryFile, setRetryFile] = useState<File | null>(navState?.photoFile instanceof File ? navState.photoFile : null);
  const [zoom, setZoom] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [draft, setDraft] = useState<number[] | null>(null); // незбережений вибір позицій

  const group = useQuery({ queryKey: ["group", groupId], queryFn: () => api.group(groupId) });
  const receipt = useQuery({ queryKey: key, queryFn: () => api.receipt(groupId, receiptId), refetchInterval: 3000 });
  const version = receipt.data?.photo_version ?? null;
  const photo = useQuery({
    queryKey: ["receipt-photo", groupId, receiptId, version],
    queryFn: () => api.receiptPhoto(groupId, receiptId, version),
    enabled: !!receipt.data?.has_photo,
    staleTime: Infinity,
  });
  const photoUrl = useMemo(() => (photo.data ? URL.createObjectURL(photo.data) : null), [photo.data]);
  useEffect(() => () => void (photoUrl && URL.revokeObjectURL(photoUrl)), [photoUrl]);

  const afterChange = (data: Receipt) => {
    qc.setQueryData(key, data);
    invalidateGroupData(qc, groupId);
  };

  const saveClaims = useMutation({
    mutationFn: (itemIds: number[]) => api.setClaims(groupId, receiptId, itemIds),
    onSuccess: (data) => {
      afterChange(data);
      setDraft(null);
      toast("Ваш вибір збережено");
    },
  });

  const upload = useMutation({
    mutationFn: (file: File) => api.uploadReceiptPhoto(groupId, receiptId, file),
    onSuccess: (data) => {
      afterChange(data);
      setPhotoError(null);
      setRetryFile(null);
      toast(data.has_photo ? "Фото збережено" : "Готово");
    },
    onError: (e, file) => {
      setPhotoError(e.message);
      setRetryFile(file);
    },
  });

  const changePayer = useMutation({
    mutationFn: (payer_id: number) => api.updateReceipt(groupId, receiptId, { payer_id }),
    onSuccess: (data) => {
      afterChange(data);
      toast("Платника змінено");
    },
  });

  const finalize = useMutation({
    mutationFn: () => api.finalizeReceipt(groupId, receiptId),
    onSuccess: () => {
      invalidateGroupData(qc, groupId);
      qc.invalidateQueries({ queryKey: key });
      toast("Чек закрито — витрату записано");
      nav(`/groups/${groupId}?tab=balances`);
    },
  });

  const remove = useMutation({
    mutationFn: () => api.deleteReceipt(groupId, receiptId),
    onSuccess: () => {
      invalidateGroupData(qc, groupId);
      toast("Чек видалено");
      nav(`/groups/${groupId}`, { replace: true });
    },
  });

  if (receipt.isLoading || group.isLoading) return <Spinner />;
  if (receipt.error || group.error) return <ErrorNote>{(receipt.error ?? group.error)?.message}</ErrorNote>;
  const r = receipt.data!;
  const g = group.data!;
  const names = new Map(g.members.map((m) => [m.id, m.display_name]));
  const open = r.status === "open";
  const canManage = user?.id === r.payer_id || user?.id === r.created_by;

  const savedMine = r.items.filter((i) => user && i.claimed_by.includes(user.id)).map((i) => i.id);
  const mySelection = draft ?? savedMine;
  const dirty = draft !== null && !sameSet(draft, savedMine);

  // Підсумки з урахуванням незбереженого вибору — як буде після «Зберегти»
  const withDraft = r.items.map((i) => {
    if (!user) return i.claimed_by;
    const others = i.claimed_by.filter((u) => u !== user.id);
    return mySelection.includes(i.id) ? [...others, user.id].sort((a, b) => a - b) : others;
  });
  const totals = new Map<number, number>();
  let unclaimed = 0;
  r.items.forEach((item, idx) => {
    if (!withDraft[idx].length) unclaimed += item.price_kop;
    for (const [uid, kop] of splitEqual(item.price_kop, withDraft[idx])) totals.set(uid, (totals.get(uid) ?? 0) + kop);
  });
  const myTotal = user ? totals.get(user.id) ?? 0 : 0;
  const savedMyTotal = user ? r.totals.find((t) => t.user_id === user.id)?.share_kop ?? 0 : 0;

  const toggle = (itemId: number) => {
    if (!open) return;
    const base = draft ?? savedMine;
    setDraft(base.includes(itemId) ? base.filter((x) => x !== itemId) : [...base, itemId]);
  };

  return (
    <div className={cn("animate-rise", dirty && "pb-28")}>
      <div className="mb-5 flex items-center gap-3">
        <Link to={`/groups/${groupId}`} aria-label="Назад" className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-white shadow-soft hover:text-rose-600">
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-xl font-extrabold tracking-tight">{r.title}</h1>
          <p className="text-sm text-muted">
            Оплата: {names.get(r.payer_id)} · {dateLabel(r.op_date)} · {formatKop(r.total_kop)}
          </p>
        </div>
      </div>

      {photoError && (
        <div className="mb-4 flex flex-col gap-3 rounded-3xl border border-minus/30 bg-minus/5 p-4" role="alert">
          <p className="flex items-start gap-2 text-sm font-semibold text-minus">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>
              Чек створено. Фото не завантажилось: {photoError}
            </span>
          </p>
          {canManage && (
            <div className="flex flex-wrap items-center gap-3">
              {retryFile && (
                <Button className="px-4 py-2 text-sm" loading={upload.isPending} onClick={() => upload.mutate(retryFile)}>
                  <RotateCcw className="h-4 w-4" /> Спробувати ще раз
                </Button>
              )}
              <span className="text-xs text-muted">або оберіть інше фото кнопками нижче</span>
            </div>
          )}
        </div>
      )}

      <div className="flex gap-3">
        <div className="flex w-32 shrink-0 flex-col gap-2">
          {r.has_photo ? (
            <button onClick={() => setZoom(true)} className="group relative h-40 w-32 overflow-hidden rounded-3xl bg-rose-50 shadow-soft" aria-label="Відкрити фото чека">
              {photoUrl ? <img src={photoUrl} alt="Фото чека" className="h-full w-full object-cover transition group-hover:scale-105" /> : <Spinner className="py-14" />}
              <span className="absolute bottom-2 right-2 grid h-7 w-7 place-items-center rounded-full bg-white/90 text-ink shadow-soft">
                <Maximize2 className="h-3.5 w-3.5" />
              </span>
            </button>
          ) : (
            <div className="grid h-40 w-32 place-items-center rounded-3xl border-2 border-dashed border-rose-200 bg-white/60 text-center text-xs font-semibold text-muted">
              <span className="flex flex-col items-center gap-1 px-2">
                <ImageOff className="h-5 w-5 text-rose-300" /> Фото ще немає
              </span>
            </div>
          )}
        </div>
        <div className="relative flex-1 overflow-hidden rounded-[2rem] bg-gradient-to-br from-rose-500 to-rose-400 p-5 text-white shadow-pop">
          <div className="pointer-events-none absolute -right-8 -top-10 h-32 w-32 rounded-full bg-white/10" />
          <p className="text-sm text-white/80">Ваша частка</p>
          <p className="tabular mt-1 text-3xl font-extrabold">{formatKop(myTotal)}</p>
          {dirty && <p className="tabular text-xs text-white/80">збережено: {formatKop(savedMyTotal)}</p>}
          <p className="mt-2 text-sm text-white/85">
            {!open ? (
              <span className="inline-flex items-center gap-1.5">
                <CheckCircle2 className="h-4 w-4" /> Чек закрито, витрату записано
              </span>
            ) : unclaimed ? (
              <>Не розібрано: {formatKop(unclaimed)}</>
            ) : (
              "Усе розібрано ✨"
            )}
          </p>
        </div>
      </div>

      {canManage && (
        <div className="mt-3">
          <PhotoPicker compact label={r.has_photo ? "замінити фото" : "фото чека"} busy={upload.isPending} onPick={(f) => upload.mutate(f)} />
          {upload.isPending && <p className="mt-2 text-xs text-muted">Завантажуємо фото…</p>}
        </div>
      )}

      {open && canManage && (
        <>
          <SectionTitle>Хто оплатив весь чек</SectionTitle>
          <div className="flex flex-wrap gap-2">
            {g.members.map((m) => (
              <Chip key={m.id} active={r.payer_id === m.id} onClick={() => m.id !== r.payer_id && changePayer.mutate(m.id)} className="pl-1.5">
                <Avatar id={m.id} name={m.display_name} size="sm" /> {m.display_name}
              </Chip>
            ))}
          </div>
          <ErrorNote>{changePayer.error?.message}</ErrorNote>
        </>
      )}

      {open && (
        <p className="mt-5 rounded-2xl bg-white/70 px-4 py-3 text-sm text-muted">
          Торкніться позицій, які <b className="text-ink">ви замовляли</b>, і натисніть <b className="text-ink">«Зберегти мій вибір»</b>. Спільну страву ділимо між усіма, хто її позначив.
        </p>
      )}

      <SectionTitle>Позиції</SectionTitle>
      <ul className="card divide-y divide-line/70 overflow-hidden">
        {r.items.map((item, idx) => {
          const mine = mySelection.includes(item.id);
          const owners = withDraft[idx];
          const n = owners.length;
          const myPart = mine && user ? splitEqual(item.price_kop, owners).get(user.id) : undefined;
          const changed = draft !== null && mine !== savedMine.includes(item.id);
          return (
            <li key={item.id}>
              <button
                type="button"
                disabled={!open}
                onClick={() => toggle(item.id)}
                className={cn("flex w-full items-center gap-3 px-4 py-3.5 text-left transition", open && "hover:bg-rose-50/60", mine && "bg-rose-50")}
              >
                <span className={cn("grid h-6 w-6 shrink-0 place-items-center rounded-lg border-2 transition", mine ? "border-rose-500 bg-rose-500 text-white" : "border-line bg-white")}>
                  {mine && <span className="text-xs font-bold">✓</span>}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-semibold">
                    {item.name}
                    {changed && <span className="ml-2 rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-bold uppercase text-rose-700">не збережено</span>}
                  </p>
                  <div className="mt-1 flex h-6 items-center gap-1.5">
                    {n === 0 ? (
                      <span className="rounded-full bg-minus/10 px-2 py-0.5 text-[11px] font-semibold text-minus">нічиє</span>
                    ) : (
                      <>
                        <div className="flex -space-x-1.5">
                          {owners.map((uid) => (
                            <Avatar key={uid} id={uid} name={names.get(uid) ?? "?"} size="sm" ring />
                          ))}
                        </div>
                        {n > 1 && <span className="text-[11px] font-semibold text-muted">÷ {n}</span>}
                      </>
                    )}
                  </div>
                </div>
                <div className="text-right">
                  <p className="tabular font-bold">{formatKop(item.price_kop)}</p>
                  {myPart !== undefined && n > 1 && <p className="tabular text-[11px] font-semibold text-rose-600">ваші {formatKop(myPart)}</p>}
                </div>
              </button>
            </li>
          );
        })}
      </ul>

      <SectionTitle>Частки учасників</SectionTitle>
      <ul className="card divide-y divide-line/70">
        {g.members.map((m) => {
          const kop = totals.get(m.id) ?? 0;
          const isPayer = m.id === r.payer_id;
          return (
            <li key={m.id} className="flex items-center gap-3 px-4 py-3">
              <Avatar id={m.id} name={m.display_name} size="sm" />
              <span className="flex-1 font-semibold">
                {m.display_name}
                {isPayer && <span className="ml-1.5 text-xs font-medium text-muted">оплатив(-ла) чек</span>}
              </span>
              <span className={cn("tabular font-bold", kop ? "text-ink" : "text-muted/50")}>{formatKop(kop)}</span>
            </li>
          );
        })}
        {unclaimed > 0 && (
          <li className="flex items-center justify-between px-4 py-3 text-sm font-semibold text-minus">
            <span>Ще не розібрано</span>
            <span className="tabular">{formatKop(unclaimed)}</span>
          </li>
        )}
      </ul>

      <div className="mt-6 space-y-3">
        <ErrorNote>{saveClaims.error?.message || finalize.error?.message || remove.error?.message || upload.error?.message}</ErrorNote>
        {open && canManage && (
          <>
            <Button block disabled={unclaimed > 0 || dirty} loading={finalize.isPending} onClick={() => finalize.mutate()}>
              <ReceiptText className="h-4 w-4" />
              {dirty ? "Спершу збережіть свій вибір" : unclaimed > 0 ? "Закрити чек можна, коли все розібрано" : "Закрити чек і записати витрату"}
            </Button>
            {confirmDelete ? (
              <div className="flex gap-2">
                <Button variant="outline" block onClick={() => setConfirmDelete(false)}>
                  Скасувати
                </Button>
                <Button variant="soft" block className="!bg-minus/10 !text-minus" loading={remove.isPending} onClick={() => remove.mutate()}>
                  Так, видалити
                </Button>
              </div>
            ) : (
              <Button variant="ghost" block onClick={() => setConfirmDelete(true)}>
                <Trash2 className="h-4 w-4" /> Видалити чек
              </Button>
            )}
          </>
        )}
        {open && !canManage && (
          <p className="text-center text-xs text-muted">Коли всі збережуть свій вибір, {names.get(r.payer_id)} закриє чек, і борги порахуються автоматично.</p>
        )}
      </div>

      {dirty &&
        createPortal(
          <div className="fixed inset-x-0 bottom-0 z-40 border-t border-line bg-white/95 px-4 pb-[calc(env(safe-area-inset-bottom)+5.5rem)] pt-3 shadow-soft backdrop-blur sm:pb-[calc(env(safe-area-inset-bottom)+1rem)]">
            <div className="mx-auto flex max-w-xl items-center gap-2">
              <Button variant="outline" className="px-4" onClick={() => setDraft(null)} disabled={saveClaims.isPending}>
                Скасувати
              </Button>
              <Button className="flex-1" loading={saveClaims.isPending} onClick={() => saveClaims.mutate(mySelection)}>
                <Save className="h-4 w-4" /> Зберегти мій вибір · {formatKop(myTotal)}
              </Button>
            </div>
          </div>,
          document.body,
        )}

      {zoom &&
        photoUrl &&
        createPortal(
          <button className="fixed inset-0 z-50 grid place-items-center bg-ink/80 p-4 backdrop-blur-sm" onClick={() => setZoom(false)} aria-label="Закрити фото">
            <img src={photoUrl} alt="Фото чека" className="max-h-full max-w-full rounded-2xl shadow-soft" />
          </button>,
          document.body,
        )}
    </div>
  );
}
