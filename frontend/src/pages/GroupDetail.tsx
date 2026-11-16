import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, Check, ChevronRight, Copy, FileSpreadsheet, Plus, Receipt, ReceiptText, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { Balances, GroupDetail, Operation } from "../api/types";
import { Avatar, AvatarStack } from "../components/Avatar";
import { Modal } from "../components/Modal";
import { RepayModal, invalidateGroupData } from "../components/RepayModal";
import { useToast } from "../components/Toast";
import { Button, EmptyState, ErrorNote, SectionTitle, SegmentedControl, Spinner, cn } from "../components/ui";
import { useAuth } from "../hooks/useAuth";
import { TransferIcon, categoryIcon, dateLabel } from "../lib/categories";
import { saveBlob } from "../lib/download";
import { formatKop } from "../lib/money";

type Tab = "ops" | "balances";
const SYNC_MS = 4000; // імітація синхронізації: зміни інших учасників з'являються за кілька секунд

const SPLIT_LABEL: Record<Operation["split_mode"], string> = { equal: "порівну", exact: "точні суми", items: "за чеком" };

export function GroupDetailPage() {
  const groupId = Number(useParams().id);
  const [params, setParams] = useSearchParams();
  const tab: Tab = params.get("tab") === "balances" ? "balances" : "ops";

  const group = useQuery({ queryKey: ["group", groupId], queryFn: () => api.group(groupId), refetchInterval: SYNC_MS });
  const ops = useQuery({ queryKey: ["operations", groupId], queryFn: () => api.operations(groupId), refetchInterval: SYNC_MS });
  const balances = useQuery({ queryKey: ["balances", groupId], queryFn: () => api.balances(groupId), refetchInterval: SYNC_MS });

  if (group.isLoading) return <Spinner />;
  if (group.error)
    return (
      <div className="space-y-4">
        <BackLink />
        <ErrorNote>{group.error.message}</ErrorNote>
      </div>
    );
  const g = group.data!;

  return (
    <div className="animate-rise">
      <div className="mb-5 flex items-center gap-3">
        <BackLink />
        <span className="grid h-12 w-12 place-items-center rounded-2xl bg-white text-2xl shadow-soft">{g.emoji}</span>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-xl font-extrabold tracking-tight">{g.name}</h1>
          <div className="mt-1 flex items-center gap-2">
            <AvatarStack people={g.members} max={5} />
            <span className="truncate text-xs text-muted">{g.members.map((m) => m.display_name).join(", ")}</span>
          </div>
        </div>
        <ExportButton groupId={g.id} />
      </div>

      <SummaryCard group={g} />

      <OpenReceipts groupId={g.id} />

      <div className="mt-6">
        <SegmentedControl<Tab>
          value={tab}
          onChange={(t) => setParams(t === "ops" ? {} : { tab: t }, { replace: true })}
          options={[
            { value: "ops", label: "Операції" },
            { value: "balances", label: "Баланси" },
          ]}
        />
      </div>

      {tab === "ops" ? <OperationsList group={g} ops={ops.data} loading={ops.isLoading} /> : <BalancesView group={g} data={balances.data} loading={balances.isLoading} />}

      {createPortal(
      <Link
        to={`/groups/${g.id}/expense`}
        aria-label="Додати витрату"
        className="fixed bottom-24 right-5 z-20 grid h-14 w-14 place-items-center rounded-full bg-rose-500 text-white shadow-pop transition hover:scale-105 hover:bg-rose-600 sm:bottom-8 sm:right-[max(1.25rem,calc(50vw-17rem))]"
      >
        <Plus className="h-6 w-6" />
      </Link>,
      document.body,
      )}
    </div>
  );
}

function BackLink() {
  return (
    <Link to="/" aria-label="Назад" className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-white text-ink shadow-soft hover:text-rose-600">
      <ArrowLeft className="h-5 w-5" />
    </Link>
  );
}

