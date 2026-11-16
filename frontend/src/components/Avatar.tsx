import { cn } from "./ui";

const PALETTE = [
  "bg-rose-200 text-rose-800",
  "bg-[#FFE1D6] text-[#9A3B1B]",
  "bg-[#EBDDFB] text-[#5B2C91]",
  "bg-[#FCE3EC] text-[#A01E55]",
  "bg-[#DDF3EA] text-[#16684A]",
  "bg-[#FFEFC7] text-[#86560A]",
];

export function Avatar({
  name,
  id,
  size = "md",
  ring,
}: {
  name: string;
  id: number;
  size?: "sm" | "md" | "lg" | "xl";
  ring?: boolean;
}) {
  const sizes = { sm: "h-7 w-7 text-xs", md: "h-10 w-10 text-sm", lg: "h-12 w-12 text-base", xl: "h-20 w-20 text-3xl" };
  return (
    <span
      title={name}
      className={cn(
        "inline-grid shrink-0 place-items-center rounded-full font-bold",
        PALETTE[id % PALETTE.length],
        sizes[size],
        ring && "ring-2 ring-white",
      )}
    >
      {name.trim().charAt(0).toUpperCase() || "?"}
    </span>
  );
}

export function AvatarStack({ people, max = 4 }: { people: { id: number; display_name: string }[]; max?: number }) {
  const shown = people.slice(0, max);
  const rest = people.length - shown.length;
  return (
    <div className="flex -space-x-2">
      {shown.map((p) => (
        <Avatar key={p.id} id={p.id} name={p.display_name} size="sm" ring />
      ))}
      {rest > 0 && (
        <span className="inline-grid h-7 w-7 place-items-center rounded-full bg-white text-[11px] font-bold text-muted ring-2 ring-white">
          +{rest}
        </span>
      )}
    </div>
  );
}
