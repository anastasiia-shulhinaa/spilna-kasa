import { describe, expect, it } from "vitest";
import { formatKop, kopToInput, parseAmount, parseShare, splitEqual } from "./money";

describe("money", () => {
  it("parses Ukrainian amounts", () => {
    expect(parseAmount("600")).toBe(60000);
    expect(parseAmount("33,34")).toBe(3334);
    expect(parseAmount("1 250")).toBe(125000);
    expect(parseAmount("0")).toBeNull();
    expect(parseAmount("abc")).toBeNull();
  });

  it("formats kopecks", () => {
    expect(formatKop(123456)).toBe("1 234,56 ₴");
    expect(formatKop(-20000)).toBe("−200,00 ₴");
    expect(formatKop(20000, { sign: true })).toBe("+200,00 ₴");
  });

  it("parses exact shares: empty and zero mean 0", () => {
    expect(parseShare("")).toBe(0);
    expect(parseShare("0")).toBe(0);
    expect(parseShare("0,00")).toBe(0);
    expect(parseShare("600")).toBe(60000);
    expect(parseShare("abc")).toBeNull();
    expect(kopToInput(60000)).toBe("600");
    expect(kopToInput(3334)).toBe("33,34");
  });

  it("splits 100 by 3 without losing a kopeck", () => {
    const shares = splitEqual(10000, [3, 1, 2]);
    expect([...shares.entries()]).toEqual([
      [1, 3334],
      [2, 3333],
      [3, 3333],
    ]);
  });
});
