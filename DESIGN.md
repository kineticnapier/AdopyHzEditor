---
name: AdopyHzEditor
description: A restrained, canvas-first dark workspace for precise human-led music transcription.
colors:
  canvas-black: "#080b0e"
  workspace-black: "#090c0f"
  surface-base: "#171b20"
  surface-chrome: "#1d2228"
  surface-control: "#262c33"
  divider: "#343b43"
  divider-strong: "#4a545e"
  text-primary: "#e7ebef"
  text-muted: "#9ca7b2"
  action-blue: "#3b9ddd"
  action-blue-strong: "#5bb7ef"
  positive-green: "#55c98a"
  warning-gold: "#e4bc5b"
  danger-red: "#ef7d7d"
  focus-blue: "#78c7ff"
  track-cyan: "rgba(135, 240, 255, 0.92)"
  selection-yellow: "#ffe65a"
  note-blue: "#46afff"
  playhead-white: "rgba(255, 255, 255, 0.92)"
  region-blue: "rgba(70, 175, 255, 0.16)"
typography:
  headline:
    fontFamily: '"Segoe UI Variable Text", "Segoe UI", "Yu Gothic UI", system-ui, sans-serif'
    fontSize: "14px"
    fontWeight: 600
    lineHeight: 1.2
  title:
    fontFamily: '"Segoe UI Variable Text", "Segoe UI", "Yu Gothic UI", system-ui, sans-serif'
    fontSize: "12px"
    fontWeight: 600
    lineHeight: 1.3
  body:
    fontFamily: '"Segoe UI Variable Text", "Segoe UI", "Yu Gothic UI", system-ui, sans-serif'
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.45
  label:
    fontFamily: '"Segoe UI Variable Text", "Segoe UI", "Yu Gothic UI", system-ui, sans-serif'
    fontSize: "11px"
    fontWeight: 400
    lineHeight: 1.3
  data:
    fontFamily: '"Cascadia Mono", Consolas, monospace'
    fontSize: "11px"
    fontWeight: 400
    lineHeight: 1.3
rounded:
  xs: "3px"
  sm: "4px"
  md: "5px"
  lg: "8px"
spacing:
  1: "2px"
  2: "4px"
  3: "6px"
  4: "8px"
  5: "12px"
  6: "16px"
components:
  button-default:
    backgroundColor: "{colors.surface-control}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.sm}"
    padding: "4px 8px"
    height: "28px"
  button-primary:
    backgroundColor: "#1769aa"
    textColor: "#ffffff"
    rounded: "{rounded.sm}"
    padding: "4px 8px"
    height: "28px"
  button-transport:
    backgroundColor: "#246c49"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.sm}"
    size: "30px"
  field:
    backgroundColor: "#3a4148"
    textColor: "#f2f4f7"
    rounded: "{rounded.sm}"
    padding: "4px 7px"
    height: "30px"
---

# Design System: AdopyHzEditor

## Overview

**Creative North Star: "The Transcription Bench"**

AdopyHzEditor is a focused instrument bench: the audio evidence and hand-authored music data occupy the work surface, while the interface forms a quiet frame around them. Its restraint is functional rather than austere. Compact controls, stable geometry, and a near-black canvas keep repeated listening, reading, selecting, and editing comfortable during long desktop sessions.

The hierarchy is editor-first. The Canvas dominates; transport and navigation support it; the collapsible Inspector follows the current Note or Frequency Track selection; infrequent configuration stays folded under Settings. Color carries operational meaning, never decoration, and the interface avoids ornamental motion, large headings, or promotional styling.

**Key Characteristics:**

- Canvas-dominant desktop composition with compact, persistent chrome.
- Restrained charcoal surfaces separated by borders and tonal steps.
- Contextual editing driven by selection, with configuration folded away.
- Blue for ordinary actions and Notes, cyan for Frequency Tracks, yellow for selection, white for playback position, and gold/red for warnings and errors.
- Stable, dense controls and tabular data readouts built for precision.

## Colors

The palette is a low-chroma dark editor frame around brighter analytical and editing marks. Spectrum imagery keeps its selected analysis colormap; chrome must not tint or compete with it.

### Primary

- **Action Blue:** Ordinary selected tabs, primary-soft actions, sliders, and active editor controls. Use it sparingly so the Canvas remains dominant.
- **Note Blue:** Unselected fixed and Curve Notes on the Canvas; alpha may vary by view mode so Spectrum evidence remains legible underneath.

### Secondary

- **Frequency Cyan:** Unselected Frequency Tracks. Opacity and width encode strength and duration; it is evidence, not a musical classification.
- **Selection Yellow:** Selected Notes, selected Frequency Tracks, resize handles, and Track-region selection. It always accompanies geometry or handles so selection never relies on hue alone.
- **Positive Green:** Playback action and connected/ready status.

### Tertiary

- **Warning Gold:** Dirty-state marks, grid emphasis, fallbacks, and non-destructive warnings.
- **Danger Red:** Errors, destructive cut regions, and destructive feedback.
- **Focus Blue:** The universal keyboard focus outline, including the inset Canvas focus treatment.

