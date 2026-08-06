---
name: Vitalis Clinical
colors:
  surface: '#f7f9fb'
  surface-dim: '#d8dadc'
  surface-bright: '#f7f9fb'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f4f6'
  surface-container: '#eceef0'
  surface-container-high: '#e6e8ea'
  surface-container-highest: '#e0e3e5'
  on-surface: '#191c1e'
  on-surface-variant: '#3d4a3e'
  inverse-surface: '#2d3133'
  inverse-on-surface: '#eff1f3'
  outline: '#6c7b6d'
  outline-variant: '#bbcbbb'
  surface-tint: '#006d37'
  primary: '#006d37'
  on-primary: '#ffffff'
  primary-container: '#2ecc71'
  on-primary-container: '#005027'
  inverse-primary: '#4ae183'
  secondary: '#006397'
  on-secondary: '#ffffff'
  secondary-container: '#5cb8fd'
  on-secondary-container: '#00476e'
  tertiary: '#b4271d'
  on-tertiary: '#ffffff'
  tertiary-container: '#ff9687'
  on-tertiary-container: '#8e0505'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#6bfe9c'
  primary-fixed-dim: '#4ae183'
  on-primary-fixed: '#00210c'
  on-primary-fixed-variant: '#005228'
  secondary-fixed: '#cce5ff'
  secondary-fixed-dim: '#92ccff'
  on-secondary-fixed: '#001d31'
  on-secondary-fixed-variant: '#004b73'
  tertiary-fixed: '#ffdad5'
  tertiary-fixed-dim: '#ffb4a9'
  on-tertiary-fixed: '#410000'
  on-tertiary-fixed-variant: '#910807'
  background: '#f7f9fb'
  on-background: '#191c1e'
  surface-variant: '#e0e3e5'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  title-md:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
    letterSpacing: 0.01em
  caption-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 8px
  xs: 4px
  sm: 12px
  md: 24px
  lg: 40px
  xl: 64px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 48px
---

## Brand & Style
The design system is centered on **Clinical Precision** and **Empathetic Wellness**. It targets healthcare professionals and patients engaging in anamnesis (medical history) and anthropometric tracking. The UI must feel authoritative and sterile enough to trust with medical data, yet soft enough to reduce "white coat hypertension" during data entry.

The style is a blend of **Modern Corporate** and **Minimalism**. It utilizes high-quality whitespace to reduce cognitive load during complex data entry, ensuring that critical health metrics remain the focal point. Surfaces are clean, utilizing subtle tonal shifts rather than heavy borders to define structure.

## Colors
The palette is rooted in functional healthcare semiotics. 
- **Healthcare Green (#2ECC71):** Used for primary actions, success states, and positive health trends. It symbolizes growth and vitality.
- **Trust Blue (#3498DB):** Used for information callouts, secondary actions, and data visualization elements that require professional neutrality.
- **System Colors:** A tertiary Red (#E74C3C) is reserved strictly for alerts, out-of-range anthropometric data, and critical medical contraindications.
- **Neutrals:** A range of cool greys (from #F8FAFC to #1E293B) provides the structural scaffolding, ensuring the background feels expansive and clean.

## Typography
The design system utilizes **Inter** for all roles to maintain a systematic, utilitarian aesthetic. 
- **Scale:** High contrast between headlines and body text helps guide clinicians through long anamnesis forms. 
- **Readability:** Body-md is the workhorse for patient notes, utilizing a generous line height (1.5x) to prevent eye strain during prolonged reading.
- **Labels:** Use Label-md for form fields and data headers, rendered in a medium weight to distinguish from input text.

## Layout & Spacing
The layout follows a **Fluid Grid** model with a maximum content width of 1280px for desktop. 
- **Grid:** 12 columns for desktop, 8 for tablet, and 4 for mobile. 
- **Anamnesis Forms:** Multi-column layouts should be avoided for patient data entry; stick to a single-column or two-column "label-left" alignment to ensure a logical scanning path.
- **Rhythm:** An 8px linear scale governs all padding and margins. Vertical rhythm should be strictly enforced in data cards to ensure baseline alignment across comparative charts.

## Elevation & Depth
Depth is conveyed through **Tonal Layering** and soft, ambient shadows.
- **Level 0 (Background):** #F8FAFC (Neutral Grey).
- **Level 1 (Cards/Containers):** Pure white (#FFFFFF) with a very soft, diffused shadow (0px 4px 20px rgba(0,0,0,0.05)).
- **Level 2 (Modals/Popovers):** Higher elevation with a more pronounced shadow to indicate temporary focus.
- **Interaction:** Buttons use a slight vertical lift on hover. Avoid heavy borders; use 1px strokes in a light grey (#E2E8F0) for card boundaries when shadows are not appropriate.

## Shapes
This design system uses a **Rounded** corner strategy. 
- **Standard Elements:** 0.5rem (8px) radius for buttons and input fields provides a friendly, approachable feel without appearing juvenile.
- **Containers:** 1rem (16px) for cards and sections to create a distinct containment for data groups.
- **Charts:** Bar charts and progress indicators should use subtle rounding (2px or 4px) to maintain the clinical softness.

## Components
- **Input Fields:** Large, clear hit areas with a 1px border (#CBD5E1). On focus, the border transitions to Primary Green with a 2px outer glow.
- **Data Cards:** Group related anthropometric data (Height, Weight, BMI). Use a Title-md for the metric name and Display-lg for the value.
- **Interactive Charts:** Line charts for tracking weight over time should use Primary Green for the data line, with Trust Blue markers for clinical milestones.
- **Chips:** Used for medical tags or dietary preferences. Subtle background fill with dark text; no borders.
- **Action Buttons:** Primary buttons are solid Primary Green with white text. Secondary buttons use a Trust Blue ghost style (outline only).
- **Segmented Control:** For toggling units (kg/lb, cm/in), use a pill-shaped toggle with a neutral grey background and a white sliding active state.