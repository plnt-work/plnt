import clsx from "clsx";

export const cx = clsx;

export const inputClass =
  "h-8 w-full rounded-md border border-line bg-panel px-2.5 text-[13px] outline-none " +
  "placeholder:text-muted focus:border-accent";

export function fmtTime(ts: number | null | undefined): string {
  if (!ts) return "—";
  return new Date(ts * 1000).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function fmtNum(n: number): string {
  return new Intl.NumberFormat().format(n);
}

export function fmtUsd(n: number): string {
  return n === 0 ? "$0" : n < 0.01 ? `$${n.toFixed(4)}` : `$${n.toFixed(2)}`;
}
