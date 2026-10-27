# Impeccable UI audit

Audit target: `frontend/src`

Product truth: `PRODUCT.md`

Scope: React Web Editor and its pywebview desktop surface

## Workflow assessment

The application already had the right large-scale anatomy: menu and transport chrome, a dominant transcription canvas, timeline navigation, contextual editing, and settings. The redesign therefore keeps the editor model intact and tightens the primary loop:

`play → read spectrum / tracks → select → create or edit Note → play again`

The most important source-observed problems were:

- Track conversion controls floated over the material being read.
- The right rail permanently consumed canvas width even when it was not useful.
- Cursor, peak, Track-hover, operation, and error messages competed for one transient status string.
- View and playback toggle state was mostly visual rather than programmatically exposed.
- Menus announced desktop-menu semantics without the corresponding arrow/Home/End navigation.
- Dialog semantics and focus handling varied between tools.
- The empty canvas did not explain the first productive action.
- Numeric pitch formatting was duplicated across the Canvas, Inspector, and application shell.

## Decisions

### FIX

- Make the right rail collapsible while keeping a stable toolbar affordance.
- Move Track selection, range control, and conversion actions into the contextual Inspector.
- Add a compact, persistent Canvas readout for time, MIDI, note name, Hz, peak, and Track details.
- Add an actionable empty-workspace state without restoring file buttons to the toolbar.
- Use semantic pressed states and explicit accessible names for transport and view controls.
- Implement menu arrow/Home/End navigation.
- Add shared dialog labeling, focus entry, focus containment, Escape close, and focus restoration.
- Expose the Canvas as a named focusable editing region.
- Strengthen small-text contrast and visible keyboard focus.
- Extract MIDI-to-Hz and MIDI-label formatting into one tested pure module.
- Replace decorative status pills, broad panel cards, and the floating Track action card with compact editor chrome.

### IGNORE WITH REASON

- Dense controls remain 28–32 px high rather than 44 px. This is a precision desktop editor, and the controls retain at least the WCAG 2.2 24 px target floor. Enlarging every control would materially reduce the Canvas.
- A neutral system UI font is retained. Long-session legibility and native desktop density are more important than introducing a branded display face.
- Modal dialogs remain for protected or bounded workflows such as export, destructive-state confirmation, and tool configuration. Routine Track actions were removed from the Canvas instead of becoming another modal.

### NOT APPLICABLE

- Mobile-first composition. The product targets desktop windows; narrow-desktop resilience is in scope.
- Decorative hero, marketing sections, or page transitions.
- Reduced-motion variants: no authored animation system or nonessential motion is used.
- AI-based automatic transcription controls: they conflict with the semi-manual product model.

## Detector

Baseline official detector result:

- `overused-font` at the former `styles.css:2`: **IGNORE WITH REASON**. `Inter` was only an unavailable fallback name and the actual interface used system UI fonts.
- All other enabled detector rules: **NOT APPLICABLE / NO MATCH**.

The unused `Inter` fallback was nevertheless removed to make the implementation and design intent agree. Final command:

```text
.agents\skills\impeccable\scripts\impeccable.cmd detect --json frontend/src
[]
```

Zero final findings are recorded as evidence, not as the product success criterion.

## Evidence limitation

Source, tests, production builds, and the real pywebview lifecycle were available. Screenshot capture was blocked by an active Windows UAC secure desktop, which must not be automated, while the in-app browser origin was explicitly denied. The invalid black capture was discarded and is not treated as visual evidence.
