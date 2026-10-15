# Building Primora from source

The extension is built with [WXT](https://wxt.dev) (Vite). The build bundles and minifies; these steps reproduce the uploaded add-on exactly.

## Requirements

- Node.js 24 (built with 24.22.0)
- npm 11 (built with 11.19.1)

## Layout

- `extension/`: the extension (WXT project, run all commands here)
- `shared/`: TypeScript and CSS imported by the extension (`../shared/...`)
- `extension/.env.production`: the public Supabase project URL and anon key, read at build time. The anon key is meant to ship in clients; data access is enforced by row-level security.

## Steps

```sh
cd extension
npm ci
npm run build:firefox
```

The built add-on is in `extension/.output/firefox-mv3/` and should match the uploaded package file for file.
