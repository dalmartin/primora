import { defineConfig } from 'wxt';

// See https://wxt.dev/api/config.html
export default defineConfig({
  modules: ['@wxt-dev/module-react'],
  manifest: {
    name: 'Primora',
    description: 'Logs your internship applications when you submit them, and keeps the promising ones on top.',
    // storage: session + queued logs; activeTab: prefill "I applied"; identity: Google sign-in.
    permissions: ['storage', 'activeTab', 'identity'],
    // Public job-board APIs, used to clean up company / role names after a submit.
    host_permissions: ['https://boards-api.greenhouse.io/*', 'https://api.ashbyhq.com/*'],
  },
  vite: () => ({
    // shared/ lives one level up, next to web/.
    server: { fs: { allow: ['..'] } },
  }),
});
