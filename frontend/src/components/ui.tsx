import { Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";

export function cn(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

type Variant = "primary" | "soft" | "ghost" | "outline";

const variants: Record<Variant, string> = {
  primary: "bg-rose-500 text-white shadow-pop hover:bg-rose-600 active:bg-rose-700",
  soft: "bg-rose-100 text-rose-700 hover:bg-rose-200",
  ghost: "text-muted hover:bg-rose-50 hover:text-ink",
  outline: "border border-line bg-white text-ink hover:border-rose-300 hover:bg-rose-50",
};

export function Button({
  variant = "primary",
  loading,
  block,
  className,
  children,
  disabled,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean; block?: boolean }) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-full px-5 py-3 text-[15px] font-semibold transition",
        "focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-rose-200 disabled:cursor-not-allowed disabled:opacity-50",
        variants[variant],
        block && "w-full",
        className,
      )}
      disabled={disabled || loading}
      {...rest}
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" />}
      {children}
    </button>
  );
}

export function Field({
  label,
  hint,
  className,
  ...rest
}: InputHTMLAttributes<HTMLInputElement> & { label?: string; hint?: string }) {
  return (
    <label className={cn("block", className)}>
      {label && <span className="label">{label}</span>}
      <input className="field" {...rest} />
      {hint && <span className="mt-1.5 block text-xs text-muted">{hint}</span>}
    </label>
  );
}

export function Chip({
  active,
  children,
  onClick,
  className,
}: {
  active?: boolean;
  children: ReactNode;
  onClick?: () => void;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "inline-flex items-center gap-2 rounded-full border px-3.5 py-2 text-sm font-medium transition",
        active
          ? "border-rose-500 bg-rose-500 text-white shadow-pop"
          : "border-line bg-white text-ink hover:border-rose-300 hover:bg-rose-50",
        className,
      )}
    >
      {children}
    </button>
  );
}

export function SegmentedControl<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
}) {
  return (
    <div className="grid rounded-full bg-rose-100/70 p-1" style={{ gridTemplateColumns: `repeat(${options.length}, 1fr)` }}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => onChange(o.value)}
          className={cn(
            "rounded-full py-2.5 text-sm font-semibold transition",
            value === o.value ? "bg-white text-rose-600 shadow-soft" : "text-muted hover:text-ink",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <div className={cn("flex justify-center py-10", className)}>
      <Loader2 className="h-6 w-6 animate-spin text-rose-400" />
    </div>
  );
}

export function EmptyState({ icon, title, text }: { icon: ReactNode; title: string; text?: string }) {
  return (
    <div className="flex flex-col items-center px-6 py-10 text-center animate-rise">
      <div className="mb-4 grid h-16 w-16 place-items-center rounded-3xl bg-rose-100 text-3xl text-rose-500">{icon}</div>
      <p className="font-bold text-ink">{title}</p>
      {text && <p className="mt-1 max-w-xs text-sm text-muted">{text}</p>}
    </div>
  );
}

export function ErrorNote({ children }: { children: ReactNode }) {
  if (!children) return null;
  return (
    <p role="alert" className="rounded-2xl bg-minus/10 px-4 py-3 text-sm font-medium text-minus">
      {children}
    </p>
  );
}

export function SectionTitle({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-3 mt-7 flex items-center justify-between px-1">
      <h2 className="text-xs font-bold uppercase tracking-wider text-muted">{children}</h2>
      {action}
    </div>
  );
}
