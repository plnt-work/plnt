import { useEffect, useRef, useState } from 'preact/hooks';
import type { ChatMessage, ConnectionState, DeployedModel } from './types';
import { sendChat } from './api';

interface Props {
  model: DeployedModel;
  messages: ChatMessage[];
  setMessages: (m: ChatMessage[]) => void;
  connection: ConnectionState;
  setConnection: (c: ConnectionState) => void;
}

function fmtTs(ts: number): string {
  const d = new Date(ts);
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  return `${hh}:${mm}`;
}

export default function ChatPanel({
  model,
  messages,
  setMessages,
  connection,
  setConnection,
}: Props) {
  const [draft, setDraft] = useState('');
  const [pending, setPending] = useState(false);
  const scrollerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (scrollerRef.current) {
      scrollerRef.current.scrollTop = scrollerRef.current.scrollHeight;
    }
  }, [messages.length, pending]);

  async function submit() {
    const text = draft.trim();
    if (!text || pending) return;
    const userMsg: ChatMessage = { role: 'user', content: text, ts: Date.now() };
    const next = [...messages, userMsg];
    setMessages(next);
    setDraft('');
    setPending(true);
    const res = await sendChat(model, next);
    setConnection(res.live ? 'live' : 'stub');
    setMessages([
      ...next,
      { role: 'assistant', content: res.reply, ts: Date.now() },
    ]);
    setPending(false);
  }

  return (
    <div class="pg-chat">
      <div class="pg-messages" ref={scrollerRef}>
        {messages.map((m) => (
          <div class={`pg-msg pg-msg-${m.role}`}>
            <div class="pg-msg-meta">
              <span class="pg-msg-role">
                {m.role === 'user' ? 'you' : m.role === 'system' ? 'plnt' : model.name}
              </span>
              <span class="pg-msg-ts">{fmtTs(m.ts)}</span>
            </div>
            <div class="pg-msg-body">{m.content}</div>
          </div>
        ))}
        {pending && (
          <div class="pg-msg pg-msg-assistant">
            <div class="pg-msg-meta">
              <span class="pg-msg-role">{model.name}</span>
            </div>
            <div class="pg-typing"><span /><span /><span /></div>
          </div>
        )}
      </div>

      <form
        class="pg-composer"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <textarea
          class="pg-input"
          placeholder="Message the model…"
          rows={2}
          value={draft}
          onInput={(e) => setDraft((e.currentTarget as HTMLTextAreaElement).value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              submit();
            }
          }}
          disabled={pending}
        />
        <div class="pg-composer-foot">
          <span class="pg-conn">
            <span class={`pg-dot pg-dot-${connection}`} />
            {connection === 'live' ? 'live' : connection === 'stub' ? 'stub' : 'checking'}
          </span>
          <button type="submit" class="pg-send" disabled={pending || !draft.trim()}>
            Send
          </button>
        </div>
      </form>
    </div>
  );
}
