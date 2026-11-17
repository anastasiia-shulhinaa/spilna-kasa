export interface User {
  id: number;
  email: string;
  display_name: string;
}

export interface UserPublic {
  id: number;
  display_name: string;
}

export interface Member extends UserPublic {
  role: "owner" | "member";
}

export interface GroupSummary {
  id: number;
  name: string;
  emoji: string;
  currency: string;
  members: Member[];
  my_balance_kop: number;
}

export interface GroupDetail extends GroupSummary {
  invite_code: string;
  total_expenses_kop: number;
}

export type SplitMode = "equal" | "exact" | "items";

export interface Operation {
  id: number;
  type: "expense" | "transfer";
  split_mode: SplitMode;
  created_by: number;
  receipt_id: number | null;
  amount_kop: number;
  payer_id: number;
  recipient_id: number | null;
  category: string | null;
  description: string;
  op_date: string;
  created_at: string;
  shares: { user_id: number; share_kop: number }[];
}

export interface Balances {
  members: { user: UserPublic; balance_kop: number }[];
  debts: { from_user: UserPublic; to_user: UserPublic; amount_kop: number }[];
  debts_optimal: boolean;
  total_expenses_kop: number;
}

export interface ReceiptItem {
  id: number;
  name: string;
  price_kop: number;
  claimed_by: number[];
}

export interface Receipt {
  id: number;
  group_id: number;
  title: string;
  category: string;
  payer_id: number;
  created_by: number;
  status: "open" | "closed";
  has_photo: boolean;
  photo_version: string | null;
  operation_id: number | null;
  op_date: string;
  created_at: string;
  items: ReceiptItem[];
  total_kop: number;
  unclaimed_kop: number;
  totals: { user_id: number; share_kop: number }[];
}

export const CATEGORIES = ["Продукти", "Житло", "Транспорт", "Розваги", "Здоров'я", "Інше"] as const;
export type Category = (typeof CATEGORIES)[number];

export interface GroupRef {
  id: number;
  name: string;
  emoji: string;
}

export interface CounterpartDebt {
  user: UserPublic;
  total_kop: number;
  groups: { group: GroupRef; amount_kop: number }[];
}

export interface MyDebts {
  owed_to_me: CounterpartDebt[];
  i_owe: CounterpartDebt[];
  owed_to_me_total_kop: number;
  i_owe_total_kop: number;
}

export interface HistoryItem {
  id: number;
  group: GroupRef;
  type: "expense" | "transfer";
  split_mode: SplitMode;
  amount_kop: number;
  payer: UserPublic;
  recipient: UserPublic | null;
  category: string | null;
  description: string;
  op_date: string;
  created_at: string;
  receipt_id: number | null;
  my_share_kop: number | null;
}
