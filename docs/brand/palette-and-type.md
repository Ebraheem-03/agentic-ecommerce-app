# Palette & Type — US-E2-03

> Status: **[REVIEW]** — token-ready color + type spec. A human signs off before Iris consumes it (Day 3 → Tailwind theme / CSS vars).
> Inputs: approved `brand-brief.md`, locked logo `logo-directions.md` (Concept 2 "Keystone").
> Logo mapping: **outer plane → brand primary (`--brand`)**, **inner plane → brand accent / agent voice (`--accent`)**.

---

## 0. The two decisions in one line

- **Primary `#B5512F` (Clay)** — fired-clay terracotta. Warm and earthen, but desaturated and red-shifted so it reads as *handmade pottery*, **not** the saturated safety-vest orange of discount e-commerce.
- **Accent `#E08A3C` (Ember)** — a brighter amber glow, reserved for the **agent's voice** (chat surface, primary CTAs, the live inner plane of Keystone). This is the single confident accent the brief asks for.

**How this keeps Keystone from reading "generic-tech / crypto":** the abstract mark gets a *fired-clay + ember* duotone (never blue/violet, never neon-gradient), and it always sits next to **Fraunces**, a humanist serif wordmark. Warm earth pigment + a serif = artisan/concierge, the opposite of the cool-sans + electric-gradient fintech default.

---

## 1. Color — Brand

| Token | Role | Hex | Usage | Notes |
|---|---|---|---|---|
| `--brand` | Primary (Keystone **outer** plane) | `#B5512F` | Brand fills, logo outer plane, headers, focus rings, links on light | Clay/terracotta. Chosen over pure orange: hue ~16°, lower chroma → "fired clay", grown-up. |
| `--brand-strong` | Primary pressed/hover | `#933E22` | Hover/active of brand surfaces, high-contrast brand text on light | Darker clay; passes AA as text on `--bg`. |
| `--brand-tint` | Primary wash | `#F6E7DF` | Subtle brand-tinted surfaces, selected rows, badges | Very light clay; pairs with `--text` for AA. |
| `--accent` | Accent / **agent voice** (Keystone **inner** plane) | `#E08A3C` | Primary CTA fill, assistant chat surface, agent "live" state, inner plane | Ember amber. The product's one confident accent — use sparingly. |
| `--accent-strong` | Accent pressed/hover | `#C5722B` | Hover/active of accent CTAs; accent-as-text on light | Use this (not `--accent`) when amber must be *text*; raw `--accent` is AA-large-only. |
| `--accent-tint` | Accent wash | `#FCEEDD` | Assistant chat-bubble background, agent highlight | Warm glow surface for the agent voice. |

> **Duotone rule for Keystone:** outer plane = `--brand`, inner plane = `--accent`. On dark surfaces, swap to `--brand` outer + `--accent` inner unchanged (both hold on warm-dark). Single-tone fallback (favicon ≤24px): flatten both planes to `--brand`.

---

## 2. Color — Neutrals (warm gray ramp)

Hue-shifted toward red/yellow (~30° hue, very low chroma) so surfaces carry hearth warmth **quietly** — never the cold blue-gray default. Body background is a near-white warm gray, **not** cream/beige (brief: cream reads as default).

| Token | Hex | Usage |
|---|---|---|
| `--n-50` | `#FAF8F6` | App background (light), lowest surface |
| `--n-100` | `#F3EFEB` | Muted surface, hover rows |
| `--n-200` | `#E7E0D9` | Borders, dividers (light) |
| `--n-300` | `#D4C9BF` | Strong borders, disabled fills |
| `--n-400` | `#A99C8F` | Placeholder text, disabled text |
| `--n-500` | `#7C6F62` | Muted/secondary text (light) |
| `--n-600` | `#5E5247` | Secondary text strong |
| `--n-700` | `#433A31` | Surface (dark theme), strong text |
| `--n-800` | `#2C261F` | Background (dark theme) |
| `--n-900` | `#1B1611` | Deepest text (light) / deepest bg (dark) |

---

## 3. Color — Semantic (tuned warm)

Each nudged toward the warm palette so they sit beside Clay/Ember without clashing into Bootstrap defaults.

