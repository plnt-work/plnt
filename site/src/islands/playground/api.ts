import type { ChatMessage, DeployedModel } from './types';

const ENV_ENDPOINT =
  (typeof import.meta !== 'undefined' && (import.meta as any).env?.PUBLIC_PLNT_ENDPOINT) || '';

// Default to the deployed backend in production if no explicit override was set.
const DEFAULT_ENDPOINT = 'https://playground.plnt.work';

const ENDPOINT = ENV_ENDPOINT || DEFAULT_ENDPOINT;

const STUB_REPLIES: Record<string, string[]> = {
  vllm: [
    'Running on vLLM — paged attention, prefix cache active. This is a stub reply; wire PUBLIC_PLNT_ENDPOINT to a live vllm-runtime deployment to see the real model.',
    'Stub mode. vLLM would stream tokens here via /v1/chat/completions with stream=true. First-token latency on a warm 2×H100 for a 70B model typically sits around 150–200ms.',
  ],
  tgi: [
    'Running on TGI — continuous batching, flash attention 2. Stub reply. Point PUBLIC_PLNT_ENDPOINT at the tgi-runtime service to talk to the real model.',
  ],
  'trt-llm': [
    'Running on TRT-LLM — precompiled Triton engine, TP=4. Stub reply. Wire a live endpoint to exercise the real inference path.',
  ],
  sglang: [
    'Running on SGLang — RadixAttention prefix caching. Stub reply. Point the endpoint env var at the sglang-runtime service to go live.',
  ],
};

let stubIndex = 0;

function stubReply(model: DeployedModel): string {
  const pool = STUB_REPLIES[model.runtime] || ['Stub reply. No live endpoint configured.'];
  const r = pool[stubIndex % pool.length];
  stubIndex += 1;
  return r;
}

export function currentEndpoint(): string {
  return ENDPOINT;
}

export interface ChatResult {
  reply: string;
  live: boolean;
  latencyMs: number;
}

export async function sendChat(
  model: DeployedModel,
  history: ChatMessage[],
): Promise<ChatResult> {
  const start = performance.now();
  const url = `${ENDPOINT.replace(/\/$/, '')}/v1/chat/completions`;
  const body = {
    model: model.id,
    messages: history
      .filter((m) => m.role !== 'system' || m.content)
      .map(({ role, content }) => ({ role, content })),
    stream: false,
  };

  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const reply =
      data?.choices?.[0]?.message?.content ??
      data?.choices?.[0]?.text ??
      '(empty response)';
    return { reply, live: true, latencyMs: performance.now() - start };
  } catch {
    // Backend unreachable or errored — degrade to a canned stub reply so the UI keeps working.
    await new Promise((res) => setTimeout(res, 250));
    return { reply: stubReply(model), live: false, latencyMs: performance.now() - start };
  }
}

export interface LiveModel {
  id: string;
  ownedBy?: string;
}

export async function fetchLiveModels(): Promise<LiveModel[] | null> {
  try {
    const res = await fetch(`${ENDPOINT.replace(/\/$/, '')}/v1/models`, {
      method: 'GET',
      headers: { accept: 'application/json' },
    });
    if (!res.ok) return null;
    const data = await res.json();
    const items = Array.isArray(data?.data) ? data.data : [];
    return items.map((m: any) => ({ id: String(m.id), ownedBy: m.owned_by }));
  } catch {
    return null;
  }
}
