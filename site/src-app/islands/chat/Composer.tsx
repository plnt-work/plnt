/** @jsxImportSource preact */
import { useEffect, useRef } from 'preact/hooks';
import { signal } from '@preact/signals';
import { composerBusy } from './state';

const draft = signal<string>('');

interface Props {
  onSubmit: (text: string) => void | Promise<void>;
}

export default function Composer({ onSubmit }: Props) {
  const taRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!composerBusy.value && taRef.current) taRef.current.focus();
  });

  const send = async () => {
    const text = draft.value.trim();
    if (!text || composerBusy.value) return;
    draft.value = '';
    if (taRef.current) taRef.current.style.height = '';
    await onSubmit(text);
  };

  const onKey = (ev: KeyboardEvent) => {
    if ((ev.metaKey || ev.ctrlKey) && ev.key === 'Enter') {
      ev.preventDefault();
      void send();
    }
  };

  const autoSize = (ev: Event) => {
    const ta = ev.currentTarget as HTMLTextAreaElement;
    draft.value = ta.value;
    ta.style.height = 'auto';
    ta.style.height = `${Math.min(ta.scrollHeight, 320)}px`;
  };

  return (
    <div class="composer">
      <span class="prompt">›</span>
      <textarea
        ref={taRef}
        class="composer-input"
        rows={1}
        placeholder='ask plnt — e.g. "find anything on agent memory in my Documents"'
        value={draft.value}
        onInput={autoSize}
        onKeyDown={onKey}
        disabled={composerBusy.value}
        aria-label="message"
      />
      <button
        type="button"
        class="btn primary compact"
        onClick={() => void send()}
        disabled={composerBusy.value || !draft.value.trim()}
      >
        {composerBusy.value ? 'running' : 'send'} <span class="kbd">⌘⏎</span>
      </button>
    </div>
  );
}