### Neutral

- **Canvas Black:** The drawing field behind Spectrum, Tracks, Notes, grid, and cursor.
- **Workspace Black:** The Canvas container fallback while raster data is absent or loading.
- **Base, Chrome, and Control Surfaces:** Three close charcoal steps establish workspace, bars/panels, and interactive controls without card stacks.
- **Primary and Muted Text:** Bright gray carries values and commands; muted gray carries labels, filenames, helper copy, and unavailable context.
- **Divider and Strong Divider:** Thin structural seams and control boundaries replace decorative shadows.
- **Playback White:** The two-pixel playback cursor. White is reserved here for immediate temporal orientation, not general accenting.
- **Region Blue:** The translucent Note-region selection fill; its dashed light outline remains visible over changing Spectrum content.

**The Semantic Canvas Rule.** Blue is editable Note data, cyan is analysis-derived Track evidence, yellow is current selection, and white is current playback time. Never reuse those hues decoratively on the Canvas.

**The Spectrum Is Evidence Rule.** Spectrum color comes from the active analysis colormap and settings. Do not force it into a brand gradient, label its layers as melody/harmony/noise, or let chrome styling reduce its readability.

## Typography

**Display Font:** None; this is an editor, not a presentation surface.
**Body Font:** Segoe UI Variable Text with Segoe UI, Yu Gothic UI, system UI, and sans-serif fallbacks.
**Label/Mono Font:** Cascadia Mono with Consolas and monospace fallbacks.

**Character:** Neutral system UI typography keeps Japanese and Latin controls compact and native-looking. Monospaced numerals provide a steady scan line for time, MIDI, Hz, percentages, and identifiers.

### Hierarchy

- **Headline** (600, 14px, 1.2): Empty-state and Inspector-empty titles only; never a page-scale heading.
- **Title** (600, 12px, 1.3): Panel headings, fold summaries, and concise section emphasis.
- **Body** (400, 12px, 1.45): Settings labels, helper copy, menu actions, and dialog content.
- **Label** (400, 11px, 1.3): Dense tabs, property labels, secondary controls, and compact explanatory text.
- **Data** (400, 11px, 1.3): Time, pitch, Hz, Track IDs, output values, and keyboard hints; use tabular numerals where values update in place.

**The Instrument Readout Rule.** Values that change with playback, cursor movement, or selection use the data face and stable width; prose and control names stay in the system UI face.

## Layout

The shell fills the viewport and uses four fixed-height horizontal bands: title/menu (34px), toolbar (40px), the flexible workspace, and status (24px). Inside the workspace, the editor receives all remaining width and the Inspector occupies 286px. Collapsing the Inspector removes its column entirely rather than leaving dead space. The editor itself gives the Canvas all flexible height, followed by a 24px cursor readout and compact timeline controls.

Spacing follows a tight 2/4/6/8/12/16px rhythm. Four pixels separates controls inside a group; 6–8px separates neighboring controls and field rows; 8–12px pads chrome and compact sections; 16px is reserved for roomier dialog content. Do not inflate the rhythm into dashboard whitespace.

Narrow desktop behavior preserves function and Canvas priority rather than transforming into a mobile layout. Below 1180px the Inspector narrows to 272px, button horizontal padding tightens, and timeline labels may disappear while their fields remain. Below 920px the Inspector narrows to 250px, view controls and time output become more compact, and secondary timeline labels collapse. Tool and dialog grids become single-column near 1100px/900px where necessary. Horizontal overflow, clipped primary actions, and a permanently expanded rail are regressions.

**The Canvas Wins Rule.** New persistent UI must not take space from the Canvas when it can be contextual, collapsible, folded, or placed in an existing menu.

**The Stable Geometry Rule.** Playback, selection, loading, and hover updates must not resize bars, move controls, or reflow the workspace.

**The Rendering Budget Rule.** Keep Spectrum and Track work viewport-bound and generation-safe: reuse decoded/offscreen rasters and region caches, request only the visible time/pitch window at the current pixel dimensions, preserve stale-response gates and prefetch limits, and retain Track level-of-detail that favors coherent long/strong paths when zoomed out. Cursor readout reporting remains throttled, and the lightweight playback cursor remains on its separate overlay Canvas so playback does not redraw the analysis layer.

## Elevation & Depth

The editor is flat by default. Tonal layering and one-pixel borders establish depth among Canvas, chrome, controls, menus, and panels. Shadows are structural and reserved for floating menus and modal windows; the persistent workspace does not use lifted cards.

### Shadow Vocabulary

- **Menu Lift** (`0 12px 32px #0009`): Desktop menu popovers only.
- **Modal Lift** (`0 20px 60px #000a`): Blocking dialog windows over the dark backdrop only.

**The Flat Workbench Rule.** Persistent editor regions are divided by tone and seams, not shadows. A shadow means the element floats above the work and temporarily owns interaction.

## Shapes

