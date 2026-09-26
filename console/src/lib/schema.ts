import type { JsonSchema } from "./api";

/** Config with schema defaults applied — the starting point for a new install. */
export function withDefaults(schema: JsonSchema | null, value: Record<string, unknown> = {}): Record<string, unknown> {
  const out: Record<string, unknown> = { ...value };
  for (const [k, p] of Object.entries(schema?.properties ?? {})) {
    if (out[k] === undefined && p.default !== undefined) out[k] = structuredClone(p.default);
  }
  return out;
}


/** Drop list rows the user added but left completely blank before saving. */
export function pruneBlankRows(schema: JsonSchema | null, value: Record<string, unknown>) {
  const out: Record<string, unknown> = { ...value };
  for (const [k, p] of Object.entries(schema?.properties ?? {})) {
    const v = out[k];
    if (p.type === "array" && Array.isArray(v)) {
      out[k] = v.filter((row) =>
        row && typeof row === "object"
          ? Object.values(row as Record<string, unknown>).some((x) => String(x ?? "").trim() !== "")
          : String(row ?? "").trim() !== "");
    }
  }
  return out;
}
