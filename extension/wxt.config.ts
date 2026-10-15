import { defineConfig } from 'wxt';

// See https://wxt.dev/api/config.html
export default defineConfig({
  modules: ['@wxt-dev/module-react'],
  // MV3 everywhere: Firefox would default to MV2, where `browser.action` doesn't exist.
  manifestVersion: 3,
  manifest: ({ browser }) => ({
    name: 'Primora',
    description: 'Logs your internship applications when you submit them, and keeps the promising ones on top.',
    // storage: session + queued logs; activeTab: prefill "I applied"; identity: Google sign-in.
    permissions: ['storage', 'activeTab', 'identity'],
    // Public job-board APIs, used to clean up company / role names after a submit.
    host_permissions: ['https://boards-api.greenhouse.io/*', 'https://api.ashbyhq.com/*'],
    ...(browser === 'firefox' && {
      // Primrose outline: light ink on dark toolbars (Firefox only; Chrome has no equivalent).
      action: {
        theme_icons: [16, 32, 48, 96, 128].map((size) => ({
          light: `icon/light-${size}.png`,
          dark: `icon/${size}.png`,
          size,
        })),
      },
      browser_specific_settings: {
        gecko: {
          // Fixed ID: Firefox MV3 requires one, and it keeps the identity redirect URL stable.
          id: 'primora@primora.app',
          strict_min_version: '142.0',
          data_collection_permissions: {
            required: ['authenticationInfo', 'personallyIdentifyingInfo', 'websiteActivity'],
          },
        },
      },
    }),
  }),
  zip: {
    // AMO rebuilds from the sources zip, and the build imports ../shared, so zip from the repo root.
    sourcesRoot: '..',
    // Dotfiles are skipped unless named, so .env.production (public Supabase URL + anon key) is listed.
    includeSources: ['extension/**', 'extension/.env.production', 'shared/**'],
    excludeSources: ['extension/e2e/**', 'extension/icon-src/**', 'extension/scripts/**'],
  },
  vite: () => ({
    // shared/ lives one level up, next to extension/.
    server: { fs: { allow: ['..'] } },
  }),
});
