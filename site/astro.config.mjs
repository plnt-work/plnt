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
      tagline: 'Ship one agent to many customers, each isolated, on any model.',
      logo: { src: './src/assets/logo-mono.svg', replacesTitle: false },
      favicon: '/favicon.svg',
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
            { label: 'Write a bundle', slug: 'docs/guides/bundles' },
            { label: 'Tools and ToolContext', slug: 'docs/guides/tools' },
            { label: 'Config and secrets', slug: 'docs/guides/config-secrets' },
            { label: 'Guardrails and budgets', slug: 'docs/guides/guardrails' },
            { label: 'Local models', slug: 'docs/guides/local-models' },
            { label: 'Serve many customers', slug: 'docs/guides/multi-tenant' },
            { label: 'Web console', slug: 'docs/guides/console' },
            { label: 'Deploy', slug: 'docs/guides/deploy' },
          ],
        },
        {
          label: 'Reference',
          items: [
            { label: 'HTTP API', slug: 'docs/reference/http-api' },
            { label: 'Events', slug: 'docs/reference/events' },
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
