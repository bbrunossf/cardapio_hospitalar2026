---
version: alpha
name: Cardapio Plena
description: Institutional clean healthcare identity — NHS Blue, IBM Plex Sans, off-white surfaces, sidebar-first data UI. Accessible to deuteranopia/protanopia (never red/green dependent).
colors:
  primary: "#005EB8"
  primary-hover: "#004E99"
  primary-soft: "#E6F0FA"
  background: "#F4F7FA"
  surface: "#FFFFFF"
  text: "#1F2933"
  text-muted: "#5C6B7A"
  border: "#D9E1E8"
  success: "#0B7A75"
  warning: "#E8A33D"
  danger: "#C2410C"
typography:
  h1:
    fontFamily: IBM Plex Sans
    fontSize: 2rem
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  h2:
    fontFamily: IBM Plex Sans
    fontSize: 1.5rem
    fontWeight: 700
    lineHeight: 1.25
  h3:
    fontFamily: IBM Plex Sans
    fontSize: 1.25rem
    fontWeight: 600
    lineHeight: 1.3
  h4:
    fontFamily: IBM Plex Sans
    fontSize: 1.125rem
    fontWeight: 600
    lineHeight: 1.35
  body-md:
    fontFamily: IBM Plex Sans
    fontSize: 1rem
    fontWeight: 400
    lineHeight: 1.5
  body-sm:
    fontFamily: IBM Plex Sans
    fontSize: 0.875rem
    fontWeight: 400
    lineHeight: 1.45
  label:
    fontFamily: IBM Plex Sans
    fontSize: 0.8125rem
    fontWeight: 600
    letterSpacing: "0.04em"
  numeric:
    fontFamily: IBM Plex Sans
    fontSize: 1rem
    fontWeight: 500
    fontFeature: "tnum"
rounded:
  sm: 4px
  md: 8px
  lg: 12px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "#FFFFFF"
    rounded: "{rounded.sm}"
    padding: 12px
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
    textColor: "#FFFFFF"
    rounded: "{rounded.sm}"
    padding: 12px
  button-secondary:
    backgroundColor: "{colors.primary-soft}"
    textColor: "{colors.primary}"
    rounded: "{rounded.sm}"
    padding: 12px
  card:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.md}"
    padding: "{spacing.lg}"
  table-header:
    backgroundColor: "{colors.primary-soft}"
    textColor: "{colors.text}"
  sidebar:
    backgroundColor: "{colors.surface}"
    width: 240px
  badge-info:
    backgroundColor: "{colors.primary-soft}"
    textColor: "{colors.primary}"
    rounded: "{rounded.lg}"
  badge-success:
    backgroundColor: "#DDF0EE"
    textColor: "#065F5A"
    rounded: "{rounded.lg}"
  badge-warning:
    backgroundColor: "#FBF0DC"
    textColor: "#7A5300"
    rounded: "{rounded.lg}"
  badge-danger:
    backgroundColor: "#F9E4DC"
    textColor: "#9A3309"
    rounded: "{rounded.lg}"
---

## Overview

Cardápio Plena is the visual identity for Bruno Oliveira's healthcare menu management app (cardápio hospitalar). Institutional clean: trustworthy, legible, low-glare. The identity is built on NHS Blue `#005EB8` — a healthcare classic — with IBM Plex Sans for type, off-white surfaces that avoid harsh pure-white glare, and a sidebar-first layout for dense data work.

Two hard constraints drive every decision:

1. **Color vision deficiency** (office manager has deuteranopia/protanopia) — red and green are never used as the *only* differentiator. Semantic states carry an icon/text cue in addition to color.
2. **Performance & minimal dependencies** — Flask-Admin (Bootstrap) is the runtime; no React, no shadcn, no heavy JS. Tailwind or custom CSS on top of Bootstrap theme overrides.

## Colors

