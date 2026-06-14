// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import starlight from '@astrojs/starlight';

export default defineConfig({
  site: 'https://plnt.dev',
  integrations: [
    starlight({
      title: 'plnt docs',
      tagline: 'personal · local · native · twin',
      logo: { src: './src/assets/logo-mono.svg', replacesTitle: false },
      favicon: '/favicon.svg',
      customCss: [
        './src/styles/starlight-overrides.css',
      ],
      social: [
        { icon: 'github', label: 'GitHub', href: 'https://github.com/devdattatalele/plnt' },
      ],
      disable404Route: true,
      pagination: true,
      sidebar: [
        {
          label: 'Getting started',
          items: [
            { label: 'Install', slug: 'docs/getting-started/install' },
            { label: 'Quickstart', slug: 'docs/getting-started/quickstart' },
          ],
        },
        {
          label: 'Concepts',
          items: [
            { label: 'The four planes', slug: 'docs/concepts/four-planes' },
            { label: 'AgentSpec', slug: 'docs/concepts/agentspec' },
            { label: 'Blackboard', slug: 'docs/concepts/blackboard' },
            { label: 'Skills', slug: 'docs/concepts/skills' },
            { label: 'Sandbox ladder', slug: 'docs/concepts/sandbox-ladder' },
          ],
        },
        {
          label: 'Reference',
          items: [
            { label: 'CLI', slug: 'docs/reference/cli' },
            { label: 'HTTP API', slug: 'docs/reference/http-api' },
            { label: 'Environment variables', slug: 'docs/reference/env-vars' },
            { label: 'Events schema', slug: 'docs/reference/events-schema' },
          ],
        },
      ],
    }),
    sitemap(),
  ],
  build: {
    inlineStylesheets: 'auto',
  },
});
