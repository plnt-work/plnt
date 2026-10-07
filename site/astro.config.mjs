// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import starlight from '@astrojs/starlight';
import preact from '@astrojs/preact';

export default defineConfig({
  site: 'https://plnt.work',
  integrations: [
    preact({ compat: false }),
    starlight({
      title: 'plnt docs',
      tagline: 'A task in, micro-agents out. Every step on the record.',
      logo: { src: './src/assets/logo.svg', replacesTitle: false },
      favicon: '/favicon.svg',
      head: [
        { tag: 'meta', attrs: { name: 'theme-color', content: '#f7f6f2' } },
        { tag: 'link', attrs: { rel: 'icon', type: 'image/png', sizes: '32x32', href: '/favicon-32.png' } },
        { tag: 'link', attrs: { rel: 'apple-touch-icon', href: '/apple-touch-icon.png' } },
        { tag: 'meta', attrs: { property: 'og:image', content: 'https://plnt.work/og.png' } },
        { tag: 'meta', attrs: { property: 'og:image:width', content: '1200' } },
        { tag: 'meta', attrs: { property: 'og:image:height', content: '630' } },
        { tag: 'meta', attrs: { name: 'twitter:card', content: 'summary_large_image' } },
        { tag: 'meta', attrs: { name: 'twitter:image', content: 'https://plnt.work/og.png' } },
      ],
      customCss: ['./src/styles/starlight-overrides.css'],
      social: [{ icon: 'github', label: 'GitHub', href: 'https://github.com/plnt-work/plnt' }],
      editLink: { baseUrl: 'https://github.com/plnt-work/plnt/edit/main/site/' },
      disable404Route: true,
      pagination: true,
      sidebar: [
        {
          label: 'Getting started',
          items: [
            { label: 'What plnt is', slug: 'docs' },
            { label: 'Quickstart', slug: 'docs/getting-started/quickstart' },
            { label: 'Concepts', slug: 'docs/getting-started/concepts' },
          ],
        },
        {
          label: 'Guides',
          items: [
            { label: 'The parent and its agents', slug: 'docs/guides/parent' },
            { label: 'Workspaces', slug: 'docs/guides/workspaces' },
            { label: 'The shipped developer bundles', slug: 'docs/guides/dev-bundles' },
            { label: 'Write a bundle', slug: 'docs/guides/bundles' },
            { label: 'Tools and ToolContext', slug: 'docs/guides/tools' },
            { label: 'Config and secrets', slug: 'docs/guides/config-secrets' },
            { label: 'Guardrails and budgets', slug: 'docs/guides/guardrails' },
            { label: 'Local models', slug: 'docs/guides/local-models' },
            { label: 'Serve many tenants', slug: 'docs/guides/multi-tenant' },
            { label: 'Web console', slug: 'docs/guides/console' },
            { label: 'Deploy', slug: 'docs/guides/deploy' },
          ],
        },
        {
          label: 'Reference',
          items: [
            { label: 'HTTP API', slug: 'docs/reference/http-api' },
            { label: 'Events', slug: 'docs/reference/events' },
            { label: 'Transcript', slug: 'docs/reference/transcript' },
            { label: 'skill.toml', slug: 'docs/reference/skill-toml' },
            { label: 'CLI', slug: 'docs/reference/cli' },
            { label: 'Environment variables', slug: 'docs/reference/env' },
          ],
        },
      ],
    }),
    sitemap(),
  ],
  build: { inlineStylesheets: 'auto' },
});