- **Primary (#005EB8):** NHS Blue — the single driver for interaction. Buttons, active nav, links, focus rings.
- **Primary-soft (#E6F0FA):** tint for table headers, hover backgrounds, badges, selected states.
- **Background (#F4F7FA):** off-white app canvas — deliberately below pure `#FFFFFF` to cut glare on long data sessions.
- **Surface (#FFFFFF):** cards, sidebar, modals — white is reserved for elevated containers, never the page backdrop.
- **Text (#1F2933) / Text-muted (#5C6B7A):** near-black slate and secondary gray.
- **Semantic trio:** success `#0B7A75` (teal), warning `#E8A33D` (amber), danger `#C2410C` (burnt orange). All distinguishable from blue and from each other under deuteranopia/protanopia by hue *and* luminance. Never pair red↔green as the only signal — always add an icon or text label.

## Typography

IBM Plex Sans everywhere — humanist grotesque with personality, excellent legibility, and tabular numerals. No serif, no display font.

- **H1→H4 hierarchy** mirrors Markdown (user preference): 2rem / 1.5rem / 1.25rem / 1.125rem, weights 700/700/600/600.
- **Numeric data** uses `font-feature-settings: "tnum"` (tabular numbers) — columns align, and digits stay OCR-safe (Bruno hit OCR failures with decorative fonts where `0/O`, `1/l` collided).
- Labels: small caps-style 0.8125rem, weight 600, +0.04em tracking.
- Body: 1rem / 0.875rem at 400, line-height 1.5 / 1.45.

## Layout

- **Sidebar always** — 240px fixed, white surface, primary-tinted active item. It's Bruno's signature.
- **Header** — 64px, page title H1 + contextual actions.
- **Content uses max width** — no fixed-width cage; tables and dashboards stretch to the viewport.
- **Cards** — 8px radius, white, 24px padding, hairline border; used for dashboard stats and groupings.
- **Icons** — inline SVG only (Lucide-style). **Never emojis** in the UI.
- Density: comfortable for daily use — 16px base gaps, 8px inside table cells.

## Elevation & Depth

Flat-first with minimal elevation: cards separated by background contrast and a `#D9E1E8` hairline border, not shadows. A single soft shadow (`0 1px 3px rgba(15,23,42,0.08)`) on modals and dropdowns only.

## Shapes

- Buttons and inputs: 4px radius (sm).
- Cards, tables, panels: 8px radius (md).
- Badges/pills: 12px (lg).

## Components

- **button-primary** — NHS Blue bg, white text, 4px radius, 12px padding. Hover: `primary-hover`.
- **button-secondary** — primary-soft bg, NHS Blue text — for less-emphasized actions.
- **card** — white, 8px radius, 24px padding, hairline border.
- **table-header** — primary-soft background, near-black text, tabular numerals in data cells.
- **badge-*** — tinted pills; each semantic state pairs color with a label/icon (never color-only).
- **sidebar** — 240px white rail; active item = primary text + primary-soft background.

## Do's and Don'ts

**Do:**
- Use NHS Blue `#005EB8` for all interactive emphasis.
- Use off-white `#F4F7FA` as the app background — avoid pure white pages.
- Use IBM Plex Sans, tabular numbers for all numeric columns.
- Use inline SVG icons (Lucide) — never emojis.
- Keep the sidebar + header + max-width content layout.
- Keep motion subtle: 150-200ms transitions, `prefers-reduced-motion` respected, no layout-shifting animations.

**Don't:**
- Don't use red or green as the only differentiator (manager is deuteranopic/protanopic) — pair with icon/text.
- Don't use pure `#FFFFFF` as the page background.
- Don't introduce serif or decorative display fonts.
- Don't add React/shadcn/heavy JS to the Flask-Admin app — Tailwind or scoped CSS only.
- Don't use emojis in UI; no autoplaying or heavy animations.
- Don't break the H1→H4 Markdown-style hierarchy.