The form language is compact and gently squared. The default control corner is 4px; tabs and compact information containers may use 5px; dialogs use 8px. Tiny keyboard keys use 3px. One-pixel borders are standard for fields, controls, warnings, and boundaries. Canvas marks remain geometric: rectangular Notes, thin Track paths, square resize handles, dashed selection regions, and a straight playback cursor.

Avoid excessive containment. Inspector sections and settings folds may have a tonal header or top divider, but they must not become cards inside cards. Pills are limited to genuine status semantics; ordinary labels and actions remain rectangular.

**The One Radius Rule.** Start at 4px for controls and deviate only for a documented structural reason: 3px for tiny keys, 5px for compact containers/tabs, and 8px for modal shells.

## Components

### Buttons

- **Shape:** Compact rectangular controls with a 4px corner, one-pixel border, 28px minimum height, and 4px by 8px padding.
- **Primary:** Action blue is reserved for the current tab or a meaningful contextual action. Playback is the distinct positive-green transport action.
- **Hover / Focus:** Hover raises the control one tonal step and strengthens its border. Keyboard focus uses the universal 2px focus-blue outline with 2px offset. Active/pressed state is exposed programmatically and shown with a filled background.
- **Secondary / Ghost:** Secondary actions use the control surface. Quiet actions are transparent and muted. Disabled controls keep their geometry and accessible label, use the default cursor, and reduce opacity to 48%.

### Cards / Containers

- **Corner Style:** Compact containers use 4–5px; modal shells use 8px.
- **Background:** Use the existing surface ladder or a purpose-specific warning/error tint.
- **Shadow Strategy:** No shadow at rest; only menus and modals lift.
- **Border:** One-pixel dividers communicate structure. Avoid double borders created by nested containers.
- **Internal Padding:** 7–10px for compact readouts and warnings; 12–16px for dialog content.

### Inputs / Fields

- **Style:** Dark raised field surface, bright value text, 4px radius, one-pixel near-black border, and 30–31px minimum height.
- **Focus:** Border shifts to action/focus blue; the global focus-visible outline remains available to keyboard users.
- **Error / Disabled:** Errors use a dark red surface plus red border and explicit text. Disabled fields remain in place at 48% opacity. Numeric inputs preserve editable intermediate text, clamp only on commit, and restore on Escape.

### Navigation

Title/menu, transport/view toolbar, Canvas readout/timeline, and status bar are compact horizontal bands. Menus use desktop arrow, Home, End, Escape, and focus-return behavior. The right rail has two pressed-state tabs—Inspector and Settings—and can be collapsed from a stable toolbar affordance. File operations remain in the File menu, never the toolbar.

### Contextual Inspector

With no selection, show a centered, useful empty state rather than disabled controls. Selecting a Note reveals its time and pitch properties; selecting multiple Notes reveals bulk editing; selecting Frequency Tracks reveals Track IDs/ranges, hover detail, and conversion actions. Selection automatically returns the rail to Inspector. Settings remain grouped in disclosure folds and never displace contextual Track or Note editing onto the Canvas.

### Editor Canvas

The Canvas is a named focusable editing region with a crosshair default cursor and contextual move, resize, and Track pointers. Spectrum is the raster evidence layer; Frequency Tracks sit above it; pitch/time grids provide orientation; Notes remain legible above both; the playback cursor is the final overlay. Selected Notes and Tracks become yellow and gain handles, thicker paths, or explicit outlines. Region and cut selections combine translucent fills with dashed outlines. The empty workspace states the first productive File-menu action and relevant shortcut without adding file buttons to the toolbar.

### Feedback States

Hover provides temporary cursor and Track detail in the persistent Canvas readout; it does not replace operation or error status. Warnings use gold/brown tint, border, and explanatory text. Errors use red tint, border, and text. Empty Inspector and Canvas states explain what to select or open. Dialogs trap focus, close on Escape where safe, restore prior focus, and suppress background editor shortcuts.

## Do's and Don'ts

### Do:

- **Do** preserve the editor-first order: Canvas, supporting playback/navigation, contextual Inspector, then folded Settings.
- **Do** keep ordinary controls within the established 28–32px desktop density while preserving visible focus, labels, and the 24px minimum pointer-target floor.
- **Do** use borders, tonal layers, stable dimensions, and semantic color to communicate state.
- **Do** keep hover information in the Canvas readout and selection-driven actions in the Inspector.
- **Do** preserve keyboard semantics, disabled/error/empty states, wheel mappings, generation guards, selection invariants, and viewport-bound rendering.

### Don't:

- **Don't** add file Open/Save/Import/Export commands to the toolbar; they belong in the File menu.
- **Don't** add dedicated ±1-second seek buttons, Note Preset UI, or a dedicated Quantize button.
- **Don't** put Track actions back on top of the Canvas or expose every setting at once.
- **Don't** build card-in-card layouts, decorative gradients, ornamental animation, oversized headings, or soft marketing-page spacing.
- **Don't** use color alone for selection/status, invent musical meaning for analysis Tracks, or describe Vorbis Direct as AI transcription.
- **Don't** let narrow-desktop compression hide core controls, cause horizontal overflow, or permanently reduce the Canvas more than the documented Inspector widths.
