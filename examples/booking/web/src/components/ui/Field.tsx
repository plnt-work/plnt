import { forwardRef, type InputHTMLAttributes, type LabelHTMLAttributes, type ReactNode } from "react";

import { cn } from "@/lib/cn";

export function Field({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return <div className={cn("flex flex-col gap-1.5", className)}>{children}</div>;
}

export const FieldLabel = forwardRef<HTMLLabelElement, LabelHTMLAttributes<HTMLLabelElement>>(
  ({ className, ...props }, ref) => (
    <label
      ref={ref}
      className={cn("text-xs font-medium uppercase tracking-wide text-ink-200", className)}
      {...props}
    />
  ),
);
FieldLabel.displayName = "FieldLabel";

export const FieldInput = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "h-10 w-full rounded-md border border-paper-600 bg-white px-3 text-sm text-ink-700 " +
          "placeholder:text-ink-100 outline-none transition-colors " +
          "focus-visible:border-iri-blue focus-visible:ring-2 focus-visible:ring-iri-blue/25 " +
          "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    />
  ),
);
FieldInput.displayName = "FieldInput";

export function FieldHint({ className, children }: { className?: string; children?: ReactNode }) {
  return <p className={cn("text-xs text-ink-100", className)}>{children}</p>;
}
