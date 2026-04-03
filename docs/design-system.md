# Track Mapper — Design System

> Visual and interaction foundations for [`apps/web-frontend`](../apps/web-frontend). Product goals and glossary live in [`top_level_spec.md`](./top_level_spec.md). Screen map and flows live in [`UI.md`](./UI.md).

## 1. Product context

1. Align with **DJ desktop software**: dark-first, **data-dense**, minimal chrome, fast scanning of many tracks.
2. **Accessibility:** Meet **WCAG 2.1 AA** for text contrast and **visible focus** in both themes; do not rely on color alone for state (pair with icon or text).
3. **Motion:** Respect **`prefers-reduced-motion`** for non-essential transitions.

## 2. Implementation stack (UI)

1. **Vite + React + TypeScript** — see [`tech-approach.md`](./tech-approach.md).
2. **Tailwind CSS** — layout, spacing, typography utilities; **avoid arbitrary pixel soup** where tokens exist.
3. **Radix UI + shadcn/ui** — **Yes, use them** for accessible primitives (Dialog where needed, DropdownMenu, Tabs, Tooltip, Select, etc.) and consistent styling. shadcn copies components into the repo so we **own** the code and can tune for density. Radix provides behavior and a11y; we style with Tailwind to match this spec.
4. **Tables** — **TanStack Table** (or headless grid) for sorting/filtering/column defs; combine with shadcn-style row/cell patterns.

## 3. Theming: dark (default) and light

1. **Dark is default** — matches Rekordbox/Ableton-style tools; **light** is a supported alternative (user toggle in Settings, persisted).
2. **CSS variables** on `:root` (or a `data-theme` wrapper) drive:
   1. Background and surface layers  
   2. Border and divider  
   3. Text primary / secondary / muted  
   4. Accent (primary action, links, focus ring)  
   5. Semantic: success / warning / danger / info (match states, toasts)
3. **Tailwind** — map theme tokens via `tailwind.config` (e.g. `colors.background`, `colors.surface-1`) so components use semantic names, not raw hex in JSX.
4. **No flash** — initialize theme from `localStorage` or `prefers-color-scheme` in a small inline script before paint if needed.

### 3.1 Dark palette (starting point)

| Token | Role | Example (tune in implementation) |
| ----- | ---- | ---------------------------------- |
| `--background` | App chrome / page | `#0a0a0a`–`#0f0f0f` |
| `--surface-1` | Panels, secondary table | `#141414`–`#1a1a1a` |
| `--surface-2` | Raised controls, header | `#1f1f1f`–`#262626` |
| `--border` | Hairlines | `#2a2a2a`–`#333` |
| `--text-primary` | Main copy | `#f0f0f0` |
| `--text-secondary` | Metadata | `#a3a3a3` |
| `--text-muted` | Hints | `#737373` |
| `--accent` | Primary CTA, focus | Single hue (e.g. cyan or blue `#22d3ee` / `#38bdf8`) — pick one and document |

### 3.2 Light palette

1. Mirror the same **token names** with inverted luminance (off-white backgrounds, dark text); keep **accent** recognizable across themes.

## 4. Typography

1. **Font stack** — **Inter**, **Geist**, or **IBM Plex Sans** (choose one family for v1); system UI fallback.
2. **Small type** — Base UI in **`rem`**: table cells roughly **0.75rem–0.8125rem** (12–13px at 16px root); headers one step up. Use **`font-feature-settings: "tnum"`** (tabular nums) on duration/BPM columns where helpful.
3. **Line height** — Tight for tables (**1.2–1.35**); slightly looser for empty states and settings.

## 5. Density, spacing, and scaling

1. **Row height** — Target **compact** ~28–32px effective row height; **comfortable** ~36–40px; **ultra-compact** ~24–28px (implementation defines exact `py` + line-height).
2. **Density toggle** — **Ship on day one** (toolbar or Settings): switches preset classes or CSS variables (`--row-height`, `--cell-padding-y`).
3. **Global font scale** — User-controlled **zoom** of UI text (e.g. 87% / 100% / 112% / 125%) via:
   1. **`rem`** for typography and most spacing tied to readability, or  
   2. A **`--ui-scale`** multiplier on `html` / wrapper  
   Persist in **localStorage**; browser zoom remains independent and should still work.
4. **Padding** — Prefer **`rem`**-based horizontal cell padding; keep **tight** for pro-user scanning.

## 6. Tables

1. **Sticky header** — Primary table (and secondary when scrollable).
2. **Zebra rows** — **Subtle** alternating row background using `--surface-1` / slightly shifted token (e.g. 2–4% luminance delta); must work in light and dark.
3. **Hover** — Clear row hover state without overpowering zebra.
4. **Selection** — Visible **selected row** border or background; keyboard focus distinct from mouse selection where both exist.

## 7. Layout chrome

1. **Minimal header** — Logo/name, user menu, density, theme, settings.
2. **No decorative noise** — Borders and separation over heavy shadows.

## 8. Feedback patterns

1. **Loading** — **Skeleton** rows/cells for tables (no spinners-only for large lists).
2. **Errors / success** — **Toasts** (non-blocking); stack sensibly; dismissible. Use Radix Toast or sonner + theme tokens.
3. **Forms** — Inline field errors where applicable.

## 9. “Full component library” (out of scope)

1. **What we mean:** A **standalone design-system product** (exhaustive Storybook of every molecule, versioning, multi-brand tokens, Figma kit in lockstep). That is **out of scope for v1**.
2. **What we do instead:** **Radix + shadcn** gives a **bounded** set of **primitives** we compose; document **patterns** in this file and **screens** in [`UI.md`](./UI.md). Add Storybook later only if the team wants visual regression.

## 10. Document map

| Doc | Role |
| --- | ---- |
| [`top_level_spec.md`](./top_level_spec.md) | Product requirements |
| [`UI.md`](./UI.md) | Screens, routes, panels |
| [`tech-approach.md`](./tech-approach.md) | Repo layout, API, Docker |
