import { day, daysBetween, eur, expectedComparable, pct, signed } from "./format";

test("formats as a German buyer reads it", () => {
  expect(eur(1234567.4)).toBe("1.234.567 €");
  expect(day("2026-12-15")).toBe("15.12.2026");
  expect(pct(0.256)).toBe("26 %");
  expect(signed(-0.05)).toBe("−0.05");
});

test("expected comparable bids add up over the selected firms", () => {
  expect(
    expectedComparable([
      { p_bid: 0.5, p_competitive: 0.6 },
      { p_bid: 0.2, p_competitive: 1 },
    ]),
  ).toBeCloseTo(0.5);
  expect(daysBetween("2026-12-01", "2026-12-15")).toBe(14);
});
