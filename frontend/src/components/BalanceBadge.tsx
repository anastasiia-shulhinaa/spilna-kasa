import { formatKop } from "../lib/money";
import { cn } from "./ui";

export function BalanceBadge({ kop, className }: { kop: number; className?: string }) {
  if (kop === 0)
    return <span className={cn("rounded-full bg-rose-50 px-3 py-1 text-xs font-semibold text-muted", className)}>розрахувались</span>;
  const plus = kop > 0;
  return (
    <span className={cn("flex flex-col items-end", className)}>
      <span className={cn("tabular text-[15px] font-bold", plus ? "text-plus" : "text-minus")}>{formatKop(kop, { sign: true })}</span>
      <span className="text-[11px] font-medium text-muted">{plus ? "вам винні" : "ви винні"}</span>
    </span>
  );
}
