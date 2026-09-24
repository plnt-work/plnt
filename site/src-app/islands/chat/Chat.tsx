/** @jsxImportSource preact */
import { useEffect, useState } from 'preact/hooks';
import Composer from './Composer';
import AgentList from './AgentList';
import AgentDrawer from './AgentDrawer';
import Parent from './Parent';
import { applyEvent, startRun, history } from './state';
import { AuthError, me, submitIntent, streamRun, logout } from './api';

export default function Chat() {
  const [authed, setAuthed] = useState<null | boolean>(null);
  const [user, setUser] = useState<string | null>(null);

  useEffect(() => {
    me().then((r) => {
      setAuthed(r.authenticated);
      setUser(r.username ?? null);
      if (!r.authenticated) redirectToLogin();
    }).catch(() => {
      setAuthed(false);
      redirectToLogin();
    });
  }, []);

  const onSubmit = async (text: string) => {
    try {
      const turns = history.value.map((t) => ({ runId: t.runId, prompt: t.prompt, answer: t.answer })).slice(-6);
      const res = await submitIntent(text, turns);
      startRun(res.run_id, text);
      streamRun(
        res.run_id,
        (e) => applyEvent(e),
        () => { /* run-level finished; composerBusy is cleared in applyEvent */ },
        () => redirectToLogin(),
      );
    } catch (err) {
      if (err instanceof AuthError) {
        redirectToLogin();
        return;
      }
      console.error(err);
      alert(`submit failed: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  if (authed === null) return <p class="dim center">Loading…</p>;
  if (!authed) return <p class="dim center">Redirecting to login…</p>;

  return (
    <div class="chat-app">
      <nav class="app-nav">
        <a href="/app/" class="brand">
          <span class="logomark">×</span>
          <span class="brandname">plnt</span>
        </a>
        <div class="links">
          <a href="/app/" class="active">Chat</a>
          <a href="/app/integrations">Integrations</a>
          <span class="dim small">{user ?? ''}</span>
          <button class="btn compact" onClick={async () => { await logout(); redirectToLogin(); }}>
            Sign out
          </button>
        </div>
      </nav>

      <main class="chat-grid">
        <Parent />
        <AgentList />
      </main>

      <footer class="composer-bar">
        <Composer onSubmit={onSubmit} />
      </footer>

      <AgentDrawer />
    </div>
  );
}

function redirectToLogin() {
  if (typeof window === 'undefined') return;
  const next = encodeURIComponent(window.location.pathname + window.location.search);
  window.location.replace(`/app/login?next=${next}`);
}
