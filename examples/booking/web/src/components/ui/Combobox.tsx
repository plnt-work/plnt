/**
 * Combobox — cmdk-backed searchable picker, rendered inside a Radix
 * Popover-shaped Dialog primitive (we reuse Dialog for the floating panel
 * to avoid adding another dependency).
 *
 * Used for the project (tenant) selector in the Console top bar and for
 * filter pickers (user_id, business_id, status) inside table headers.
 */
import {
  forwardRef,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Command } from "cmdk";
import { Check, ChevronsUpDown, Search } from "lucide-react";

import { cn } from "@/lib/cn";

export interface ComboboxItem {
  value: string;
  label: ReactNode;
  /** Free-text the user can match against. Defaults to `value`. */
  keywords?: string[];
  trailing?: ReactNode;
}

interface Props {
  value: string | null;
  onChange: (value: string | null) => void;
  items: ComboboxItem[];
  placeholder?: string;
  searchPlaceholder?: string;
  emptyText?: string;
  clearLabel?: string;
  triggerClassName?: string;
  contentClassName?: string;
  ariaLabel?: string;
}

export const Combobox = forwardRef<HTMLButtonElement, Props>(function Combobox(
  {
    value,
    onChange,
    items,
    placeholder = "Select…",
    searchPlaceholder = "Search…",
    emptyText = "No matches.",
    clearLabel,
    triggerClassName,
    contentClassName,
    ariaLabel,
  },
  ref,
) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close on outside click + Esc.
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      const t = e.target as Node;
      if (containerRef.current && !containerRef.current.contains(t)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const selected = items.find((it) => it.value === value);

  return (
    <div ref={containerRef} className="relative inline-block">
      <button
        ref={(node) => {
          triggerRef.current = node;
          if (typeof ref === "function") ref(node);
          else if (ref) ref.current = node;
        }}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={ariaLabel}
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "inline-flex h-8 items-center gap-1.5 rounded-md border border-coal-500 bg-coal-600/60 px-2.5 text-[13px] text-coal-50",
          "hover:border-coal-400 transition-colors outline-none",
          "focus-visible:ring-2 focus-visible:ring-iri-blue/40",
          "min-w-[160px]",
          triggerClassName,
        )}
      >
        <span className="flex-1 truncate text-left">
          {selected ? selected.label : <span className="text-coal-200">{placeholder}</span>}
        </span>
        <ChevronsUpDown className="size-3.5 text-coal-200 shrink-0" />
      </button>

      {open && (
        <div
          role="listbox"
          className={cn(
            "absolute z-50 mt-1 w-[280px] rounded-lg border border-coal-500 bg-coal-700 shadow-lg overflow-hidden",
            contentClassName,
          )}
        >
          <Command label={ariaLabel ?? placeholder} className="text-coal-50">
            <div className="flex items-center gap-2 px-3 py-2 border-b border-coal-500">
              <Search className="size-3.5 text-coal-200" aria-hidden />
              <Command.Input
                placeholder={searchPlaceholder}
                autoFocus
                className="flex-1 bg-transparent outline-none text-sm text-coal-50 placeholder:text-coal-200"
              />
            </div>
            <Command.List className="max-h-[280px] overflow-y-auto p-1">
              <Command.Empty className="px-3 py-6 text-center text-[12px] text-coal-200">
                {emptyText}
              </Command.Empty>
              {clearLabel && value && (
                <Command.Item
                  value={`__clear__ ${clearLabel}`}
                  onSelect={() => { onChange(null); setOpen(false); }}
                  className="cursor-pointer px-3 py-1.5 rounded text-[13px] text-coal-200 hover:bg-coal-500/60 data-[selected=true]:bg-coal-500/60"
                >
                  {clearLabel}
                </Command.Item>
              )}
              {items.map((it) => {
                const isSelected = it.value === value;
                return (
                  <Command.Item
                    key={it.value}
                    value={[it.value, ...(it.keywords ?? [])].join(" ")}
                    onSelect={() => { onChange(it.value); setOpen(false); }}
                    className={cn(
                      "cursor-pointer flex items-center gap-2 px-3 py-1.5 rounded text-[13px]",
                      "data-[selected=true]:bg-coal-500/60",
                      isSelected ? "text-coal-50" : "text-coal-100",
                    )}
                  >
                    <Check className={cn("size-3.5 shrink-0", isSelected ? "opacity-100 text-iri-blue" : "opacity-0")} />
                    <span className="flex-1 truncate">{it.label}</span>
                    {it.trailing && <span className="text-[11px] text-coal-200">{it.trailing}</span>}
                  </Command.Item>
                );
              })}
            </Command.List>
          </Command>
        </div>
      )}
    </div>
  );
});
