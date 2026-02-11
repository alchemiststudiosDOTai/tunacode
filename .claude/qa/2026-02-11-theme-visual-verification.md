---
title: Dream UI visual verification for unified theme architecture
type: qa
link: theme-visual-verification
path: src/tunacode/ui/styles
depth: 0
seams: [A, S, M]
ontological_relations:
  - verifies: [[theme-system]]
  - verifies: [[ui]]
  - relates_to: [[nextstep-design-language]]
tags:
  - qa
  - visual-verification
  - theme
  - nextstep
  - dream-ui
created_at: 2026-02-11T15:57:42-06:00
updated_at: 2026-02-11T15:57:42-06:00
uuid: ab39d759-80fb-480b-809c-8f6a5b8db76f
---

# Dream UI visual verification for unified theme architecture

## Reference inputs

- `docs/images/dream-ui/tunacode-cli-home.png`
- `docs/images/dream-ui/tunacode-cli-home-catpu.png`
- `docs/images/dream-ui/tunacode-cli-response.png`
- `docs/images/dream-ui/tunacode-cli-lsp.png`
- `memory-bank/plan/assets/dream-mockup-slim-panels.webp`

## Verification artifacts

Generated headless screenshots:

- `memory-bank/plan/assets/verification/verification-home.svg`
- `memory-bank/plan/assets/verification/verification-response.svg`
- `memory-bank/plan/assets/verification/verification-lsp.svg`
- `memory-bank/plan/assets/verification/verification-nextstep-home.svg`

## Checks performed

1. **Viewport border tone**
   - Tunacode theme uses subtle dark border tone (no magenta structural frame).
   - NeXTSTEP theme uses light bevel high/low edges with preserved structure.

2. **Scrollbar palette behavior**
   - Tunacode verification captures include magenta thumb token (`#fe6b9d`) on dark track.
   - NeXTSTEP verification captures include neutral gray scrollbar token (`#606060`) with light track.

3. **Streaming state semantics**
   - `#viewport.streaming` uses pressed bevel + primary outline (`$primary`), preserving structure.
   - No theme-specific structural overrides required.

4. **Panel semantics**
   - Tool, agent, error panels share one structural bevel grammar.
   - Semantic color changes happen via outlines (`$primary`, `$accent`, `$error`, etc.), not custom per-theme CSS.

5. **Theme swap contract**
   - Theme switch now swaps only palette values under one shared variable contract.
   - No `.theme-*` class overrides and no `theme-nextstep.tcss` file.

## Intentional deltas from reference images

- Automated captures are Textual terminal screenshots (font/antialiasing/layout rasterization differ from PNG mockups).
- Verification focuses on **structure + palette semantics** (border tone, scrollbar behavior, streaming state, panel accents), not pixel-identical glyph rendering.
