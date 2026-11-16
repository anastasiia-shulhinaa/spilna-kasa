import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDownLeft, ArrowUpRight, ChevronRight, KeyRound, Plus } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { AvatarStack } from "../components/Avatar";
import { BalanceBadge } from "../components/BalanceBadge";
import { PageHeader } from "../components/Layout";
import { Modal } from "../components/Modal";
import { useToast } from "../components/Toast";
import { Button, EmptyState, ErrorNote, Field, Spinner, cn } from "../components/ui";
import { useAuth } from "../hooks/useAuth";
import { formatKop } from "../lib/money";

const EMOJIS = ["🏠", "🏔️", "✈️", "🎉", "🍕", "🎁", "🚗", "💗"];

export function GroupsPage() {
  const { user } = useAuth();
  const groups = useQuery({ queryKey: ["groups"], queryFn: api.groups, refetchInterval: 5000 });
  const [modal, setModal] = useState<"create" | "join" | null>(null);

  return (
    <>
      <PageHeader title="Мої групи" subtitle={user ? `Вітаємо, ${user.display_name}!` : undefined} />

      <DebtsSummary />

      {groups.isLoading && <Spinner />}
      <ErrorNote>{groups.error?.message}</ErrorNote>

      {groups.data?.length === 0 && (
        <div className="card">
          <EmptyState icon="👋" title="Поки що жодної групи" text="Створіть групу для квартири чи поїздки або приєднайтеся за кодом від друзів." />
        </div>
      )}

      <ul className="space-y-3">
        {groups.data?.map((g, i) => (
          <li key={g.id} className="animate-rise" style={{ animationDelay: `${i * 40}ms` }}>
            <Link to={`/groups/${g.id}`} className="card group flex items-center gap-4 p-4 transition hover:-translate-y-0.5">
              <span className="grid h-14 w-14 shrink-0 place-items-center rounded-2xl bg-rose-50 text-3xl">{g.emoji}</span>
              <div className="min-w-0 flex-1">
                <p className="truncate font-bold">{g.name}</p>
                <div className="mt-1.5 flex items-center gap-2">
                  <AvatarStack people={g.members} />
                  <span className="whitespace-nowrap text-xs text-muted">{g.members.length} учасн.</span>
                </div>
              </div>
              <BalanceBadge kop={g.my_balance_kop} />
              <ChevronRight className="h-5 w-5 shrink-0 text-rose-300 transition group-hover:translate-x-0.5" />
            </Link>
          </li>
        ))}
      </ul>

      <div className="mt-6 grid grid-cols-2 gap-3">
        <Button onClick={() => setModal("create")}>
          <Plus className="h-4 w-4" /> Нова група
        </Button>
        <Button variant="outline" onClick={() => setModal("join")}>
          <KeyRound className="h-4 w-4" /> За кодом
        </Button>
      </div>

      <CreateGroupModal open={modal === "create"} onClose={() => setModal(null)} />
      <JoinGroupModal open={modal === "join"} onClose={() => setModal(null)} />
    </>
  );
}

function DebtsSummary() {
  const debts = useQuery({ queryKey: ["my-debts"], queryFn: api.myDebts, refetchInterval: 5000 });
  if (!debts.data) return null;
  const d = debts.data;
  const top = d.owed_to_me.slice(0, 3);
  return (
    <Link to="/debts" className="card mb-5 block p-4 transition hover:-translate-y-0.5">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <p className="flex items-center gap-1 text-xs font-semibold text-muted">
            <ArrowDownLeft className="h-3.5 w-3.5 text-plus" /> Вам винні
          </p>
          <p className="tabular text-xl font-extrabold text-plus">{formatKop(d.owed_to_me_total_kop)}</p>
        </div>
        <div>
          <p className="flex items-center gap-1 text-xs font-semibold text-muted">
            <ArrowUpRight className="h-3.5 w-3.5 text-minus" /> Ви винні
          </p>
          <p className="tabular text-xl font-extrabold text-minus">{formatKop(d.i_owe_total_kop)}</p>
        </div>
      </div>
      {top.length > 0 && (
        <p className="mt-3 truncate border-t border-line/70 pt-3 text-xs text-muted">
          {top.map((r) => `${r.user.display_name} — ${formatKop(r.total_kop)}`).join(" · ")}
          {d.owed_to_me.length > top.length && " · …"}
        </p>
      )}
      <p className="mt-2 flex items-center gap-1 text-xs font-semibold text-rose-600">
        Детальніше <ChevronRight className="h-3.5 w-3.5" />
      </p>
    </Link>
  );
}

function CreateGroupModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const nav = useNavigate();
  const toast = useToast();
  const [name, setName] = useState("");
  const [emoji, setEmoji] = useState(EMOJIS[0]);
  const create = useMutation({
    mutationFn: api.createGroup,
    onSuccess: (g) => {
      qc.invalidateQueries({ queryKey: ["groups"] });
      toast("Групу створено");
      onClose();
      setName("");
      nav(`/groups/${g.id}`);
    },
  });

  return (
    <Modal open={open} onClose={onClose} title="Нова група">
      <form
        className="space-y-5"
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate({ name, emoji });
        }}
      >
        <Field label="Назва" autoFocus required maxLength={80} value={name} onChange={(e) => setName(e.target.value)} placeholder="Квартира, Карпати 2026…" />
        <div>
          <span className="label">Іконка</span>
          <div className="grid grid-cols-8 gap-2">
            {EMOJIS.map((em) => (
              <button
                key={em}
                type="button"
                onClick={() => setEmoji(em)}
                className={cn("grid aspect-square place-items-center rounded-2xl text-xl transition", emoji === em ? "bg-rose-100 ring-2 ring-rose-400" : "bg-blush hover:bg-rose-50")}
              >
                {em}
              </button>
            ))}
          </div>
        </div>
        <ErrorNote>{create.error?.message}</ErrorNote>
        <Button type="submit" block loading={create.isPending}>
          Створити групу
        </Button>
      </form>
    </Modal>
  );
}

function JoinGroupModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const nav = useNavigate();
  const toast = useToast();
  const [code, setCode] = useState("");
  const join = useMutation({
    mutationFn: api.joinGroup,
    onSuccess: (g) => {
      qc.invalidateQueries({ queryKey: ["groups"] });
      toast(`Ви приєдналися до «${g.name}»`);
      onClose();
      setCode("");
      nav(`/groups/${g.id}`);
    },
  });

  return (
    <Modal open={open} onClose={onClose} title="Приєднатися до групи">
      <form
        className="space-y-5"
        onSubmit={(e) => {
          e.preventDefault();
          join.mutate(code);
        }}
      >
        <label className="block">
          <span className="label">Код запрошення</span>
          <input
            autoFocus
            required
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            maxLength={8}
            placeholder="KASA26"
            className="field text-center font-mono text-2xl font-bold tracking-[0.4em]"
          />
          <span className="mt-1.5 block text-xs text-muted">Код можна взяти на сторінці групи в учасника.</span>
        </label>
        <ErrorNote>{join.error?.message}</ErrorNote>
        <Button type="submit" block loading={join.isPending}>
          Приєднатися
        </Button>
      </form>
    </Modal>
  );
}
