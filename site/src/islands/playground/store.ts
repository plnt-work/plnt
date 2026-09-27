// Visitors' sessions, remembered per browser. Tokens die with the server, so
// a session that 404s is marked expired and only its title is kept.
export type Stored = {
  session_id: string;
  token: string;
  tenant: string;
  workspace: string;
  bundle: string;
  title: string;
  created: number;
  expired?: boolean;
};

const KEY = 'plnt.playground.sessions';

export function loadSessions(): Stored[] {
  try {
    const raw = localStorage.getItem(KEY);
    const list = raw ? (JSON.parse(raw) as Stored[]) : [];
    return Array.isArray(list) ? list : [];
  } catch {
    return [];
  }
}

export function saveSessions(list: Stored[]): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(list.slice(0, 30)));
  } catch {
    /* private mode: sessions live for this page load only */
  }
}
