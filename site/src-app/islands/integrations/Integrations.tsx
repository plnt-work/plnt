/** @jsxImportSource preact */
import { useEffect, useState } from 'preact/hooks';
import { signal } from '@preact/signals';
import { getIntegrations, getSkill, listSkills, logout, me, setIntegration } from '../chat/api';
import type { IntegrationsMap, SkillDetail } from '../chat/types';

const skills = signal<string[]>([]);
const skillsLoaded = signal(false);
const skillCache = signal<Record<string, SkillDetail>>({});
const integrations = signal<IntegrationsMap>({});
const status = signal<{ ok: boolean; msg: string } | null>(null);

function redirectToLogin() {
  if (typeof window === 'undefined') return;
  const next = encodeURIComponent(window.location.pathname + window.location.search);
  window.location.replace(`/app/login?next=${next}`);
}

async function ensureSkill(role: string) {
  if (skillCache.value[role]) return;
  const sk = await getSkill(role);
  skillCache.value = { ...skillCache.value, [role]: sk };
}

function SkillCard({ role }: { role: string }) {
  const sk = skillCache.value[role];
  const saved = integrations.value[role] ?? {};
  const [, setTick] = useState(0);
  const [draft, setDraft] = useState<Record<string, string>>(() => {
    const o: Record<string, string> = {};
    for (const k of Object.keys(saved)) o[k] = String(saved[k]);
    return o;
  });
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!sk && open) {
      ensureSkill(role).then(() => setTick((n) => n + 1)).catch((e) => {
        status.value = { ok: false, msg: `load ${role}: ${e?.message ?? e}` };
      });
    }
  }, [role, open, sk]);

  const inputs = sk?.manifest?.requires?.inputs ?? [];
  const optional = sk?.manifest?.requires?.optional ?? [];
  const all = [
    ...inputs.map((i) => ({ name: i.name, type: i.type ?? 'string', description: i.description, example: i.example, required: true })),
    ...optional.map((i) => ({ name: i.name, type: 'string', description: i.description ?? '', example: '', required: false })),
  ];

  // Also expose any keys the user previously saved that aren't in the manifest
  // (legacy skills or freeform values).
  for (const k of Object.keys(saved)) {
    if (!all.find((a) => a.name === k)) all.push({ name: k, type: 'string', description: '(custom)', example: '', required: false });
  }

  const onSave = async () => {
    setBusy(true);
    try {
      const values: Record<string, string> = {};
      for (const [k, v] of Object.entries(draft)) {
        if (v.trim() !== '') values[k] = v;
      }
      await setIntegration(role, values);
      integrations.value = { ...integrations.value, [role]: values };
      status.value = { ok: true, msg: `saved ${Object.keys(values).length} value(s) for ${role}` };
    } catch (e: any) {
      status.value = { ok: false, msg: `save ${role}: ${e?.message ?? e}` };
    } finally {
      setBusy(false);
    }
  };

  const filled = Object.values(draft).filter((v) => v && v.trim() !== '').length;

  return (
    <article class="skill-card">
      <header onClick={() => setOpen(!open)} class="skill-card-head">
        <div>
          <h3 class="role">{role}</h3>
          {sk?.manifest?.meta?.description && (
            <p class="dim small">{sk.manifest.meta.description}</p>
          )}
        </div>
        <div class="skill-card-meta">
          {filled > 0 && <span class="pill ok mono">{filled} set</span>}
          {sk && <span class="pill mono dim">{sk.model_hint}</span>}
          <span class="caret">{open ? '−' : '+'}</span>
        </div>
      </header>
      {open && (
        <div class="skill-card-body">
          {!sk && <p class="dim">Loading manifest…</p>}
          {sk && all.length === 0 && (
            <p class="dim">This skill declares no [requires.inputs] in skill.toml. Add one to expose configurable values here.</p>
          )}
          {sk && all.length > 0 && (
            <form class="integration-form" onSubmit={(ev) => { ev.preventDefault(); void onSave(); }}>
              {all.map((field) => (
                <label class="field" key={field.name}>
                  <span class="field-head">
                    <strong class="mono">{field.name}</strong>
                    <span class="dim mono small">{field.type}{field.required ? ' · required' : ''}</span>
                  </span>
                  {field.description && <span class="dim small">{field.description}</span>}
                  <input
                    type="text"
                    value={draft[field.name] ?? ''}
                    placeholder={field.example || ''}
                    onInput={(e) => setDraft({ ...draft, [field.name]: (e.currentTarget as HTMLInputElement).value })}
                  />
                </label>
              ))}
              <div class="field-actions">
                <button class="btn primary compact" type="submit" disabled={busy}>
                  {busy ? 'saving…' : 'save'}
                </button>
              </div>
            </form>
          )}
        </div>
      )}
    </article>
  );
}

export default function Integrations() {
  const [authed, setAuthed] = useState<null | boolean>(null);
  const [user, setUser] = useState<string | null>(null);

  useEffect(() => {
    me().then((r) => {
      setAuthed(r.authenticated);
      setUser(r.username ?? null);
      if (!r.authenticated) { redirectToLogin(); return; }
      Promise.all([listSkills(), getIntegrations()])
        .then(([sk, ints]) => {
          skills.value = sk.skills;
          integrations.value = ints.integrations || {};
          skillsLoaded.value = true;
        })
        .catch((e) => { status.value = { ok: false, msg: String(e?.message ?? e) }; });
    }).catch(() => { setAuthed(false); redirectToLogin(); });
  }, []);

  if (authed === null) return <p class="dim center">Loading…</p>;
  if (!authed) return <p class="dim center">Redirecting…</p>;

  return (
    <div class="chat-app">
      <nav class="app-nav">
        <a href="/app/" class="brand">
          <span class="logomark">×</span>
          <span class="brandname">plnt</span>
        </a>
        <div class="links">
          <a href="/app/">Chat</a>
          <a href="/app/integrations" class="active">Integrations</a>
          <span class="dim small">{user ?? ''}</span>
          <button class="btn compact" onClick={async () => { await logout(); redirectToLogin(); }}>
            Sign out
          </button>
        </div>
      </nav>

      <main class="integrations-main">
        <header class="integrations-head">
          <span class="kicker">INTEGRATIONS</span>
          <h1>Saved skill inputs</h1>
          <p class="lead">
            Values configured here are folded into <code>AgentSpec.inputs</code> at spawn time
            for the matching skill. Planner-supplied values take precedence — these only fill
            blanks. Persisted to <code>~/.plnt/integrations.toml</code>.
          </p>
        </header>

        {status.value && (
          <div class={`flash ${status.value.ok ? 'flash-ok' : 'flash-err'}`}>
            {status.value.msg}
            <button class="btn compact" onClick={() => { status.value = null; }}>dismiss</button>
          </div>
        )}

        {!skillsLoaded.value && <p class="dim">Loading skills…</p>}
        {skillsLoaded.value && skills.value.length === 0 && (
          <p class="dim">No skills installed in <code>~/.plnt/skills/</code>. Install one with <code>plnt skills install anthropic</code>.</p>
        )}

        <section class="skill-list">
          {skills.value.map((role) => <SkillCard key={role} role={role} />)}
        </section>
      </main>
    </div>
  );
}
