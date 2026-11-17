import { ArrowRightLeft, Bus, HeartPulse, Home, PartyPopper, Receipt, ShoppingBasket, type LucideIcon } from "lucide-react";

export const CATEGORY_ICONS: Record<string, LucideIcon> = {
  Продукти: ShoppingBasket,
  Житло: Home,
  Транспорт: Bus,
  Розваги: PartyPopper,
  "Здоров'я": HeartPulse,
  Інше: Receipt,
};

export const TransferIcon = ArrowRightLeft;

export function categoryIcon(category: string | null): LucideIcon {
  return (category && CATEGORY_ICONS[category]) || Receipt;
}

export function dateLabel(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diff = Math.round((today.getTime() - d.getTime()) / 86_400_000);
  if (diff === 0) return "Сьогодні";
  if (diff === 1) return "Вчора";
  return d.toLocaleDateString("uk-UA", { day: "numeric", month: "long" });
}

export function todayIso(): string {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 10);
}
