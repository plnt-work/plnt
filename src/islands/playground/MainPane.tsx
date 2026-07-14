import { useEffect, useState } from 'preact/hooks';
import type { ChatMessage, ConnectionState, DeployedModel } from './types';
import { RUNTIME_LABEL } from './models';
import ChatPanel from './ChatPanel';

type Tab = 'briefing' | 'chat' | 'metrics' | 'manifest' | 'logs';

interface Props {
  model: DeployedModel;
  messages: ChatMessage[];
  setMessages: (m: ChatMessage[]) => void;
  connection: ConnectionState;
  setConnection: (c: ConnectionState) => void;
  sessionStartedAt: number;
  onRestart: () => void;
}

const TABS: { id: Tab; label: string }[] = [
  { id: 'briefing', label: 'Briefing' },
  { id: 'chat', label: 'Chat' },
  { id: 'metrics', label: 'Metrics' },
  { id: 'manifest', label: 'Manifest' },
  { id: 'logs', label: 'Logs' },
];

function fmtElapsed(ms: number): string {
  const total = Math.floor(ms / 1000);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

export default function MainPane({
  model,
  messages,
  setMessages,
  connection,
  setConnection,
  sessionStartedAt,
  onRestart,
}: Props) {
  const [tab, setTab] = useState<Tab>('chat');
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  const userMessages = messages.filter((m) => m.role === 'user').length;

  return (
    <section class="pg-main">
      <header class="pg-header">
        <div>
          <h1 class="pg-title">{model.name}</h1>
          <p class="pg-header-desc">{model.description}</p>
        </div>
        <div class="pg-header-right">
          <span class="pg-stat">{userMessages} msg</span>
          <span class="pg-stat">{fmtElapsed(now - sessionStartedAt)}</span>
          <button class="pg-restart" onClick={onRestart}>Restart</button>
        </div>
      </header>

      <nav class="pg-tabs" role="tablist">
        {TABS.map((t) => (
          <button
            role="tab"
            class={`pg-tab ${tab === t.id ? 'pg-tab-active' : ''}`}
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <div class="pg-body">
        {tab === 'briefing' && <BriefingTab model={model} />}
        {tab === 'chat' && (
          <ChatPanel
            model={model}
            messages={messages}
            setMessages={setMessages}
            connection={connection}
            setConnection={setConnection}
          />
        )}
        {tab === 'metrics' && <MetricsTab />}
        {tab === 'manifest' && <ManifestTab model={model} />}
        {tab === 'logs' && <LogsTab />}
      </div>
    </section>
  );
}

function BriefingTab({ model }: { model: DeployedModel }) {
  return (
    <div class="pg-prose">
      <p>{model.briefing}</p>
      <dl class="pg-brief-list">
        <div><dt>Runtime</dt><dd>{RUNTIME_LABEL[model.runtime]}</dd></div>
        <div><dt>Chart</dt><dd>{model.chartVersion}</dd></div>
        <div><dt>Parameters</dt><dd>{model.params}</dd></div>
        <div><dt>Context</dt><dd>{model.contextLength}</dd></div>
        <div><dt>License</dt><dd>{model.license}</dd></div>
        <div><dt>GPU</dt><dd>{model.gpu}</dd></div>
        <div><dt>Replicas</dt><dd>{model.replicas}</dd></div>
        <div><dt>Endpoint</dt><dd class="pg-mono">{model.endpoint}</dd></div>
      </dl>
    </div>
  );
}

function MetricsTab() {
  return (
    <div class="pg-prose">
      <p>
        No live metrics scrape configured for this instance. A production plnt
        deployment exposes <code>/metrics</code> in Prometheus format — TTFT p50/p95/p99,
        TPOT, tokens/sec/GPU, KV cache utilization, and per-runtime batch fill.
      </p>
      <p class="pg-dim">Wire a Grafana datasource to plnt-prometheus.svc to render panels here.</p>
    </div>
  );
}

function ManifestTab({ model }: { model: DeployedModel }) {
  return (
    <div class="pg-prose">
      <div class="pg-label">InferenceModel</div>
      <pre class="pg-code">{model.manifest}</pre>
      <div class="pg-label pg-mt">Helm values (excerpt)</div>
      <pre class="pg-code">{model.values}</pre>
    </div>
  );
}

function LogsTab() {
  return (
    <div class="pg-prose">
      <p>
        No workflow runs recorded. In a live deployment this streams events from
        the Temporal deploy saga
        (<code>validate → pull_weights → helm_install → smoke → promote</code>)
        plus per-request logs from the runtime.
      </p>
    </div>
  );
}
