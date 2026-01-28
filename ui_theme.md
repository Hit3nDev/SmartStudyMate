# UI Theme Guide

This theme gives SmartStudyMate a polished glass/3D SaaS look.

## Palette
- Backgrounds: `#08090f` / `#0f111a` / `#131726`
- Primary: `#7c5cff` (indigo-violet)
- Secondary: `#2fe6d6` (cyan)
- Accent/Highlight: `#ff6fa3` (magenta)
- Text: primary `#f8f9ff`, secondary `rgba(248,249,255,0.78)`, muted `rgba(248,249,255,0.58)`
- Glow: `rgba(124,92,255,0.18)` and `rgba(47,230,214,0.16)`

## Typography
- Font stack: Inter, Poppins, system-ui, -apple-system, "Segoe UI"
- Sizes: H1 ~48px, H2 ~28–32px, H3 ~18–20px, body 14–16px.

## Spacing & Radius
- Base spacing 12px. Steps: 12 / 18 / 24 / 32 / 48.
- Radii: small 10–12px, cards 18px, hero 22px.

## Shadows & Effects
- Soft card shadow: `0 8px 30px rgba(3,6,15,0.6)`
- Rim glow: `0 0 28px rgba(124,92,255,0.18)`
- Transitions: 120–220ms ease on hover/focus; slight lift on cards.

## Components (see `ui/components.py`)
- `ui_glass_card`: glass panel with hover lift.
- `ui_section_heading`: consistent section headers.
- `status_pill` / `focus_summary_card`: pills with tone classes and mini focus widget.

## Tweaking
- Update color variables in `style.css :root`.
- Adjust spacing via `--space-*` tokens.
- Change radii via `--radius-*`.
- Soften/strengthen glow via `--rim-glow` and `--accent-*glow`.

## Privacy Messaging
Keep the inline microcopy: “Focus Detection runs entirely in your browser. No video or images are uploaded or stored. Only numeric scores & timestamps are saved.”

