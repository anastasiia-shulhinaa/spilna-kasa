import { useQuery } from "@tanstack/react-query";
import { ArrowDownLeft, ArrowUpRight, ChevronRight } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { CounterpartDebt } from "../api/types";
import { Avatar } from "../components/Avatar";
import { PageHeader } from "../components/Layout";
import { RepayModal, type RepayTarget } from "../components/RepayModal";
import { Button, EmptyState, ErrorNote, SectionTitle, Spinner, cn } from "../components/ui";
import { useAuth } from "../hooks/useAuth";
import { formatKop } from "../lib/money";

export function DebtsPage() {
  const { user } = useAuth();
  const debts = useQuery({ queryKey: ["my-debts"], queryFn: api.myDebts, refetchInterval: 5000 });
  const [repay, setRepay] = useState<RepayTarget | null>(null);

  if (debts.isLoading || !user) return <Spinner />;
  if (debts.error) return <ErrorNote>{debts.error.message}</ErrorNote>;
  const d = debts.data!;
  const me = { id: user.id, display_name: user.display_name };
  const empty = d.owed_to_me.length === 0 && d.i_owe.length === 0;

  return (
    <div className="animate-rise">
      <PageHeader title="Борги" subtitle="Хто кому скільки винен просто зараз, у всіх ваших групах" />

      <div className="grid grid-cols-2 gap-3">
        <div className="card p-4">
          <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted">
            <ArrowDownLeft className="h-4 w-4 text-plus" /> Вам винні
          </p>
          <p className="tabular mt-1 text-2xl font-extrabold text-plus">{formatKop(d.owed_to_me_total_kop)}</p>
        </div>
        <div className="card p-4">
          <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted">
            <ArrowUpRight className="h-4 w-4 text-minus" /> Ви винні
          </p>
          <p className="tabular mt-1 text-2xl font-extrabold text-minus">{formatKop(d.i_owe_total_kop)}</p>
        </div>
      </div>

      {empty && (
        <div className="card mt-6">
          <EmptyState icon="✨" title="Усе чисто, ніхто нікому не винен!" text="Коли з'являться нові витрати, тут буде видно, хто кому має повернути гроші." />
        </div>
      )}

      {d.owed_to_me.length > 0 && (
        <>
          <SectionTitle>Хто вам винен</SectionTitle>
          <ul className="space-y-3">
            {d.owed_to_me.map((row) => (
              <PersonCard
                key={row.user.id}
                row={row}
                tone="plus"
                actionLabel="Отримано"
                onAction={(groupId, groupLabel, amount) => setRepay({ groupId, groupLabel, from_user: row.user, to_user: me, amount_kop: amount })}
              />
            ))}
          </ul>
        </>
      )}

      {d.i_owe.length > 0 && (
        <>
          <SectionTitle>Кому ви винні</SectionTitle>
          <ul className="space-y-3">
            {d.i_owe.map((row) => (
              <PersonCard
                key={row.user.id}
                row={row}
                tone="minus"
                actionLabel="Повернути"
                onAction={(groupId, groupLabel, amount) => setRepay({ groupId, groupLabel, from_user: me, to_user: row.user, amount_kop: amount })}
              />
            ))}
          </ul>
        </>
      )}

      <p className="mt-6 px-1 text-xs text-muted">
        Борги рахуються окремо в кожній групі: якщо в одній групі вам винні, а в іншій винні ви, суми не взаємозараховуються.
      </p>

      <RepayModal key={repay ? `${repay.groupId}-${repay.from_user.id}-${repay.to_user.id}` : "none"} target={repay} onClose={() => setRepay(null)} />
    </div>
  );
}

function PersonCard({
  row,
  tone,
  actionLabel,
  onAction,
}: {
  row: CounterpartDebt;
  tone: "plus" | "minus";
  actionLabel: string;
  onAction: (groupId: number, groupLabel: string, amount: number) => void;
}) {
  return (
    <li className="card overflow-hidden">
      <div className="flex items-center gap-3 px-4 pb-2 pt-4">
        <Avatar id={row.user.id} name={row.user.display_name} />
        <p className="flex-1 font-bold">{row.user.display_name}</p>
        <p className={cn("tabular text-lg font-extrabold", tone === "plus" ? "text-plus" : "text-minus")}>{formatKop(row.total_kop)}</p>
      </div>
      <ul className="divide-y divide-line/70 border-t border-line/70">
        {row.groups.map(({ group, amount_kop }) => (
          <li key={group.id} className="flex items-center gap-3 px-4 py-2.5">
            <Link to={`/groups/${group.id}?tab=balances`} className="flex min-w-0 flex-1 items-center gap-2 text-sm hover:text-rose-600">
              <span>{group.emoji}</span>
              <span className="truncate">{group.name}</span>
              <ChevronRight className="h-4 w-4 shrink-0 text-rose-300" />
            </Link>
            <span className="tabular text-sm font-semibold">{formatKop(amount_kop)}</span>
            <Button
              variant={tone === "minus" ? "primary" : "soft"}
              className="px-3 py-1.5 text-xs"
              onClick={() => onAction(group.id, `${group.emoji} ${group.name}`, amount_kop)}
            >
              {actionLabel}
            </Button>
          </li>
        ))}
      </ul>
    </li>
  );
}
