/** Theme switching. Styles live in shared/theme.css + shared/themes/; this only picks one. */

export const THEMES = {
  bloom: { label: 'Bloom', favicon: '/favicon-bloom.svg' },
  classic: { label: 'Classic', favicon: '/favicon.svg' },
} as const;

export type ThemeName = keyof typeof THEMES;

/** The theme everyone gets until they pick another one. Change this line to switch the default. */
export const DEFAULT_THEME: ThemeName = 'bloom';

const KEY = 'primora:theme';

export function savedTheme(): ThemeName {
  try {
    const t = localStorage.getItem(KEY);
    if (t && t in THEMES) return t as ThemeName;
  } catch {
    // Storage blocked: use the default.
  }
  return DEFAULT_THEME;
}

/** Apply a theme to the page; `remember` saves it for next time (per browser). */
export function applyTheme(theme: ThemeName, remember = false) {
  document.documentElement.dataset.theme = theme;
  const icon = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
  if (icon) icon.href = THEMES[theme].favicon;
  if (remember) {
    try {
      localStorage.setItem(KEY, theme);
    } catch {
      // ignore
    }
  }
}
