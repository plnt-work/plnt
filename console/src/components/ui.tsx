import { Loader2, X } from "lucide-react";
import { useEffect, useRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { cx } from "@/lib/format";

type Variant = "primary" | "secondary" | "ghost" | "danger";

export function Button({
  variant = "secondary",
  busy,
  className,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; busy?: boolean }) {
  return (
    <button
      {...rest}
      // Default to a plain button: only buttons that say type="submit" submit forms.
      type={rest.type ?? "button"}
      disabled={rest.disabled || busy}
      className={cx(
        "inline-flex h-8 items-center justify-center gap-1.5 rounded-md px-3 text-[13px] font-medium",
        "transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
        variant === "primary" && "bg-accent text-accent-ink hover:opacity-90",
        variant === "secondary" && "border border-line bg-panel hover:bg-sunken",
        variant === "ghost" && "hover:bg-sunken",
        variant === "danger" && "border border-line bg-panel text-danger hover:bg-danger-soft",
        className,
      )}
    >
      {busy && <Loader2 className="size-3.5 animate-spin" />}
      {children}
    </button>
  );
}

export function Card({ title, actions, children, className }: {
  title?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cx("rounded-lg border border-line bg-panel", className)}>
      {(title || actions) && (
        <header className="flex items-center justify-between gap-3 border-b border-line px-4 py-2.5">
          <h2 className="text-[13px] font-semibold">{title}</h2>
          <div className="flex items-center gap-2">{actions}</div>
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function Badge({ tone = "neutral", children }: {
  tone?: "neutral" | "good" | "bad" | "warn";
  children: ReactNode;
}) {
  return (
    <span
      className={cx(
        "inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-medium",
        tone === "neutral" && "bg-sunken text-muted",
        tone === "good" && "bg-accent-soft text-accent",
        tone === "bad" && "bg-danger-soft text-danger",
        tone === "warn" && "bg-warn-soft text-warn",
      )}
    >
      {children}
    </span>
  );
}

export function Stat({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div className="rounded-lg border border-line bg-panel px-4 py-3">
      <div className="text-[12px] text-muted">{label}</div>
      <div className="mt-1 text-xl font-semibold tabular-nums">{value}</div>
      {sub && <div className="mt-0.5 text-[12px] text-muted">{sub}</div>}
    </div>
  );
}

export function Field({ label, hint, required, children }: {
  label: string;
  hint?: string;
  required?: boolean;
  children: ReactNode;
}) {
  return (
    <label className="block space-y-1">
      <span className="text-[12px] font-medium">
        {label}
        {required && <span className="text-danger"> *</span>}
      </span>
      {children}
      {hint && <span className="block text-[12px] text-muted">{hint}</span>}
    </label>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  if (!error) return null;
  const msg = error instanceof Error ? error.message : String(error);
  return (
    <div role="alert" className="rounded-md bg-danger-soft px-3 py-2 text-[13px] text-danger">
      {msg}
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-line px-6 py-10 text-center">
      <div className="font-medium">{title}</div>
      {children && <div className="mt-1 text-[13px] text-muted">{children}</div>}
    </div>
  );
}

export function Spinner() {
  return <Loader2 className="size-4 animate-spin text-muted" aria-label="Loading" />;
}

/** Native <dialog>: focus trap, Esc and backdrop handled by the browser. */
export function Modal({ open, onClose, title, children, wide }: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => e.target === ref.current && onClose()}
      className={cx(
        "m-auto w-[calc(100%-2rem)] rounded-lg border border-line bg-panel p-0 text-ink shadow-xl",
        wide ? "max-w-2xl" : "max-w-md",
      )}
    >
      {open && (
        <div>
          <header className="flex items-center justify-between border-b border-line px-4 py-3">
            <h2 className="font-semibold">{title}</h2>
            <button onClick={onClose} className="rounded p-1 hover:bg-sunken" aria-label="Close">
              <X className="size-4" />
            </button>
          </header>
          <div className="max-h-[75vh] overflow-y-auto p-4">{children}</div>
        </div>
      )}
    </dialog>
  );
}

export function Tabs<T extends string>({ tabs, value, onChange }: {
  tabs: { id: T; label: string }[];
  value: T;
  onChange: (t: T) => void;
}) {
  return (
    <nav className="-mx-4 flex gap-1 overflow-x-auto border-b border-line px-4 md:mx-0 md:px-0" role="tablist">
      {tabs.map((t) => (
        <button
          key={t.id}
          role="tab"
          aria-selected={value === t.id}
          onClick={() => onChange(t.id)}
          className={cx(
            "-mb-px shrink-0 whitespace-nowrap border-b-2 px-3 py-2 text-[13px] font-medium",
            value === t.id ? "border-accent text-ink" : "border-transparent text-muted hover:text-ink",
          )}
        >
          {t.label}
        </button>
      ))}
    </nav>
  );
}
