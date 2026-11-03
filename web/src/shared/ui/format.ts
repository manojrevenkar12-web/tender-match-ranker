const de = new Intl.NumberFormat("de-DE");

export function pct(v: number, digits = 0): string {
  return `${(v * 100).toFixed(digits)} %`;
}

export function eur(v: number): string {
  return `${de.format(Math.round(v))} €`;
}

export function day(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}.${m}.${y}`;
}

export function daysBetween(from: string, to: string): number {
  return Math.round((Date.parse(to) - Date.parse(from)) / 86_400_000);
}

/** Expected comparable bids from the selected firms: each bids with p_bid and is competitive with p_competitive. */
export function expectedComparable(firms: { p_bid: number; p_competitive: number }[]): number {
  return firms.reduce((s, f) => s + f.p_bid * f.p_competitive, 0);
}

export function signed(v: number, digits = 2): string {
  return `${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(digits)}`;
}
