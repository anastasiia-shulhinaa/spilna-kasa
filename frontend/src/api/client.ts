import type { Balances, GroupDetail, GroupSummary, HistoryItem, MyDebts, Operation, Receipt, User } from "./types";

const TOKEN_KEY = "kasa.token";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export const tokenStore = {
  get: (): string | null => {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set: (token: string | null) => {
    try {
      if (token) localStorage.setItem(TOKEN_KEY, token);
      else localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* приватний режим — токен житиме лише до перезавантаження */
    }
  },
};

let onUnauthorized: () => void = () => {};
export function setUnauthorizedHandler(fn: () => void) {
  onUnauthorized = fn;
}

async function send(method: string, path: string, body?: unknown): Promise<Response> {
  const headers: Record<string, string> = {};
  const isForm = body instanceof FormData;
  if (body !== undefined && !isForm) headers["Content-Type"] = "application/json";
  const token = tokenStore.get();
  if (token) headers.Authorization = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : isForm ? (body as FormData) : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "Сервер недоступний. Перевірте, чи запущено бекенд.");
  }

  if (res.status === 401 && token) onUnauthorized();
  if (!res.ok) {
    let detail = "Щось пішло не так. Спробуйте ще раз.";
    try {
      const data = await res.json();
      if (typeof data.detail === "string") detail = data.detail;
    } catch {
      /* відповідь без JSON */
    }
    throw new ApiError(res.status, detail);
  }
  return res;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await send(method, path, body);
  return (res.status === 204 ? undefined : await res.json()) as T;
}

async function blob(path: string): Promise<{ blob: Blob; filename: string | null }> {
  const res = await send("GET", path);
  const cd = res.headers.get("Content-Disposition") ?? "";
  const utf = /filename\*=UTF-8''([^;]+)/i.exec(cd);
  return { blob: await res.blob(), filename: utf ? decodeURIComponent(utf[1]) : null };
}

export type ExpenseInput = {
  amount_kop: number;
  payer_id: number;
  category: string;
  description: string;
  op_date: string;
} & ({ split_mode: "equal"; participant_ids: number[] } | { split_mode: "exact"; shares: { user_id: number; share_kop: number }[] });

export const api = {
  register: (data: { email: string; password: string; display_name: string }) =>
    request<{ access_token: string }>("POST", "/auth/register", data),
  login: (data: { email: string; password: string }) =>
    request<{ access_token: string }>("POST", "/auth/login", data),
  me: () => request<User>("GET", "/users/me"),
  updateMe: (display_name: string) => request<User>("PATCH", "/users/me", { display_name }),

  groups: () => request<GroupSummary[]>("GET", "/groups"),
  group: (id: number) => request<GroupDetail>("GET", `/groups/${id}`),
  createGroup: (data: { name: string; emoji: string }) => request<GroupDetail>("POST", "/groups", data),
  joinGroup: (invite_code: string) => request<GroupDetail>("POST", "/groups/join", { invite_code }),

  operations: (id: number) => request<Operation[]>("GET", `/groups/${id}/operations`),
  balances: (id: number) => request<Balances>("GET", `/groups/${id}/balances`),
  addExpense: (id: number, data: ExpenseInput) => request<Operation>("POST", `/groups/${id}/expenses`, data),
  deleteOperation: (id: number, opId: number) => request<void>("DELETE", `/groups/${id}/operations/${opId}`),
  exportXlsx: (id: number) => blob(`/groups/${id}/export.xlsx`),

  receipts: (id: number, status?: "open" | "closed") =>
    request<Receipt[]>("GET", `/groups/${id}/receipts${status ? `?status_filter=${status}` : ""}`),
  receipt: (id: number, rid: number) => request<Receipt>("GET", `/groups/${id}/receipts/${rid}`),
  createReceipt: (
    id: number,
    data: { title: string; payer_id: number; category: string; op_date: string; items: { name: string; price_kop: number }[] },
  ) => request<Receipt>("POST", `/groups/${id}/receipts`, data),
  uploadReceiptPhoto: (id: number, rid: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Receipt>("POST", `/groups/${id}/receipts/${rid}/photo`, form);
  },
  receiptPhoto: (id: number, rid: number, version: string | null) =>
    blob(`/groups/${id}/receipts/${rid}/photo?v=${version ?? ""}`).then((r) => r.blob),
  updateReceipt: (id: number, rid: number, data: { payer_id?: number; title?: string }) =>
    request<Receipt>("PATCH", `/groups/${id}/receipts/${rid}`, data),
  myDebts: () => request<MyDebts>("GET", "/me/debts"),
  history: (params: { kind: "all" | "transfers" | "expenses"; groupId?: number; mine?: boolean }) => {
    const q = new URLSearchParams({ kind: params.kind });
    if (params.groupId) q.set("group_id", String(params.groupId));
    if (params.mine) q.set("mine", "true");
    return request<HistoryItem[]>("GET", `/history?${q}`);
  },
  setClaims: (id: number, rid: number, item_ids: number[]) =>
    request<Receipt>("PUT", `/groups/${id}/receipts/${rid}/claims`, { item_ids }),
  finalizeReceipt: (id: number, rid: number) => request<Operation>("POST", `/groups/${id}/receipts/${rid}/finalize`),
  deleteReceipt: (id: number, rid: number) => request<void>("DELETE", `/groups/${id}/receipts/${rid}`),
  addTransfer: (id: number, data: { from_user_id: number; to_user_id: number; amount_kop: number }) =>
    request<Operation>("POST", `/groups/${id}/transfers`, data),
};
