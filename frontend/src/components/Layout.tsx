import { HandCoins, History, Users, UserRound } from "lucide-react";
import type { ReactNode } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { Avatar } from "./Avatar";
import { cn } from "./ui";

export function Logo({ size = "md" }: { size?: "md" | "lg" }) {
  const box = size === "lg" ? "h-14 w-14 text-2xl rounded-[1.25rem]" : "h-9 w-9 text-base rounded-xl";
  return (
    <div className="flex items-center gap-2.5">
      <span className={cn("grid place-items-center bg-gradient-to-br from-rose-400 to-rose-600 font-extrabold text-white shadow-pop", box)}>₴</span>
      <span className={cn("font-extrabold tracking-tight", size === "lg" ? "text-2xl" : "text-lg")}>
        Спільна <span className="text-rose-500">каса</span>
      </span>
    </div>
  );
}

const NAV = [
  { to: "/", label: "Групи", icon: Users, end: true },
  { to: "/debts", label: "Борги", icon: HandCoins, end: false },
  { to: "/history", label: "Історія", icon: History, end: false },
  { to: "/profile", label: "Профіль", icon: UserRound, end: false },
];

/** Каркас застосунку: верхня панель на ПК, нижня навігація на телефоні. */
export function AppShell() {
  const { user } = useAuth();
  return (
    <div className="min-h-dvh bg-glow">
      <header className="sticky top-0 z-30 border-b border-line/60 bg-blush/80 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-xl items-center justify-between px-4">
          <NavLink to="/">
            <Logo />
          </NavLink>
          <nav className="hidden items-center gap-1 sm:flex">
            {NAV.map(({ to, label, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  cn("rounded-full px-4 py-2 text-sm font-semibold transition", isActive ? "bg-white text-rose-600 shadow-soft" : "text-muted hover:text-ink")
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
          {user && (
            <NavLink to="/profile" className="sm:hidden">
              <Avatar id={user.id} name={user.display_name} size="sm" />
            </NavLink>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-xl px-4 pb-32 pt-6 sm:pb-16">
        <Outlet />
      </main>

      <nav className="fixed inset-x-0 bottom-0 z-30 border-t border-line/60 bg-white/90 pb-[env(safe-area-inset-bottom)] backdrop-blur-md sm:hidden">
        <div className="mx-auto grid max-w-xl grid-cols-4">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) => cn("flex flex-col items-center gap-1 py-3 text-[11px] font-semibold", isActive ? "text-rose-600" : "text-muted")}
            >
              <Icon className="h-5 w-5" />
              {label}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  );
}

export function PageHeader({ title, subtitle, left, right }: { title: ReactNode; subtitle?: ReactNode; left?: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-6 flex items-center gap-3">
      {left}
      <div className="min-w-0 flex-1">
        <h1 className="truncate text-2xl font-extrabold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-muted">{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}
