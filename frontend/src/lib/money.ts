/** Суми зберігаються в копійках (цілі числа), як і на бекенді. */

const AMOUNT_RE = /^\d{1,12}([.,]\d{1,2})?$/;

export function parseAmount(text: string): number | null {
  const cleaned = text.replace(/[\s ]/g, "");
  if (!AMOUNT_RE.test(cleaned)) return null;
  const [whole, frac = ""] = cleaned.replace(",", ".").split(".");
  const kop = Number(whole) * 100 + Number(frac.padEnd(2, "0") || "0");
  return kop > 0 ? kop : null;
}

/** Частка в режимі «точні суми»: порожнє поле або «0» = 0, некоректне значення = null. */
export function parseShare(text: string): number | null {
  const cleaned = text.replace(/[\s ]/g, "");
  if (cleaned === "" || /^0+([.,]0{0,2})?$/.test(cleaned)) return 0;
  return parseAmount(cleaned);
}

export function kopToInput(kop: number): string {
  return kop % 100 === 0 ? String(kop / 100) : (kop / 100).toFixed(2).replace(".", ",");
}

export function formatKop(kop: number, opts: { sign?: boolean } = {}): string {
  const abs = Math.abs(kop);
  const whole = Math.floor(abs / 100)
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  const frac = (abs % 100).toString().padStart(2, "0");
  const sign = kop < 0 ? "−" : opts.sign && kop > 0 ? "+" : "";
  return `${sign}${whole},${frac} ₴`;
}

/** Та сама логіка, що й на сервері: залишок отримують перші учасники за зростанням id. */
export function splitEqual(amountKop: number, ids: number[]): Map<number, number> {
  const result = new Map<number, number>();
  if (amountKop <= 0 || ids.length === 0) return result;
  const ordered = [...ids].sort((a, b) => a - b);
  const base = Math.floor(amountKop / ordered.length);
  const remainder = amountKop % ordered.length;
  ordered.forEach((id, i) => result.set(id, base + (i < remainder ? 1 : 0)));
  return result;
}