| Token | Hex | Usage | Notes |
|---|---|---|---|
| `--success` | `#3E7C5A` | Confirmed, in-stock, paid | Warm-leaning forest green (yellow-shifted, not minty). |
| `--success-tint` | `#E4F0E8` | Success surface/badge | |
| `--warning` | `#C58A1E` | Low stock, attention | Goldenrod, not the brand ember — distinct from `--accent`. |
| `--warning-tint` | `#FBF0D8` | Warning surface/badge | |
| `--error` | `#C23B34` | Failed, out of stock, destructive | Warm brick red; harmonizes with Clay, reads clearly as error. |
| `--error-tint` | `#FBE6E4` | Error surface/badge | |
| `--info` | `#3F6E86` | Neutral info, tips | Muted teal-blue, desaturated so it never competes with brand. Only "cool" color, used rarely. |
| `--info-tint` | `#E2EDF1` | Info surface/badge | |

---

## 4. Color — Surface & text roles (light + dark)

### Light theme
| Token | Maps to | Hex | Notes |
|---|---|---|---|
| `--bg` | background | `#FAF8F6` | warm near-white |
| `--surface` | card / panel | `#FFFFFF` | raised content |
| `--surface-muted` | muted surface | `#F3EFEB` | secondary panels |
| `--border` | border/divider | `#E7E0D9` | |
| `--text` | text-primary | `#1B1611` | warm near-black |
| `--text-muted` | text-secondary | `#5E5247` | (`--n-600`) |
| `--on-accent` | text/icon on `--accent` & `--brand` | `#FFFFFF` | |

### Dark theme
| Token | Maps to | Hex | Notes |
|---|---|---|---|
| `--bg` | background | `#1B1611` | warm-dark, not black |
| `--surface` | card / panel | `#2C261F` | |
| `--surface-muted` | muted surface | `#241F19` | |
| `--border` | border/divider | `#433A31` | |
| `--text` | text-primary | `#F3EFEB` | warm off-white |
| `--text-muted` | text-secondary | `#A99C8F` | (`--n-400`) |
| `--on-accent` | text/icon on `--accent` & `--brand` | `#1B1611` | dark ink on warm fills reads cleanest on dark UI |

> On dark, **accent stays `#E08A3C`** with **dark ink** (`#1B1611`) on top for CTAs — that pairing is the highest-contrast option and keeps the ember glow.

---

## 5. Accessibility — WCAG 2.1 AA

Body text target ≥ 4.5:1; large text (≥18.66px bold / ≥24px) and UI/graphics ≥ 3:1. Ratios computed from the hex values above.

| Pairing | Ratio | Verdict |
|---|---|---|
| `--text` `#1B1611` on `--bg` `#FAF8F6` (light) | **17.0:1** | AA + AAA body |
| `--text-muted` `#5E5247` on `--surface` `#FFFFFF` (light) | **7.6:1** | AA body |
| `--text-muted` `#5E5247` on `--bg` `#FAF8F6` | **7.2:1** | AA body |
| `--on-accent` `#FFFFFF` on `--accent` `#E08A3C` | **2.7:1** | ✗ **fails** — see rule below |
| `--on-accent` `#FFFFFF` on `--accent-strong` `#C5722B` | **3.6:1** | AA **large/UI only** |
| `--text` `#1B1611` (ink) on `--accent` `#E08A3C` | **6.7:1** | AA + AAA body — **default CTA pairing** |
| `--on-accent` `#FFFFFF` on `--brand` `#B5512F` | **5.0:1** | AA body |
| `--text` `#F3EFEB` on `--bg` `#1B1611` (dark) | **15.7:1** | AA + AAA body |
| `--text-muted` `#A99C8F` on `--surface` `#2C261F` (dark) | **5.6:1** | AA body |
| ink `#1B1611` on `--accent` `#E08A3C` (dark CTA) | **6.7:1** | AA + AAA body |

**Rules that fall out of the math:**
1. **Primary CTA = `--accent` fill with DARK ink (`--text`), not white.** White on ember (2.7:1) fails; dark ink on ember (6.7:1) is excellent. This is the canonical button in both themes.
2. **White on `--brand` (clay) passes (5.0:1)** — so brand-clay buttons *may* use white text. Brand is the default for non-agent primary actions; accent-ember is reserved for the agent's voice.
3. **Ember as TEXT must use `--accent-strong`** and only at large/UI sizes (3.4:1). Never set body copy in raw `--accent`.

