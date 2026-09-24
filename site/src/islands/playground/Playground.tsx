import { useEffect, useState } from 'preact/hooks';
import type { ChatMessage, ConnectionState, Quantization } from './types';
import { MODELS, RUNTIME_LABEL } from './models';
import { fetchLiveModels } from './api';
import Sidebar from './Sidebar';
import MainPane from './MainPane';

function welcomeMessage(name: string, runtime: string): ChatMessage {
  return {
    role: 'system',
    ts: Date.now(),
    content:
      `Welcome. You're connected to ${name} on ${runtime}. ` +
      `This endpoint is OpenAI-compatible — /v1/chat/completions with streaming. ` +
      `Ask anything; the model has no persistent memory across sessions in this playground.`,
  };
}

export default function Playground() {
  const [modelId, setModelId] = useState(MODELS[0].id);
  const model = MODELS.find((m) => m.id === modelId) ?? MODELS[0];
  const [variant, setVariant] = useState<Quantization>(model.defaultVariant);
  const [messages, setMessages] = useState<ChatMessage[]>([
    welcomeMessage(model.name, RUNTIME_LABEL[model.runtime]),
  ]);
  const [connection, setConnection] = useState<ConnectionState>('checking');
  const [sessionStartedAt, setSessionStartedAt] = useState<number>(Date.now());

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const live = await fetchLiveModels();
      if (cancelled) return;
      setConnection(live && live.length > 0 ? 'live' : 'stub');
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  function selectModel(id: string) {
    const next = MODELS.find((m) => m.id === id) ?? MODELS[0];
    setModelId(next.id);
    setVariant(next.defaultVariant);
    setMessages([welcomeMessage(next.name, RUNTIME_LABEL[next.runtime])]);
    setSessionStartedAt(Date.now());
  }

  function restart() {
    setMessages([welcomeMessage(model.name, RUNTIME_LABEL[model.runtime])]);
    setSessionStartedAt(Date.now());
  }

  return (
    <div class="pg-shell">
      <Sidebar
        model={model}
        variant={variant}
        onSelectModel={selectModel}
        onSelectVariant={setVariant}
        onStart={restart}
      />
      <MainPane
        model={model}
        messages={messages}
        setMessages={setMessages}
        connection={connection}
        setConnection={setConnection}
        sessionStartedAt={sessionStartedAt}
        onRestart={restart}
      />
    </div>
  );
}
