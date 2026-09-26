import { Plus, Trash2 } from "lucide-react";
import type { JsonSchema } from "@/lib/api";
import { Button, Field } from "./ui";
import { inputClass } from "@/lib/format";

// Renders a form for a bundle's config_schema. Covers what bundle configs
// actually use: strings (incl. enums), numbers, booleans, arrays of strings,
// arrays of flat objects (e.g. FAQ q/a pairs). Anything else falls back to a
// JSON textarea so no schema is ever un-editable.

type Value = Record<string, unknown>;

function typeOf(s: JsonSchema): string {
  const t = Array.isArray(s.type) ? s.type.find((x) => x !== "null") : s.type;
  if (t) return t;
  if (s.enum) return "string";
  return "object";
}

function label(key: string, s: JsonSchema): string {
  return s.title ?? key.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

export function SchemaForm({ schema, value, onChange }: {
  schema: JsonSchema | null;
  value: Value;
  onChange: (v: Value) => void;
}) {
  const props = Object.entries(schema?.properties ?? {});
  if (!props.length) {
    return <p className="text-[13px] text-muted">This agent has no settings.</p>;
  }
  const required = new Set(schema?.required ?? []);
  const set = (k: string, v: unknown) => onChange({ ...value, [k]: v });
  return (
    <div className="space-y-4">
      {props.map(([key, s]) => (
        <PropField key={key} name={key} schema={s} required={required.has(key)}
                   value={value[key]} onChange={(v) => set(key, v)} />
      ))}
    </div>
  );
}

function PropField({ name, schema, required, value, onChange }: {
  name: string;
  schema: JsonSchema;
  required: boolean;
  value: unknown;
  onChange: (v: unknown) => void;
}) {
  const t = typeOf(schema);
  const common = { label: label(name, schema), hint: schema.description, required };

  if (schema.enum) {
    return (
      <Field {...common}>
        <select className={inputClass} value={String(value ?? "")}
                onChange={(e) => onChange(e.target.value)}>
          {!required && <option value="">—</option>}
          {schema.enum.map((o) => <option key={String(o)} value={String(o)}>{String(o)}</option>)}
        </select>
      </Field>
    );
  }
  if (t === "boolean") {
    return (
      <label className="flex items-center gap-2 text-[13px]">
        <input type="checkbox" checked={Boolean(value)} onChange={(e) => onChange(e.target.checked)} />
        {common.label}
        {schema.description && <span className="text-muted">— {schema.description}</span>}
      </label>
    );
  }
  if (t === "number" || t === "integer") {
    return (
      <Field {...common}>
        <input type="number" className={inputClass} value={value === undefined ? "" : String(value)}
               step={t === "integer" ? 1 : "any"}
               onChange={(e) => onChange(e.target.value === "" ? undefined : Number(e.target.value))} />
      </Field>
    );
  }
  if (t === "string") {
    return (
      <Field {...common}>
        <input className={inputClass} value={String(value ?? "")}
               onChange={(e) => onChange(e.target.value)} />
      </Field>
    );
  }
  if (t === "array" && schema.items && typeOf(schema.items) === "object" && schema.items.properties) {
    return <ObjectList {...common} schema={schema.items}
                       value={Array.isArray(value) ? (value as Value[]) : []} onChange={onChange} />;
  }
  if (t === "array" && schema.items && typeOf(schema.items) === "string") {
    const lines = Array.isArray(value) ? (value as string[]).join("\n") : "";
    return (
      <Field {...common} hint={[schema.description, "One per line."].filter(Boolean).join(" ")}>
        <textarea className={`${inputClass} h-24 py-1.5`} value={lines}
                  onChange={(e) => onChange(e.target.value.split("\n").filter((l) => l.trim()))} />
      </Field>
    );
  }
  return <JsonField {...common} value={value} onChange={onChange} />;
}

function ObjectList({ label: title, hint, required, schema, value, onChange }: {
  label: string;
  hint?: string;
  required: boolean;
  schema: JsonSchema;
  value: Value[];
  onChange: (v: Value[]) => void;
}) {
  const cols = Object.entries(schema.properties ?? {});
  const update = (i: number, k: string, v: unknown) =>
    onChange(value.map((row, j) => (j === i ? { ...row, [k]: v } : row)));
  return (
    <fieldset className="space-y-2">
      <legend className="text-[12px] font-medium">
        {title}
        {required && <span className="text-danger"> *</span>}
      </legend>
      {hint && <p className="text-[12px] text-muted">{hint}</p>}
      {value.map((row, i) => (
        <div key={i} className="flex items-start gap-2 rounded-md border border-line p-2">
          <div className="grid flex-1 gap-2">
            {cols.map(([k, s]) => (
              <input key={k} className={inputClass} placeholder={label(k, s)}
                     aria-label={`${label(k, s)} ${i + 1}`} value={String(row[k] ?? "")}
                     onChange={(e) => update(i, k, e.target.value)} />
            ))}
          </div>
          <Button variant="ghost" aria-label="Remove row"
                  onClick={() => onChange(value.filter((_, j) => j !== i))}>
            <Trash2 className="size-3.5" />
          </Button>
        </div>
      ))}
      <Button onClick={() => onChange([...value, Object.fromEntries(cols.map(([k]) => [k, ""]))])}>
        <Plus className="size-3.5" /> Add
      </Button>
    </fieldset>
  );
}

function JsonField({ label: title, hint, required, value, onChange }: {
  label: string;
  hint?: string;
  required: boolean;
  value: unknown;
  onChange: (v: unknown) => void;
}) {
  return (
    <Field label={title} hint={hint ?? "JSON"} required={required}>
      <textarea
        className={`${inputClass} h-28 py-1.5 font-mono text-[12px]`}
        defaultValue={value === undefined ? "" : JSON.stringify(value, null, 2)}
        onBlur={(e) => {
          try {
            onChange(e.target.value.trim() ? JSON.parse(e.target.value) : undefined);
          } catch {
            /* keep last valid value; the server validates on save */
          }
        }}
      />
    </Field>
  );
}
