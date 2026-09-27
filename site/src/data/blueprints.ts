// Use cases ("blueprints"): what a parent session does for a given kind of
// task, which agents it spawns, and how far along plnt is for it.
export type Category = 'Coding' | 'Research' | 'Ops' | 'Multi-agent';
export type Status = 'ships' | 'bundle' | 'roadmap';

export type Blueprint = {
  slug: string;
  title: string;
  category: Category;
  summary: string;
  agents: string[];
  status: Status;
  /** A playground preset, when the shipped demo covers it. */
  playground?: { tenant: string; task: string };
  docs?: string;
};

export const CATEGORIES: Category[] = ['Coding', 'Research', 'Ops', 'Multi-agent'];

export const STATUS_LABEL: Record<Status, string> = {
  ships: 'ships today',
  bundle: 'with your bundle',
  roadmap: 'roadmap',
};

export const BLUEPRINTS: Blueprint[] = [
  {
    slug: 'repo-audit',
    title: 'Repo audit',
    category: 'Coding',
    summary: 'Point the parent at a repository and ask what is wrong with it. It spawns a reviewer per concern and merges the findings with path:line citations.',
    agents: ['code-reviewer', 'repo-explainer'],
    status: 'ships',
    playground: { tenant: 'notes-api', task: 'Audit app/store.py and app/main.py for bugs.' },
  },
  {
    slug: 'test-writing',
    title: 'Test writing',
    category: 'Coding',
    summary: 'A reviewer finds the behaviour worth pinning down; the test writer, which depends on it, writes the tests in the project’s own framework and runs them when allowed.',
    agents: ['code-reviewer', 'test-writer'],
    status: 'ships',
    playground: { tenant: 'notes-api', task: 'Write tests for the notes store.' },
  },
  {
    slug: 'explain-codebase',
    title: 'Explain a codebase',
    category: 'Coding',
    summary: 'For a new contributor, a reviewer or a manager: layout, entry points, the main flow, how to run it, what looks unfinished. Always from files it read.',
    agents: ['repo-explainer'],
    status: 'ships',
    playground: { tenant: 'cli-tool', task: 'What does this tool do and how do I run it?' },
  },
  {
    slug: 'changelog',
    title: 'Changelog and release notes',
    category: 'Coding',
    summary: 'From git history where the agent may run git, or from the code itself where it may not. Grouped as Added / Changed / Fixed, ready to paste.',
    agents: ['changelog-writer'],
    status: 'ships',
    playground: { tenant: 'cli-tool', task: 'Review todo/cli.py for style and write release notes for 1.2.0.' },
  },
  {
    slug: 'code-review-pr',
    title: 'Review a pull request',
    category: 'Coding',
    summary: 'Clone the branch as the session’s workspace, review the diff by module in parallel, and post one merged review. Needs a bundle that knows your review rules.',
    agents: ['code-reviewer', 'your review bundle'],
    status: 'bundle',
    docs: '/docs/guides/workspaces/',
  },
  {
    slug: 'dependency-upgrade',
    title: 'Dependency upgrade',
    category: 'Coding',
    summary: 'Read the lockfile and the changelog of the new version, find every call site that changes, write the patch and run the tests. Needs execute on the workspace.',
    agents: ['repo-explainer', 'invented roles', 'test-writer'],
    status: 'bundle',
    docs: '/docs/guides/parent/',
  },
  {
    slug: 'research-brief',
    title: 'Research brief',
    category: 'Research',
    summary: 'Split a question into sub-questions, one reader per source folder, one writer that depends on all of them. Works today on documents in the workspace; the web needs your own fetch tool.',
    agents: ['invented roles', 'your reader bundle'],
    status: 'bundle',
    docs: '/docs/guides/tools/',
  },
  {
    slug: 'compare-options',
    title: 'Compare options',
    category: 'Research',
    summary: 'Vendors, libraries, designs: one agent per option reads its material, a comparer merges them into a table with the trade-offs the user asked about.',
    agents: ['invented roles'],
    status: 'bundle',
    docs: '/docs/guides/parent/',
  },
  {
    slug: 'incident-triage',
    title: 'Incident triage',
    category: 'Ops',
    summary: 'Drop the logs and the runbook into a workspace. A log reader, a runbook matcher and a summariser run in parallel; the reply says what happened and what to do next.',
    agents: ['invented roles', 'your log bundle'],
    status: 'bundle',
    docs: '/docs/guides/dev-bundles/',
  },
  {
    slug: 'data-pipeline-check',
    title: 'Data pipeline check',
    category: 'Ops',
    summary: 'Read the pipeline code and a sample of its output, and report where the two disagree. Read-only by default, so it is safe to run on a schedule.',
    agents: ['code-reviewer', 'invented roles'],
    status: 'bundle',
    docs: '/docs/guides/guardrails/',
  },
  {
    slug: 'many-repos',
    title: 'One task across many repos',
    category: 'Multi-agent',
    summary: 'The same task on every repository a team owns, one session each, isolated, with usage and audit per tenant. The console shows every run side by side.',
    agents: ['any bundle'],
    status: 'ships',
    docs: '/docs/guides/multi-tenant/',
  },
  {
    slug: 'nested-parents',
    title: 'Agents that spawn agents',
    category: 'Multi-agent',
    summary: 'Today one parent spawns up to four agents per message in dependency order. Deeper trees, where an agent can itself plan and spawn, are on the roadmap.',
    agents: ['parent', 'sub-parents'],
    status: 'roadmap',
    docs: 'https://github.com/plnt-work/plnt/blob/main/ROADMAP.md',
  },
];
