// Typed API client. Every component-facing call goes through a wrapper
// here, not a raw fetch (HDGEcalls isMeResponse pattern). Zod parses
// the response so a backend shape drift fails loudly at the boundary
// instead of NaN-ing a UI three frames later.
import { z } from "zod";
import { env } from "@/lib/env";

class ApiError extends Error {
  constructor(public status: number, public path: string, msg: string) {
    super(`[api ${status}] ${path}: ${msg}`);
  }
}

export async function apiGet<T>(path: string, schema: z.ZodType<T>): Promise<T> {
  const url = `${env.apiBase.replace(/\/$/, "")}${path}`;
  const res = await fetch(url, {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new ApiError(res.status, path, await res.text().catch(() => ""));
  }
  const json = await res.json();
  const parsed = schema.safeParse(json);
  if (!parsed.success) {
    throw new ApiError(
      res.status,
      path,
      `schema mismatch: ${parsed.error.message}`,
    );
  }
  return parsed.data;
}

export { ApiError };
