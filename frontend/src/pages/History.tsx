import { useQuery } from "@tanstack/react-query";
import { History as HistoryIcon, ReceiptText } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { HistoryItem } from "../api/types";
import { PageHeader } from "../components/Layout";
import { Chip, EmptyState, ErrorNote, SectionTitle, SegmentedControl, Spinner, cn } from "../components/ui";
import { useAuth } from "../hooks/useAuth";
import { TransferIcon, categoryIcon, dateLabel } from "../lib/categories";
import { formatKop } from "../lib/money";

type Kind = "all" | "transfers" | "expenses";
const SPLIT: Record<HistoryItem["split_mode"], string> = { equal: "порівну", exact: "точні суми", items: "за чеком" };

export function HistoryPage() {
  const { user } = useAuth();
  const [kind, setKind] = useState<Kind>("transfers");
  const [groupId, setGroupId] = useState<number | undefined>();
  const [mine, setMine] = useState(false);

  const groups = useQuery({ queryKey: ["groups"], queryFn: api.groups });
  const history = useQuery({
    queryKey: ["history", kind, groupId ?? 0, mine],
    queryFn: () => api.history({ kind, groupId, mine }),
    refetchInterval: 5000,
  });

  const byDate = useMemo(() => {
    const map = new Map<string, HistoryItem[]>();
    for (const item of history.data ?? []) map.set(item.op_date, [...(map.get(item.op_date) ?? []), item]);
    return [...map.entries()];
  }, [history.data]);

  const total = (history.data ?? []).reduce((s, i) => s + i.amount_kop, 0);

  return (
    <div className="animate-rise">
      <PageHeader title="Історія" subtitle="Повернення боргів і витрати в усіх ваших групах" />

      <SegmentedControl<Kind>
        value={kind}
        onChange={setKind}
        options={[
          { value: "transfers", label: "Повернення" },
          { value: "expenses", label: "Витрати" },
          { value: "all", label: "Усе" },
        ]}
      />

      <div className="mt-4 flex flex-wrap gap-2">
        <Chip active={groupId === undefined} onClick={() => setGroupId(undefined)}>
          Усі групи
        </Chip>
        {groups.data?.map((g) => (
          <Chip key={g.id} active={groupId === g.id} onClick={() => setGroupId(g.id)}>
            {g.emoji} {g.name}
          </Chip>
        ))}
        <Chip active={mine} onClick={() => setMine((v) => !v)}>
          Лише за моєю участю
        </Chip>
      </div>

      {history.isLoading && <Spinner />}
      <ErrorNote>{history.error?.message}</ErrorNote>

      {history.data && history.data.length > 0 && (
        <p className="mt-5 px-1 text-sm text-muted">
          {history.data.length} записів на суму <b className="tabular text-ink">{formatKop(total)}</b>
        </p>
      )}

      {history.data?.length === 0 && (
        <div className="card mt-6">
          <EmptyState
            icon={<HistoryIcon />}
            title={kind === "transfers" ? "Повернень ще не було" : "Записів немає"}
            text="Спробуйте інший фільтр або додайте операцію в групі."
          />
        </div>
      )}

      {byDate.map(([date, items]) => (
        <section key={date}>
          <SectionTitle>{dateLabel(date)}</SectionTitle>
          <ul className="card divide-y divide-line/70 overflow-hidden">
            {items.map((item) => {
              const transfer = item.type === "transfer";
              const Icon = transfer ? TransferIcon : item.receipt_id ? ReceiptText : categoryIcon(item.category);
              const toMe = transfer && item.recipient?.id === user?.id;
              const fromMe = transfer && item.payer.id === user?.id;
              return (
                <li key={item.id}>
                  <Link to={`/groups/${item.group.id}`} className="flex items-center gap-3.5 px-4 py-3.5 transition hover:bg-rose-50/60">
                    <span className={cn("grid h-11 w-11 shrink-0 place-items-center rounded-2xl", transfer ? "bg-plus/10 text-plus" : "bg-rose-50 text-rose-500")}>
                      <Icon className="h-5 w-5" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-semibold">
                        {transfer ? `${item.payer.display_name} → ${item.recipient?.display_name}` : item.description || item.category}
                      </p>
                      <p className="text-xs leading-snug text-muted">
                        {item.group.emoji} {item.group.name} ·{" "}
                        {transfer ? (toMe ? "повернули вам" : fromMe ? "ви повернули" : "повернення боргу") : `оплата: ${item.payer.display_name} · ${SPLIT[item.split_mode]}`}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className={cn("tabular font-bold", toMe && "text-plus", fromMe && "text-minus")}>
                        {toMe ? "+" : fromMe ? "−" : ""}
                        {formatKop(item.amount_kop)}
                      </p>
                      {item.my_share_kop !== null && <p className="tabular text-[11px] text-muted">ваша частка {formatKop(item.my_share_kop)}</p>}
                    </div>
                  </Link>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}