function SummaryCard({ group }: { group: GroupDetail }) {
  const [copied, setCopied] = useState(false);
  const b = group.my_balance_kop;
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(group.invite_code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* буфер обміну недоступний */
    }
  };

  return (
    <div className="relative overflow-hidden rounded-[2rem] bg-gradient-to-br from-rose-500 via-rose-500 to-rose-400 p-6 text-white shadow-pop">
      <div className="pointer-events-none absolute -right-10 -top-12 h-44 w-44 rounded-full bg-white/10" />
      <div className="pointer-events-none absolute -bottom-16 right-16 h-32 w-32 rounded-full bg-white/10" />
      <p className="text-sm font-medium text-white/80">Ваш баланс</p>
      <p className="tabular mt-1 text-4xl font-extrabold tracking-tight">{formatKop(b, { sign: true })}</p>
      <p className="mt-1 text-sm text-white/85">{b > 0 ? "Вам винні — список нижче, у вкладці «Баланси»" : b < 0 ? "Ви винні — нічого страшного, це просто облік" : "Ви з усіма розрахувались ✨"}</p>

      <div className="relative mt-5 flex items-center justify-between gap-3 border-t border-white/20 pt-4">
        <div>
          <p className="text-xs text-white/70">Витрати групи</p>
          <p className="tabular font-bold">{formatKop(group.total_expenses_kop)}</p>
        </div>
        <button onClick={copy} className="flex items-center gap-2 rounded-full bg-white/15 px-4 py-2 text-sm font-semibold backdrop-blur transition hover:bg-white/25" title="Скопіювати код запрошення">
          <span className="text-white/75">Код</span>
          <span className="font-mono tracking-widest">{group.invite_code}</span>
          {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
        </button>
      </div>
    </div>
  );
}

