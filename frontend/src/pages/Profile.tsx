import { useMutation, useQueryClient } from "@tanstack/react-query";
import { LogOut } from "lucide-react";
import { useState } from "react";
import { api } from "../api/client";
import { Avatar } from "../components/Avatar";
import { PageHeader } from "../components/Layout";
import { useToast } from "../components/Toast";
import { Button, ErrorNote, Field, Spinner } from "../components/ui";
import { useAuth } from "../hooks/useAuth";

export function ProfilePage() {
  const { user, signOut } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const [name, setName] = useState<string | null>(null);
  const update = useMutation({
    mutationFn: api.updateMe,
    onSuccess: () => {
      qc.invalidateQueries();
      setName(null);
      toast("Ім'я збережено");
    },
  });

  if (!user) return <Spinner />;
  const value = name ?? user.display_name;

  return (
    <div className="animate-rise">
      <PageHeader title="Профіль" />
      <div className="card flex flex-col items-center px-6 py-8 text-center">
        <Avatar id={user.id} name={value || user.display_name} size="xl" />
        <p className="mt-4 text-lg font-extrabold">{user.display_name}</p>
        <p className="text-sm text-muted">{user.email}</p>
      </div>

      <form
        className="card mt-4 space-y-4 p-6"
        onSubmit={(e) => {
          e.preventDefault();
          update.mutate(value);
        }}
      >
        <Field label="Ім'я в групах" required maxLength={80} value={value} onChange={(e) => setName(e.target.value)} />
        <ErrorNote>{update.error?.message}</ErrorNote>
        <Button type="submit" variant="soft" block loading={update.isPending} disabled={value.trim() === user.display_name}>
          Зберегти
        </Button>
      </form>

      <Button variant="ghost" block className="mt-4" onClick={signOut}>
        <LogOut className="h-4 w-4" /> Вийти
      </Button>
      <p className="mt-6 text-center text-xs text-muted">Спільна каса · версія 0.4 (етап 4)</p>
    </div>
  );
}
