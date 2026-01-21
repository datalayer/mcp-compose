/*
 * Copyright (c) 2025-2026 Datalayer, Inc.
 * Distributed under the terms of the Modified BSD License.
 */

/** @type {import('@docusaurus/types').DocusaurusConfig} */
module.exports = {
  title: 'Ξ MCP Compose',
  tagline: 'MCP Compose',
  url: 'https://mcp-compose.datalayer.tech',
  baseUrl: '/',
  onBrokenLinks: 'throw',
  onBrokenMarkdownLinks: 'warn',
  favicon: 'img/favicon.ico',
  organizationName: 'datalayer',
  projectName: 'datalayer',
  markdown: {
    mermaid: true,
  },
  plugins: [
    '@docusaurus/theme-live-codeblock',
    'docusaurus-lunr-search',
  ],
  themes: [
    '@docusaurus/theme-mermaid',
  ],
  themeConfig: {
    colorMode: {
      defaultMode: 'light',
      disableSwitch: true,
    },
    navbar: {
      title: 'MCP Compose',
      logo: {
        alt: 'Datalayer Logo',
        src: 'img/datalayer/logo.svg',
      },
      items: [
        {
          type: 'doc',
          docId: 'getting-started/index',
          position: 'left',
          label: 'Start',
        },
        {
          type: 'doc',
          docId: 'clients/index',
          position: 'left',
          label: 'Clients',
        },
        {
          type: 'doc',
          docId: 'configuration/index',
          position: 'left',
          label: 'Configuration',
        },
        {
          type: 'doc',
          docId: 'architecture/index',
          position: 'left',
          label: 'Architecture',
        },
        {
          type: 'doc',
          docId: 'discovery/index',
          position: 'left',
          label: 'Discovery',
        },
        {
          type: 'doc',
          docId: 'operation/index',
          position: 'left',
          label: 'Operation',
        },
        {
          type: 'doc',
          docId: 'integrations/index',
          position: 'left',
          label: 'Integrations',
        },
        {
          type: 'doc',
          docId: 'examples/index',
          position: 'left',
          label: 'Examples',
        },
        {
          type: 'doc',
          docId: 'deployment/index',
          position: 'left',
          label: 'Deployment',
        },
        {
          type: 'doc',
          docId: 'api-reference/index',
          position: 'left',
          label: 'API',
        },
        {
          type: 'doc',
          docId: 'contributing/index',
          position: 'left',
          label: 'Contributing',
        },
        {
          href: 'https://discord.gg/YQFwvmSSuR',
          position: 'right',
          className: 'header-discord-link',
          'aria-label': 'Discord',
        },
        {
          href: 'https://github.com/datalayer',
          position: 'right',
          className: 'header-github-link',
          'aria-label': 'GitHub',
        },
        {
          href: 'https://bsky.app/profile/datalayer.ai',
          position: 'right',
          className: 'header-bluesky-link',
          'aria-label': 'Bluesky',
        },
        {
          href: 'https://x.com/DatalayerIO',
          position: 'right',
          className: 'header-x-link',
          'aria-label': 'X',
        },
        {
          href: 'https://www.linkedin.com/company/datalayer',
          position: 'right',
          className: 'header-linkedin-link',
          'aria-label': 'LinkedIn',
        },
        {
          href: 'https://tiktok.com/@datalayerio',
          position: 'right',
          className: 'header-tiktok-link',
          'aria-label': 'TikTok',
        },
        {
          href: 'https://www.youtube.com/@datalayer',
          position: 'right',
          className: 'header-youtube-link',
          'aria-label': 'YouTube',
        },
        {
          href: 'https://datalayer.ai',
          position: 'right',
          className: 'header-datalayer-io-link',
          'aria-label': 'Datalayer',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Docs',
          items: [
            {
              label: 'MCP Compose',
              to: '/',
            },
          ],
        },
        {
          title: 'Community',
          items: [
            {
              label: 'GitHub',
              href: 'https://github.com/datalayer',
            },
            {
              label: 'Bluesky',
              href: 'https://assets.datalayer.tech/logos-social-grey/youtube.svg',
            },
            {
              label: 'LinkedIn',
              href: 'https://www.linkedin.com/company/datalayer',
            },
          ],
        },
        {
          title: 'More',
          items: [
            {
              label: 'Datalayer AI',
              href: 'https://datalayer.ai',
            },
            {
              label: 'Datalayer App',
              href: 'https://datalayer.app',
            },
            {
              label: 'Datalayer Docs',
              href: 'https://docs.datalayer.app',
            },
            {
              label: 'Datalayer Blog',
              href: 'https://datalayer.blog',
            },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} Datalayer, Inc.`,
    },
  },
  presets: [
    [
      '@docusaurus/preset-classic',
      {
        docs: {
          routeBasePath: '/',
          sidebarPath: require.resolve('./sidebars.js'),
          docItemComponent: '@theme/CustomDocItem',  
          editUrl: 'https://github.com/datalayer/mcp-compose/edit/main/',
        },
        theme: {
          customCss: require.resolve('./src/css/custom.css'),
        },
      },
    ],
  ],
};
