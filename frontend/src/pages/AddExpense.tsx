import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Plus, Trash2, X } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { CATEGORIES, type Category, type Member } from "../api/types";
import { Avatar } from "../components/Avatar";
import { PhotoPicker } from "../components/PhotoPicker";
import { invalidateGroupData } from "../components/RepayModal";
import { useToast } from "../components/Toast";
import { Button, Chip, ErrorNote, SectionTitle, SegmentedControl, Spinner, cn } from "../components/ui";
import { useAuth } from "../hooks/useAuth";
import { CATEGORY_ICONS, todayIso } from "../lib/categories";
import { formatKop, kopToInput, parseAmount, parseShare, splitEqual } from "../lib/money";

type Mode = "equal" | "exact" | "items";
interface ItemRow {
  key: number;
  name: string;
  price: string;
}

let rowKey = 1;
const newRow = (): ItemRow => ({ key: rowKey++, name: "", price: "" });

export function AddExpensePage() {
  const groupId = Number(useParams().id);
  const [params] = useSearchParams();
  const { user } = useAuth();
  const nav = useNavigate();
  const qc = useQueryClient();
  const toast = useToast();
  const group = useQuery({ queryKey: ["group", groupId], queryFn: () => api.group(groupId) });

  const [mode, setMode] = useState<Mode>(() => (["equal", "exact", "items"].includes(params.get("mode") ?? "") ? (params.get("mode") as Mode) : "equal"));
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<Category>("Продукти");
  const [payerId, setPayerId] = useState<number | null>(null);
  const [participants, setParticipants] = useState<number[]>([]);
  const [exact, setExact] = useState<Record<number, string>>({});
  const [items, setItems] = useState<ItemRow[]>(() => [newRow(), newRow()]);
  const [photo, setPhoto] = useState<File | null>(null);
  const [date, setDate] = useState(todayIso());
  const [touched, setTouched] = useState(false);

  useEffect(() => {
    if (group.data && payerId === null) {
      setPayerId(user?.id ?? group.data.members[0].id);
      setParticipants(group.data.members.map((m) => m.id));
    }
  }, [group.data, user, payerId]);

  useEffect(() => {
    if (mode === "items" && category === "Продукти") setCategory("Розваги");
    setTouched(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  const members: Member[] = group.data?.members ?? [];
  const amountKop = parseAmount(amount);

  // --- порівну
  const equalShares = useMemo(() => (amountKop ? splitEqual(amountKop, participants) : new Map<number, number>()), [amountKop, participants]);

  // --- точні суми
  const exactParsed = members.map((m) => [m.id, parseShare(exact[m.id] ?? "")] as const);
  const exactInvalid = exactParsed.some(([, v]) => v === null);
  const exactSum = exactParsed.reduce((s, [, v]) => s + (v ?? 0), 0);
  const remaining = (amountKop ?? 0) - exactSum;

  // --- чек
  const itemsParsed = items.map((r) => ({ name: r.name.trim(), price: r.price.trim() ? parseAmount(r.price) : null, blank: !r.name.trim() && !r.price.trim() }));
  const filledItems = itemsParsed.filter((i) => !i.blank);
  const itemsInvalid = filledItems.some((i) => !i.name || i.price === null);
  const itemsTotal = filledItems.reduce((s, i) => s + (i.price ?? 0), 0);

  const invalidate = () => invalidateGroupData(qc, groupId);

  const saveExpense = useMutation({
    mutationFn: () =>
      api.addExpense(groupId, {
        amount_kop: amountKop!,
        payer_id: payerId!,
        category,
        description: description.trim(),
        op_date: date,
        ...(mode === "exact"
          ? { split_mode: "exact" as const, shares: exactParsed.filter(([, v]) => (v ?? 0) > 0).map(([user_id, v]) => ({ user_id, share_kop: v! })) }
          : { split_mode: "equal" as const, participant_ids: participants }),
      }),
    onSuccess: () => {
      invalidate();
      toast("Витрату додано");
      nav(`/groups/${groupId}`);
    },
  });

  const saveReceipt = useMutation({
    mutationFn: async () => {
      const receipt = await api.createReceipt(groupId, {
        title: description.trim(),
        payer_id: payerId!,
        category,
        op_date: date,
        items: filledItems.map((i) => ({ name: i.name, price_kop: i.price! })),
      });
      // Чек уже збережено. Помилка фото не скасовує створення й не дає записати дубль (D05)
      let photoError: string | undefined;
      if (photo) {
        try {
          await api.uploadReceiptPhoto(groupId, receipt.id, photo);
        } catch (e) {
          photoError = e instanceof Error ? e.message : "невідома помилка";
        }
      }
      return { receipt, photoError };
    },
    onSuccess: ({ receipt, photoError }) => {
      invalidate();
      toast(photoError ? "Чек створено. Фото не завантажилось" : "Чек створено — тепер кожен позначає свої позиції");
      nav(`/groups/${groupId}/receipts/${receipt.id}`, { replace: true, state: photoError ? { photoError, photoFile: photo } : null });
    },
  });

  if (group.isLoading) return <Spinner />;
  if (group.error) return <ErrorNote>{group.error.message}</ErrorNote>;
  const g = group.data!;

  const localError = (() => {
    if (mode === "items") {
      if (!description.trim()) return "Вкажіть назву закладу або чека";
      if (filledItems.length === 0) return "Додайте хоча б одну позицію з ціною";
      if (itemsInvalid) return "У кожної позиції мають бути назва й ціна більша за 0";
      return null;
    }
    if (amount && amountKop === null) return "Введіть суму числом, наприклад 250 або 99,90";
    if (!amountKop) return "Введіть суму";
    if (mode === "equal") return participants.length === 0 ? "Оберіть хоча б одного учасника поділу" : null;
    if (exactInvalid) return "Перевірте суми учасників — лише числа, наприклад 600 або 99,90";
    if (remaining > 0) return `Залишилось розподілити ${formatKop(remaining)}`;
    if (remaining < 0) return `Частки перевищують суму на ${formatKop(-remaining)}`;
    return null;
  })();

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setTouched(true);
    if (localError || !payerId) return;
    if (mode === "items") saveReceipt.mutate();
    else saveExpense.mutate();
  };

  const pending = saveExpense.isPending || saveReceipt.isPending;
  const serverError = saveExpense.error?.message || saveReceipt.error?.message;

  return (
    <form onSubmit={submit} className="animate-rise">
      <div className="mb-4 flex items-center gap-3">
        <Link to={`/groups/${groupId}`} aria-label="Назад" className="grid h-10 w-10 place-items-center rounded-full bg-white shadow-soft hover:text-rose-600">
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div>
          <h1 className="text-xl font-extrabold tracking-tight">{mode === "items" ? "Новий чек" : "Нова витрата"}</h1>
          <p className="text-sm text-muted">
            {g.emoji} {g.name}
          </p>
        </div>
      </div>

      <div className="mb-4">
        <SegmentedControl<Mode>
          value={mode}
          onChange={setMode}
          options={[
            { value: "equal", label: "Порівну" },
            { value: "exact", label: "Точні суми" },
            { value: "items", label: "За чеком" },
          ]}
        />
      </div>

      <div className="card px-6 py-7 text-center">
        <span className="text-xs font-semibold uppercase tracking-wider text-muted">{mode === "items" ? "Разом за чеком" : "Сума"}</span>
        {mode === "items" ? (
          <p className={cn("tabular mt-2 text-5xl font-extrabold tracking-tight", itemsTotal ? "text-ink" : "text-rose-200")}>{formatKop(itemsTotal)}</p>
        ) : (
          <div className="mt-2 flex items-baseline justify-center gap-2">
            <input
              id="amount"
              autoFocus
              inputMode="decimal"
              autoComplete="off"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="0,00"
              style={{ width: `${Math.max(4, (amount || "0,00").length) + 0.6}ch` }}
              className="tabular min-w-0 max-w-full bg-transparent text-center text-5xl font-extrabold tracking-tight text-ink outline-none placeholder:text-rose-200"
            />
            <span className="text-3xl font-bold text-rose-400">₴</span>
          </div>
        )}
        <input
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          maxLength={mode === "items" ? 120 : 200}
          placeholder={mode === "items" ? "Заклад, наприклад колиба «Смерековий дим»" : "За що? Наприклад, ресторан"}
          className="mt-5 w-full rounded-full bg-blush px-5 py-3 text-center text-sm outline-none placeholder:text-muted/80 focus:ring-4 focus:ring-rose-100"
        />
      </div>

      <SectionTitle>Категорія</SectionTitle>
      <div className="flex flex-wrap gap-2">
        {CATEGORIES.map((c) => {
          const Icon = CATEGORY_ICONS[c];
          return (
            <Chip key={c} active={category === c} onClick={() => setCategory(c)}>
              <Icon className="h-4 w-4" /> {c}
            </Chip>
          );
        })}
      </div>

      <SectionTitle>{mode === "items" ? "Хто оплатив весь чек" : "Хто платив"}</SectionTitle>
      <div className="flex flex-wrap gap-2">
        {members.map((m) => (
          <Chip key={m.id} active={payerId === m.id} onClick={() => setPayerId(m.id)} className="pl-1.5">
            <Avatar id={m.id} name={m.display_name} size="sm" /> {m.display_name}
          </Chip>
        ))}
      </div>

      {mode === "equal" && (
        <EqualSection members={members} participants={participants} setParticipants={setParticipants} shares={equalShares} amountKop={amountKop} />
      )}
      {mode === "exact" && (
        <ExactSection
          members={members}
          exact={exact}
          setExact={setExact}
          remaining={remaining}
          amountKop={amountKop}
          payerId={payerId}
          exactInvalid={exactInvalid}
        />
      )}
      {mode === "items" && <ItemsSection items={items} setItems={setItems} photo={photo} setPhoto={setPhoto} parsed={itemsParsed} />}

      <SectionTitle>Дата</SectionTitle>
      <input type="date" value={date} max={todayIso()} onChange={(e) => setDate(e.target.value)} className="field" />

      <div className="mt-6 space-y-3">
        <ErrorNote>{(touched && localError) || serverError}</ErrorNote>
        <Button type="submit" block loading={pending}>
          {mode === "items" ? "Створити чек і запросити позначити своє" : "Додати витрату"}
        </Button>
      </div>
    </form>
  );
}

function EqualSection({
  members,
  participants,
  setParticipants,
  shares,
  amountKop,
}: {
  members: Member[];
  participants: number[];
  setParticipants: (fn: (p: number[]) => number[]) => void;
  shares: Map<number, number>;
  amountKop: number | null;
}) {
  const allSelected = participants.length === members.length;
  const values = [...shares.values()];
  const unique = [...new Set(values)].sort((a, b) => b - a);
  const toggle = (id: number) => setParticipants((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));

  return (
    <>
      <SectionTitle
        action={
          <button type="button" className="text-xs font-semibold text-rose-600 hover:underline" onClick={() => setParticipants(() => (allSelected ? [] : members.map((m) => m.id)))}>
            {allSelected ? "Зняти всіх" : "Обрати всіх"}
          </button>
        }
      >
        Ділимо порівну між
      </SectionTitle>
      <ul className="card divide-y divide-line/70">
        {members.map((m) => {
          const on = participants.includes(m.id);
          return (
            <li key={m.id}>
              <button type="button" onClick={() => toggle(m.id)} className="flex w-full items-center gap-3 px-4 py-3 text-left">
                <span className={cn("grid h-6 w-6 place-items-center rounded-lg border-2 transition", on ? "border-rose-500 bg-rose-500 text-white" : "border-line")}>
                  {on && <span className="text-xs font-bold">✓</span>}
                </span>
                <Avatar id={m.id} name={m.display_name} size="sm" />
                <span className="flex-1 font-semibold">{m.display_name}</span>
                <span className={cn("tabular text-sm font-semibold", on ? "text-ink" : "text-muted/50")}>{on && shares.has(m.id) ? formatKop(shares.get(m.id)!) : "—"}</span>
              </button>
            </li>
          );
        })}
      </ul>
      {amountKop && participants.length > 0 && (
        <div className="mt-4 rounded-2xl bg-rose-100/70 px-4 py-3 text-center text-sm font-semibold text-rose-700">
          {unique.length === 1
            ? `По ${formatKop(unique[0])} кожному`
            : `${formatKop(unique[0])} × ${values.filter((v) => v === unique[0]).length}, ${formatKop(unique[1])} × ${values.filter((v) => v === unique[1]).length} — жодна копійка не губиться`}
        </div>
      )}
    </>
  );
}

function ExactSection({
  members,
  exact,
  setExact,
  remaining,
  amountKop,
  payerId,
  exactInvalid,
}: {
  members: Member[];
  exact: Record<number, string>;
  setExact: (fn: (e: Record<number, string>) => Record<number, string>) => void;
  remaining: number;
  amountKop: number | null;
  payerId: number | null;
  exactInvalid: boolean;
}) {
  const fillEqual = () => {
    if (!amountKop) return;
    const shares = splitEqual(amountKop, members.map((m) => m.id));
    setExact(() => Object.fromEntries([...shares].map(([id, kop]) => [id, kopToInput(kop)])));
  };
  const restToPayer = () => {
    if (!payerId || remaining <= 0) return;
    setExact((e) => ({ ...e, [payerId]: kopToInput((parseShare(e[payerId] ?? "") ?? 0) + remaining) }));
  };

  const done = amountKop !== null && remaining === 0 && !exactInvalid;

  return (
    <>
      <SectionTitle
        action={
          <button type="button" className="text-xs font-semibold text-rose-600 hover:underline disabled:opacity-40" disabled={!amountKop} onClick={fillEqual}>
            Заповнити порівну
          </button>
        }
      >
        Хто скільки винен
      </SectionTitle>
      <ul className="card divide-y divide-line/70">
        {members.map((m) => {
          const bad = parseShare(exact[m.id] ?? "") === null;
          return (
            <li key={m.id} className="flex items-center gap-3 px-4 py-2.5">
              <Avatar id={m.id} name={m.display_name} size="sm" />
              <span className="flex-1 font-semibold">
                {m.display_name}
                {m.id === payerId && <span className="ml-1.5 text-xs font-medium text-muted">платить</span>}
              </span>
              <div className={cn("flex items-center gap-1 rounded-xl border bg-blush px-3 py-2 focus-within:border-rose-400 focus-within:ring-4 focus-within:ring-rose-100", bad ? "border-minus" : "border-transparent")}>
                <input
                  inputMode="decimal"
                  aria-label={`Частка: ${m.display_name}`}
                  value={exact[m.id] ?? ""}
                  onChange={(e) => setExact((x) => ({ ...x, [m.id]: e.target.value }))}
                  placeholder="0"
                  className="tabular w-20 bg-transparent text-right font-semibold outline-none placeholder:text-muted/50"
                />
                <span className="text-sm text-muted">₴</span>
              </div>
            </li>
          );
        })}
      </ul>
      <div
        className={cn(
          "mt-4 flex items-center justify-between gap-3 rounded-2xl px-4 py-3 text-sm font-semibold",
          done ? "bg-plus/10 text-plus" : remaining < 0 ? "bg-minus/10 text-minus" : "bg-rose-100/70 text-rose-700",
        )}
      >
        <span className="tabular">
          {!amountKop
            ? "Спершу введіть загальну суму"
            : done
              ? `Розподілено все: ${formatKop(amountKop)} ✓`
              : remaining > 0
                ? `Залишилось розподілити ${formatKop(remaining)}`
                : `Перевищено на ${formatKop(-remaining)}`}
        </span>
        {amountKop && remaining > 0 && payerId && (
          <button type="button" onClick={restToPayer} className="shrink-0 rounded-full bg-white px-3 py-1.5 text-xs font-bold text-rose-600 shadow-soft hover:bg-rose-50">
            Решту — платнику
          </button>
        )}
      </div>
    </>
  );
}

function ItemsSection({
  items,
  setItems,
  photo,
  setPhoto,
  parsed,
}: {
  items: ItemRow[];
  setItems: (fn: (r: ItemRow[]) => ItemRow[]) => void;
  photo: File | null;
  setPhoto: (f: File | null) => void;
  parsed: { name: string; price: number | null; blank: boolean }[];
}) {
  const preview = useMemo(() => (photo ? URL.createObjectURL(photo) : null), [photo]);
  useEffect(() => () => void (preview && URL.revokeObjectURL(preview)), [preview]);

  const update = (key: number, patch: Partial<ItemRow>) => setItems((rows) => rows.map((r) => (r.key === key ? { ...r, ...patch } : r)));

  return (
    <>
      <SectionTitle>Фото чека</SectionTitle>
      {preview ? (
        <div className="card relative flex items-center gap-4 p-3">
          <img src={preview} alt="Фото чека" className="h-24 w-20 rounded-2xl object-cover" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold">{photo!.name}</p>
            <p className="text-xs text-muted">{(photo!.size / 1024 / 1024).toFixed(1)} МБ · побачать усі учасники групи</p>
            <div className="mt-2">
              <PhotoPicker compact label="інше фото" onPick={setPhoto} />
            </div>
          </div>
          <button type="button" onClick={() => setPhoto(null)} className="grid h-9 w-9 place-items-center self-start rounded-full text-muted hover:bg-rose-50 hover:text-ink" aria-label="Прибрати фото">
            <X className="h-5 w-5" />
          </button>
        </div>
      ) : (
        <div className="rounded-3xl border-2 border-dashed border-rose-200 bg-white/60 p-4">
          <PhotoPicker onPick={setPhoto} />
          <p className="mt-2 text-center text-xs text-muted">Необов'язково. Фото можна додати й пізніше на сторінці чека.</p>
        </div>
      )}

      <SectionTitle>Позиції чека</SectionTitle>
      <ul className="card divide-y divide-line/70">
        {items.map((r, i) => {
          const p = parsed[i];
          const badPrice = !p.blank && p.price === null;
          return (
            <li key={r.key} className="flex items-center gap-2 px-3 py-2">
              <span className="w-5 text-center text-xs font-semibold text-muted">{i + 1}</span>
              <input
                value={r.name}
                onChange={(e) => update(r.key, { name: e.target.value })}
                placeholder="Страва чи напій"
                maxLength={120}
                aria-label={`Назва позиції ${i + 1}`}
                className="min-w-0 flex-1 rounded-xl bg-transparent px-2 py-2 text-[15px] outline-none placeholder:text-muted/60 focus:bg-blush"
              />
              <div className={cn("flex items-center gap-1 rounded-xl border bg-blush px-2.5 py-2", badPrice ? "border-minus" : "border-transparent")}>
                <input
                  value={r.price}
                  onChange={(e) => update(r.key, { price: e.target.value })}
                  inputMode="decimal"
                  placeholder="0"
                  aria-label={`Ціна позиції ${i + 1}`}
                  className="tabular w-16 bg-transparent text-right font-semibold outline-none placeholder:text-muted/50"
                />
                <span className="text-sm text-muted">₴</span>
              </div>
              <button
                type="button"
                onClick={() => setItems((rows) => (rows.length > 1 ? rows.filter((x) => x.key !== r.key) : [newRow()]))}
                className="grid h-8 w-8 place-items-center rounded-full text-muted hover:bg-rose-50 hover:text-minus"
                aria-label="Видалити позицію"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </li>
          );
        })}
      </ul>
      <Button type="button" variant="soft" block className="mt-3" onClick={() => setItems((rows) => [...rows, newRow()])}>
        <Plus className="h-4 w-4" /> Додати позицію
      </Button>
      <p className="mt-3 px-1 text-xs text-muted">Після створення кожен учасник позначить, що замовляв. Спільну страву поділимо між усіма, хто її позначив.</p>
    </>
  );
}