function OperationsList({ group, ops, loading }: { group: GroupDetail; ops?: Operation[]; loading: boolean }) {
  const { user } = useAuth();
  const [selected, setSelected] = useState<Operation | null>(null);
  const names = useMemo(() => new Map(group.members.map((m) => [m.id, m.display_name])), [group.members]);
  const grouped = useMemo(() => {
    const map = new Map<string, Operation[]>();
    for (const op of ops ?? []) map.set(op.op_date, [...(map.get(op.op_date) ?? []), op]);
    return [...map.entries()];
  }, [ops]);

  if (loading) return <Spinner />;
  if (!ops?.length)
    return <EmptyState icon={<Receipt />} title="Операцій ще немає" text="Натисніть «+», щоб додати першу витрату. Поділ порахується автоматично." />;

  return (
    <div>
      {grouped.map(([date, list]) => (
        <section key={date}>
          <SectionTitle>{dateLabel(date)}</SectionTitle>
          <ul className="card divide-y divide-line/70 overflow-hidden">
            {list.map((op) => {
              const isTransfer = op.type === "transfer";
              const Icon = isTransfer ? TransferIcon : op.receipt_id ? ReceiptText : categoryIcon(op.category);
              const myShare = op.shares.find((s) => s.user_id === user?.id)?.share_kop;
              return (
                <li key={op.id}>
                  <button type="button" onClick={() => setSelected(op)} className="flex w-full items-center gap-3.5 px-4 py-3.5 text-left transition hover:bg-rose-50/60">
                  <span className={cn("grid h-11 w-11 shrink-0 place-items-center rounded-2xl", isTransfer ? "bg-plus/10 text-plus" : "bg-rose-50 text-rose-500")}>
                    <Icon className="h-5 w-5" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-semibold">
                      {isTransfer ? `${names.get(op.payer_id)} → ${names.get(op.recipient_id!)}` : op.description || op.category}
                    </p>
                    <p className="truncate text-xs text-muted">
                      {isTransfer ? "Повернення боргу" : `${op.category} · оплата: ${names.get(op.payer_id)} · ${SPLIT_LABEL[op.split_mode]}`}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className={cn("tabular font-bold", isTransfer && "text-plus")}>{formatKop(op.amount_kop)}</p>
                    {myShare !== undefined && <p className="tabular text-[11px] text-muted">ваша частка {formatKop(myShare)}</p>}
                  </div>
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
      <OperationModal key={selected?.id ?? "none"} group={group} op={selected} onClose={() => setSelected(null)} />
    </div>
  );
}

function ExportButton({ groupId }: { groupId: number }) {
  const toast = useToast();
  const exp = useMutation({
    mutationFn: () => api.exportXlsx(groupId),
    onSuccess: ({ blob, filename }) => {
      saveBlob(blob, filename ?? `spilna-kasa-${groupId}.xlsx`);
      toast("Таблицю Excel завантажено");
    },
    onError: (e) => toast(e.message),
  });
  return (
    <button
      onClick={() => exp.mutate()}
      disabled={exp.isPending}
      title="Експорт в Excel"
      className="flex h-10 shrink-0 items-center gap-2 rounded-full bg-white px-3.5 text-sm font-semibold text-ink shadow-soft transition hover:text-rose-600 disabled:opacity-60"
    >
      <FileSpreadsheet className="h-4 w-4 text-plus" />
      <span className="hidden sm:inline">Excel</span>
    </button>
  );
}

function OpenReceipts({ groupId }: { groupId: number }) {
  const { user } = useAuth();
  const receipts = useQuery({ queryKey: ["receipts", groupId, "open"], queryFn: () => api.receipts(groupId, "open"), refetchInterval: SYNC_MS });
  if (!receipts.data?.length) return null;
  return (
    <div className="mt-4 space-y-2">
      {receipts.data.map((r) => {
        const picked = r.items.some((i) => user && i.claimed_by.includes(user.id));
        return (
          <Link key={r.id} to={`/groups/${groupId}/receipts/${r.id}`} className="card flex items-center gap-3 border border-rose-200 p-4 transition hover:-translate-y-0.5">
            <span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-rose-100 text-rose-600">
              <ReceiptText className="h-5 w-5" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate font-bold">{r.title}</p>
              <p className="text-xs font-semibold text-rose-600">
                {picked ? "Ви вже позначили своє" : "Позначте, що ви замовляли"}
                {r.unclaimed_kop > 0 && <span className="font-medium text-muted"> · не розібрано {formatKop(r.unclaimed_kop)}</span>}
              </p>
            </div>
            <span className="tabular text-sm font-bold">{formatKop(r.total_kop)}</span>
            <ChevronRight className="h-5 w-5 shrink-0 text-rose-300" />
          </Link>
        );
      })}
    </div>
  );
}

function OperationModal({ group, op, onClose }: { group: GroupDetail; op: Operation | null; onClose: () => void }) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const nav = useNavigate();
  const toast = useToast();
  const [confirm, setConfirm] = useState(false);
  const del = useMutation({
    mutationFn: () => api.deleteOperation(group.id, op!.id),
    onSuccess: () => {
      invalidateGroupData(qc, group.id);
      toast(op?.receipt_id ? "Запис видалено — чек знову відкрито" : "Запис видалено");
      onClose();
    },
  });
  if (!op) return null;
  const names = new Map(group.members.map((m) => [m.id, m.display_name]));
  const isTransfer = op.type === "transfer";
  const canDelete = user?.id === op.created_by || user?.id === op.payer_id;

  return (
    <Modal open onClose={onClose} title={isTransfer ? "Повернення боргу" : op.description || op.category || "Витрата"}>
      <div className="mb-5 rounded-3xl bg-rose-50 p-5 text-center">
        <p className="tabular text-3xl font-extrabold">{formatKop(op.amount_kop)}</p>
        <p className="mt-1 text-sm text-muted">
          {isTransfer
            ? `${names.get(op.payer_id)} → ${names.get(op.recipient_id!)}`
            : `${op.category} · оплата: ${names.get(op.payer_id)} · ${SPLIT_LABEL[op.split_mode]}`}
        </p>
        <p className="mt-0.5 text-xs text-muted">{dateLabel(op.op_date)}</p>
      </div>

      {!isTransfer && (
        <>
          <p className="label">Хто скільки винен</p>
          <ul className="mb-5 divide-y divide-line/70 rounded-2xl border border-line">
            {op.shares.map((s) => (
              <li key={s.user_id} className="flex items-center gap-3 px-4 py-2.5">
                <Avatar id={s.user_id} name={names.get(s.user_id) ?? "?"} size="sm" />
                <span className="flex-1 text-sm font-semibold">
                  {names.get(s.user_id) ?? "Колишній учасник"}
                  {s.user_id === op.payer_id && <span className="ml-1.5 text-xs font-medium text-muted">платить</span>}
                </span>
                <span className="tabular text-sm font-bold">{formatKop(s.share_kop)}</span>
              </li>
            ))}
          </ul>
        </>
      )}

      <div className="space-y-2">
        {op.receipt_id && (
          <Button variant="soft" block onClick={() => nav(`/groups/${group.id}/receipts/${op.receipt_id}`)}>
            <ReceiptText className="h-4 w-4" /> Відкрити чек
          </Button>
        )}
        <ErrorNote>{del.error?.message}</ErrorNote>
        {canDelete &&
          (confirm ? (
            <div className="flex gap-2">
              <Button variant="outline" block onClick={() => setConfirm(false)}>
                Скасувати
              </Button>
              <Button variant="soft" block className="!bg-minus/10 !text-minus" loading={del.isPending} onClick={() => del.mutate()}>
                Так, видалити
              </Button>
            </div>
          ) : (
            <Button variant="ghost" block onClick={() => setConfirm(true)}>
              <Trash2 className="h-4 w-4" /> Видалити запис
            </Button>
          ))}
        {op.receipt_id && canDelete && <p className="text-center text-xs text-muted">Після видалення чек знову відкриється, і позначки можна буде виправити.</p>}
      </div>
    </Modal>
  );
}

type Debt = Balances["debts"][number];

function BalancesView({ group, data, loading }: { group: GroupDetail; data?: Balances; loading: boolean }) {
  const { user } = useAuth();
  const [repay, setRepay] = useState<Debt | null>(null);
  if (loading || !data) return <Spinner />;

  const maxAbs = Math.max(1, ...data.members.map((m) => Math.abs(m.balance_kop)));

  return (
    <div>
      <SectionTitle>Баланси учасників</SectionTitle>
      <ul className="card divide-y divide-line/70">
        {data.members.map(({ user: u, balance_kop }) => (
          <li key={u.id} className="flex items-center gap-3.5 px-4 py-3.5">
            <Avatar id={u.id} name={u.display_name} />
            <div className="min-w-0 flex-1">
              <p className="font-semibold">
                {u.display_name} {u.id === user?.id && <span className="text-xs font-medium text-muted">(ви)</span>}
              </p>
              <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-rose-50">
                <div
                  className={cn("h-full rounded-full transition-all", balance_kop >= 0 ? "bg-plus/70" : "bg-minus/70")}
                  style={{ width: `${(Math.abs(balance_kop) / maxAbs) * 100}%` }}
                />
              </div>
            </div>
            <p className={cn("tabular w-28 text-right font-bold", balance_kop > 0 ? "text-plus" : balance_kop < 0 ? "text-minus" : "text-muted")}>
              {balance_kop === 0 ? "0,00 ₴" : formatKop(balance_kop, { sign: true })}
            </p>
          </li>
        ))}
      </ul>

      <SectionTitle>Хто кому винен</SectionTitle>
      {data.debts.length === 0 ? (
        <div className="card">
          <EmptyState icon="✨" title="Усе чисто, ніхто нікому не винен!" />
        </div>
      ) : (
        <ul className="space-y-3">
          {data.debts.map((d) => {
            const mine = d.from_user.id === user?.id;
            const toMe = d.to_user.id === user?.id;
            return (
              <li key={`${d.from_user.id}-${d.to_user.id}`} className="card flex items-center gap-3 p-4">
                <Avatar id={d.from_user.id} name={d.from_user.display_name} size="sm" />
                <span className="text-sm font-semibold">{d.from_user.display_name}</span>
                <ArrowRight className="h-4 w-4 text-rose-300" />
                <Avatar id={d.to_user.id} name={d.to_user.display_name} size="sm" />
                <span className="min-w-0 flex-1 truncate text-sm font-semibold">{d.to_user.display_name}</span>
                <span className="tabular font-bold">{formatKop(d.amount_kop)}</span>
                {(mine || toMe) && (
                  <Button variant={mine ? "primary" : "soft"} className="px-4 py-2 text-sm" onClick={() => setRepay(d)}>
                    {mine ? "Повернути" : "Отримано"}
                  </Button>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {!data.debts_optimal && (
        <p className="mt-4 rounded-2xl bg-rose-50 px-4 py-3 text-xs text-muted">Група велика: план переказів правильний, але мінімальність кількості переказів не доведено.</p>
      )}
      <p className="mt-4 px-1 text-xs text-muted">Позначене повернення — це запис в обліку, а не банківський платіж.</p>

      <RepayModal
        key={repay ? `${repay.from_user.id}-${repay.to_user.id}` : "none"}
        target={repay ? { groupId: group.id, ...repay } : null}
        onClose={() => setRepay(null)}
      />
    </div>
  );
}
