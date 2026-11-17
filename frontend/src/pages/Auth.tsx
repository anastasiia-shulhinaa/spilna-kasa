import { useMutation } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, Navigate } from "react-router-dom";
import { api } from "../api/client";
import { Avatar } from "../components/Avatar";
import { Logo } from "../components/Layout";
import { Button, ErrorNote, Field } from "../components/ui";
import { useAuth } from "../hooks/useAuth";

const DEMO = [
  { id: 1, name: "Іванна", email: "ivanna@demo.ua" },
  { id: 2, name: "Софія", email: "sofia@demo.ua" },
  { id: 3, name: "Марина", email: "maryna@demo.ua" },
  { id: 4, name: "Вікторія", email: "viktoria@demo.ua" },
  { id: 5, name: "Анастасія", email: "anastasiia@demo.ua" },
];

function AuthFrame({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <div className="grid min-h-dvh place-items-center bg-glow px-4 py-10">
      <div className="w-full max-w-sm animate-rise">
        <div className="mb-8 flex justify-center">
          <Logo size="lg" />
        </div>
        <div className="card p-7">
          <h1 className="text-xl font-extrabold">{title}</h1>
          <p className="mb-6 mt-1 text-sm text-muted">{subtitle}</p>
          {children}
        </div>
        <p className="mt-6 text-center text-xs text-muted">Спільні гроші без суперечок 💗</p>
      </div>
    </div>
  );
}

export function LoginPage() {
  const { token, signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const login = useMutation({ mutationFn: api.login, onSuccess: (r) => signIn(r.access_token) });

  if (token) return <Navigate to="/" replace />;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    login.mutate({ email, password });
  };

  return (
    <AuthFrame title="З поверненням!" subtitle="Увійдіть, щоб побачити свої групи">
      <form onSubmit={submit} className="space-y-4">
        <Field label="Email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
        <Field label="Пароль" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
        <ErrorNote>{login.error?.message}</ErrorNote>
        <Button type="submit" block loading={login.isPending}>
          Увійти
        </Button>
      </form>

      <div className="mt-6 rounded-2xl bg-rose-50 p-4">
        <p className="mb-3 flex items-center gap-1.5 text-xs font-semibold text-rose-700">
          <Sparkles className="h-3.5 w-3.5" /> Демо-акаунти · пароль demo1234
        </p>
        <div className="flex flex-wrap gap-2">
          {DEMO.map((d) => (
            <button
              key={d.email}
              type="button"
              onClick={() => login.mutate({ email: d.email, password: "demo1234" })}
              className="flex items-center gap-2 rounded-full bg-white py-1 pl-1 pr-3 text-sm font-semibold shadow-soft transition hover:-translate-y-0.5"
            >
              <Avatar id={d.id} name={d.name} size="sm" />
              {d.name}
            </button>
          ))}
        </div>
      </div>

      <p className="mt-6 text-center text-sm text-muted">
        Ще немає акаунта?{" "}
        <Link to="/register" className="font-semibold text-rose-600 hover:underline">
          Створити
        </Link>
      </p>
    </AuthFrame>
  );
}

export function RegisterPage() {
  const { token, signIn } = useAuth();
  const [form, setForm] = useState({ display_name: "", email: "", password: "" });
  const register = useMutation({ mutationFn: api.register, onSuccess: (r) => signIn(r.access_token) });

  if (token) return <Navigate to="/" replace />;

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });

  return (
    <AuthFrame title="Створити акаунт" subtitle="Це займе менше хвилини">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          register.mutate(form);
        }}
        className="space-y-4"
      >
        <Field label="Ім'я" required value={form.display_name} onChange={set("display_name")} placeholder="Як вас називати?" autoComplete="given-name" />
        <Field label="Email" type="email" required value={form.email} onChange={set("email")} placeholder="you@example.com" autoComplete="email" />
        <Field label="Пароль" type="password" required minLength={6} value={form.password} onChange={set("password")} placeholder="Щонайменше 6 символів" autoComplete="new-password" />
        <ErrorNote>{register.error?.message}</ErrorNote>
        <Button type="submit" block loading={register.isPending}>
          Зареєструватися
        </Button>
      </form>
      <p className="mt-6 text-center text-sm text-muted">
        Уже є акаунт?{" "}
        <Link to="/login" className="font-semibold text-rose-600 hover:underline">
          Увійти
        </Link>
      </p>
    </AuthFrame>
  );
}