---

## 6. Typography

### Families
| Role | Family | Fallback stack | Why |
|---|---|---|---|
| **Display / Headings + wordmark** | **Fraunces** (Google) | `'Fraunces', Georgia, 'Times New Roman', serif` | A humanist "old-style with soft modern" serif. Carries warmth + a premium, hand-made concierge register, and is the single biggest lever keeping Keystone from reading generic-tech (a serif beside the abstract mark = artisan, not fintech). Optical-size axis lets headlines feel crafted. |
| **UI / Body** | **Outfit** (Google) | `'Outfit', 'Segoe UI', system-ui, -apple-system, sans-serif` | Geometric-humanist sans, already used in the locked lockup. Clean and calm for dense UI (tables, dashboard, controls), low-contrast strokes keep it friendly rather than corporate. Pairs with Fraunces without competing. |

> **One family alternative considered:** Fraunces alone (it ships a sans-ish low-contrast soft optical size). Rejected — a dedicated sans reads better in small UI chrome and the dashboard. Two families it is, kept lean (see weights).

### Weights to load (perf)
Keep it tight — **4 files total**:
- **Fraunces:** 400 (subhead/quotes), 600 (headings). Use the `opsz` optical axis if variable; otherwise static 400 + 600.
- **Outfit:** 400 (body), 500 (UI labels/buttons). Add 600 only if the dashboard needs it; default no.

`font-display: swap`. Subset `latin`. Preconnect to `fonts.gstatic.com`.

### Modular scale
Base **16px = 1rem**, ratio ~**1.25 (major third)** for headings, tightened for UI steps. `rem` is authoritative.

| Token | Use | Family | px / rem | Weight | Line-height | Letter-spacing |
|---|---|---|---|---|---|---|
| `display` | Hero / marketing headline | Fraunces | 56 / 3.5rem | 600 | 1.05 | -0.02em |
| `h1` | Page title | Fraunces | 40 / 2.5rem | 600 | 1.1 | -0.015em |
| `h2` | Section | Fraunces | 30 / 1.875rem | 600 | 1.15 | -0.01em |
| `h3` | Subsection | Fraunces | 24 / 1.5rem | 600 | 1.2 | -0.005em |
| `h4` | Card title / minor head | Outfit | 20 / 1.25rem | 500 | 1.3 | 0 |
| `body-lg` | Lead paragraph, chat | Outfit | 18 / 1.125rem | 400 | 1.6 | 0 |
| `body` | Default copy | Outfit | 16 / 1rem | 400 | 1.6 | 0 |
| `small` | Secondary, captions in UI | Outfit | 14 / 0.875rem | 400 | 1.5 | 0.005em |
| `caption` | Labels, meta, badges | Outfit | 12 / 0.75rem | 500 | 1.4 | 0.02em (UPPER ok) |

### Wordmark treatment — "Hearth"
- **Family:** Fraunces 600. (Note: the locked lockup SVG currently sets the wordmark in Outfit 600 — **recommend re-cutting the lockup wordmark to Fraunces** to land the humanist-serif warmth. Flagging for sign-off; mark geometry unchanged.)
- **Size relationship:** wordmark cap-height ≈ 0.55 × mark height in the lockup.
- **Tracking:** `-0.01em`. **Case:** title-case "Hearth" (never all-caps, never lowercase).
- **Color:** wordmark in `--text`; mark in the duotone (`--brand` + `--accent`). Optionally the dotless ascent of the "t" / first letter never recolored — keep the wordmark one solid color so the *mark* owns the duotone.

---

## 7. Hand-off note for Iris (Day 3)
- Emit §1–4 as CSS custom properties on `:root` (light) and `[data-theme="dark"]`, then map into Tailwind `theme.extend.colors`.
- Ship the **dark-ink-on-ember** button as the default `Button` primary variant; brand-clay-with-white as `Button` variant `brand`.
- Load only the 4 font files in §6; wire `--font-display` (Fraunces) and `--font-sans` (Outfit).
- Recolor `hearth-logo-mark.svg`: outer path `fill: var(--brand)`, inner path `fill: var(--accent)` (drop the `opacity:0.45`, the accent hue carries the separation now).
