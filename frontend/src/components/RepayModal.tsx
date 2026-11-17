import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { useState } from "react";
import { api } from "../api/client";
import type { UserPublic } from "../api/types";
import { formatKop, kopToInput, parseAmount } from "../lib/money";
import { Avatar } from "./Avatar";
import { Modal } from "./Modal";
import { useToast } from "./Toast";
import { Button, ErrorNote } from "./ui";

export interface RepayTarget {
  groupId: number;
  groupLabel?: string;
  from_user: UserPublic;
  to_user: UserPublic;
  amount_kop: number;
}

/** Інвалідація всього, що залежить від операцій групи. */
export function invalidateGroupData(qc: ReturnType<typeof useQueryClient>, groupId: number) {
  for (const key of ["group", "operations", "balances", "receipts"]) qc.invalidateQueries({ queryKey: [key, groupId] });
  for (const key of ["groups", "my-debts", "history"]) qc.invalidateQueries({ queryKey: [key] });
}

export function RepayModal({ target, onClose }: { target: RepayTarget | null; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [amount, setAmount] = useState(() => (target ? kopToInput(target.amount_kop) : ""));
  const transfer = useMutation({
    mutationFn: (kop: number) =>
      api.addTransfer(target!.groupId, { from_user_id: target!.from_user.id, to_user_id: target!.to_user.id, amount_kop: kop }),
    onSuccess: () => {
      invalidateGroupData(qc, target!.groupId);
      toast("Повернення записано");
      onClose();
    },
  });

  if (!target) return null;
  const kop = parseAmount(amount);
  const partial = kop !== null && kop < target.amount_kop;

  return (
    <Modal open onClose={onClose} title="Повернення боргу">
      <div className="mb-5 flex items-center justify-center gap-3 rounded-3xl bg-rose-50 p-4">
        <Avatar id={target.from_user.id} name={target.from_user.display_name} />
        <ArrowRight className="h-5 w-5 text-rose-400" />
        <Avatar id={target.to_user.id} name={target.to_user.display_name} />
      </div>
      <p className="mb-4 text-center text-sm text-muted">
        {target.from_user.display_name} повертає {target.to_user.display_name}
        {target.groupLabel && <span className="block text-xs">{target.groupLabel}</span>}
      </p>
      <label className="block">
        <span className="label">Сума, ₴</span>
        <input inputMode="decimal" className="field tabular text-center text-2xl font-bold" value={amount} onChange={(e) => setAmount(e.target.value)} />
      </label>
      {partial && <p className="mt-2 text-center text-xs text-muted">Часткове повернення: залишиться {formatKop(target.amount_kop - kop!)}</p>}
      <div className="mt-4">
        <ErrorNote>{kop === null ? "Введіть суму більшу за 0" : transfer.error?.message}</ErrorNote>
      </div>
      <Button block className="mt-5" loading={transfer.isPending} disabled={kop === null} onClick={() => kop && transfer.mutate(kop)}>
        Підтвердити
      </Button>
      <p className="mt-3 text-center text-xs text-muted">Позначене повернення — це запис в обліку, а не банківський платіж.</p>
    </Modal>
  );
}
