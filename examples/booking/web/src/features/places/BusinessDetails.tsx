/**
 * BusinessDetails — vertical-aware "what does this place offer" section.
 *
 * Renders inside the right rail, between BusinessHeader and AgentStrip,
 * but only when the selected business has seed data for the relevant
 * field. Each chip is tappable and dispatches a real chat message via
 * onAsk — there is no decorative-only data here. If a vertical's seed
 * field is missing, the section renders nothing.
 *
 * Restaurant → menu_highlights
 * Doctor     → specialties
 * Salon      → services
 * Pharmacy   → categories
 * Gym        → classes
 */
import type { Business } from "./types";
import { metaFor } from "./verticals";

interface Props {
  business: Business;
  /** Send a free-text question into the chat. The ChatPanel envelope
   *  (biz + agent prefix) is wrapped by the parent. */
  onAsk: (text: string) => void;
}

export default function BusinessDetails({ business, onAsk }: Props) {
  const accent = metaFor(business.vertical).color;

  if (business.vertical === "restaurant" && business.menu_highlights?.length) {
    return (
      <Section title="Menu highlights" accent={accent}>
        {business.menu_highlights.map((m) => (
          <PriceChip
            key={m.name}
            label={m.name}
            sub={m.price}
            hint={m.note}
            accent={accent}
            onClick={() => onAsk(`Is ${m.name} available today?`)}
          />
        ))}
      </Section>
    );
  }

  if (business.vertical === "doctor" && business.specialties?.length) {
    return (
      <Section title="Specialties" accent={accent}>
        {business.specialties.map((s) => (
          <PlainChip
            key={s}
            label={s}
            accent={accent}
            onClick={() => onAsk(`I need a ${s} appointment — earliest slot?`)}
          />
        ))}
      </Section>
    );
  }

  if (business.vertical === "salon" && business.services?.length) {
    return (
      <Section title="Services" accent={accent}>
        {business.services.map((s) => (
          <PriceChip
            key={s.name}
            label={s.name}
            sub={s.price}
            hint={s.duration}
            accent={accent}
            onClick={() => onAsk(`Book a ${s.name} — earliest slot today.`)}
          />
        ))}
      </Section>
    );
  }

  if (business.vertical === "pharmacy" && business.categories?.length) {
    return (
      <Section title="What they stock" accent={accent}>
        {business.categories.map((c) => (
          <PlainChip
            key={c}
            label={c}
            accent={accent}
            onClick={() => onAsk(`${c} — do you have it in stock?`)}
          />
        ))}
      </Section>
    );
  }

  if (business.vertical === "gym" && business.classes?.length) {
    return (
      <Section title="Classes & passes" accent={accent}>
        {business.classes.map((c) => (
          <PlainChip
            key={c}
            label={c}
            accent={accent}
            onClick={() => onAsk(`Sign me up for ${c} — what's available this week?`)}
          />
        ))}
      </Section>
    );
  }

  return null;
}

function Section({
  title,
  accent,
  children,
}: {
  title: string;
  accent: string;
  children: React.ReactNode;
}) {
  return (
    <section className="px-4 pb-3 border-b border-paper-500/60">
      <div className="text-[11px] uppercase tracking-wide text-ink-100 mb-2 flex items-center gap-1.5">
        <span
          aria-hidden
          className="inline-block size-1.5 rounded-full"
          style={{ background: accent }}
        />
        {title}
      </div>
      <div className="flex flex-wrap gap-1.5">{children}</div>
    </section>
  );
}

function PlainChip({
  label,
  accent,
  onClick,
}: {
  label: string;
  accent: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="
        h-7 px-2.5 rounded-full text-[12px] font-medium
        border border-paper-600 bg-white text-ink-700
        hover:border-current hover:text-current transition-colors
        focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-iri-blue/40
      "
      style={{ color: "var(--color-ink-700)", ["--hover-accent" as unknown as string]: accent }}
    >
      {label}
    </button>
  );
}

function PriceChip({
  label,
  sub,
  hint,
  accent,
  onClick,
}: {
  label: string;
  sub?: string;
  hint?: string;
  accent: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={hint}
      className="
        h-auto py-1.5 px-2.5 rounded-lg text-left
        border border-paper-600 bg-white
        hover:border-current transition-colors
        focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-iri-blue/40
        flex flex-col items-start gap-0.5
      "
      style={{ color: "var(--color-ink-700)", borderColor: "var(--color-paper-600)" }}
    >
      <span className="text-[12.5px] font-medium leading-tight">{label}</span>
      {(sub || hint) && (
        <span className="text-[10.5px] text-ink-100 leading-tight" style={{ color: accent }}>
          {[sub, hint].filter(Boolean).join(" · ")}
        </span>
      )}
    </button>
  );
}
