import { createClient, type SupportedStorage } from '@supabase/supabase-js';

export const SUPABASE_URL = import.meta.env.WXT_SUPABASE_URL as string;
const SUPABASE_ANON_KEY = import.meta.env.WXT_SUPABASE_ANON_KEY as string;

if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
  console.error('Primora: set WXT_SUPABASE_URL and WXT_SUPABASE_ANON_KEY in extension/.env.local');
}

// Popup and background share one session through extension storage.
const chromeStorage: SupportedStorage = {
  async getItem(key) {
    const got = await browser.storage.local.get(key);
    return (got[key] as string | undefined) ?? null;
  },
  async setItem(key, value) {
    await browser.storage.local.set({ [key]: value });
  },
  async removeItem(key) {
    await browser.storage.local.remove(key);
  },
};

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
  auth: {
    storage: chromeStorage,
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: false,
    flowType: 'pkce',
  },
});
