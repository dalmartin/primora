import { defineConfig } from 'wxt';

// See https://wxt.dev/api/config.html
export default defineConfig({
  modules: ['@wxt-dev/module-react'],
  manifest: {
    name: 'Primora',
    description: 'Know when internships open, log every application automatically, and see which ones are still alive.',
  },
});
