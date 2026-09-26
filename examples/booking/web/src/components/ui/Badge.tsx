import type { HTMLAttributes } from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/cn";

const badgeStyles = cva(
  "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide whitespace-nowrap",
  {
    variants: {
      tone: {
        neutral: "bg-paper-300 text-ink-300 ring-1 ring-inset ring-paper-500",
        ok: "bg-sage/15 text-sage ring-1 ring-inset ring-sage/30",
        warn: "bg-amber/15 text-amber ring-1 ring-inset ring-amber/30",
        danger: "bg-rust/15 text-rust ring-1 ring-inset ring-rust/30",
        info: "bg-sky/15 text-sky ring-1 ring-inset ring-sky/30",
        coal: "bg-coal-500/60 text-coal-50 ring-1 ring-inset ring-coal-400/70",
      },
      size: {
        sm: "text-[10px] px-1.5",
        md: "text-[11px]",
      },
    },
    defaultVariants: { tone: "neutral", size: "md" },
  },
);

interface Props extends HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeStyles> {}

export function Badge({ tone, size, className, ...props }: Props) {
  return <span className={cn(badgeStyles({ tone, size }), className)} {...props} />;
}
