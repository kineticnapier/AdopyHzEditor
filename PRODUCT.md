# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

AdopyHzEditor is for people who transcribe music by listening and reading frequency information over long editing sessions. The primary user needs precise control over timing and pitch, including fractional MIDI pitches and curve notes, and expects a dense desktop editing workspace rather than a simplified consumer flow.

## Product Purpose

AdopyHzEditor is a semi-manual transcription editor. Its core loop is:

1. Open and listen to an audio source.
2. Read its Spectrum and Frequency Tracks.
3. Place and edit Note and Curve Note data by hand.
4. Listen again and refine.
5. Export the result to MIDI or an ADOFAI Hz Chart.

Success means the user can move repeatedly through listening, reading, selecting, and editing without unrelated interface chrome interrupting the work.

## Positioning

AdopyHzEditor treats analysis as evidence for a human editor, not as an automatic transcription authority. Vorbis Direct follows `OGG → frequency information → human transcription → Note[] → ADOFAI`; it must not be reframed as `OGG → AI-generated chart`.

## Operating Context

- The main work surface combines Spectrum, Frequency Tracks, Notes, a playback cursor, pitch, and time.
- Frequent actions are play/stop, seek, time and pitch navigation, Track inspection, and Note/Curve Note creation and editing.
- Project work must preserve Undo/Redo, dirty-state, selection, playback-preview synchronization, and safe file operations.
- File opening, project loading/saving, MIDI import/export, and ADOFAI export live in the File menu rather than occupying the primary toolbar.
- The application targets desktop-sized windows, including narrower desktop layouts; it is not a mobile-first website.

## Capabilities and Constraints

- Supports CQT Spectrum and Vorbis Direct Raw Spectrum/Frequency Tracks.
- Supports fixed Notes, Curve Notes, Track selection, and Track-to-Note conversion.
- Supports MIDI import/export and ADOFAI Hz Chart export.
- Wheel pans time; Ctrl+Wheel zooms time; Shift+Wheel pans pitch; Alt+Wheel zooms pitch. These mappings are established behavior.
- Existing public APIs, project format, and ADOFAI/MIDI compatibility remain stable unless a product requirement explicitly demands a change.
- Existing generation guards, selection invariants, numeric-input behavior, and performance boundaries must not regress during UI work.
- Track readability and LOD favor coherent, long, strong tracks at wider zoom levels while retaining detail when zoomed in. The UI must not invent musical labels such as fundamental, harmonic, melody, or noise.
- Dedicated file-operation toolbar buttons, ±1 second seek buttons, Note Preset UI, and a dedicated Quantize button are intentionally absent.

## Evidence on Hand

- The React/TypeScript editor is implemented under `frontend/src/`.
- Backend state, analysis, editing, import, and export behavior is covered by Python regression tests under `tests/`.
- Frontend interaction, request-generation, navigation, and rendering helpers are covered under `frontend/tests/`.
- The repository does not contain user research, usage telemetry, or claims that should be fabricated as product evidence.

## Product Principles

1. **Canvas first.** The central Editor Canvas is the product; playback/navigation supports it, the contextual Inspector follows it, and Settings remain subordinate.
2. **Keep the transcription loop short.** Listening, reading Spectrum/Tracks, editing Notes, and listening again should require minimal pointer travel and no unnecessary modal steps.
3. **Show context, not every control.** Hover reveals temporary reading information; selection drives the Inspector; infrequent configuration stays folded under Settings.
4. **Precision over decoration.** Dense information, stable geometry, meaningful color, clear focus, and fast feedback matter more than cards, gradients, large headings, or ornamental motion.
5. **Analysis assists human judgment.** Preserve raw evidence and readable Tracks without pretending the analysis understands musical intent.

## Accessibility & Inclusion

- All controls require visible keyboard focus, accessible names, associated labels, and useful disabled/error states.
- Dialogs suppress background shortcuts and expose a coherent keyboard path.
- Selection and status must not rely on color alone.
- Controls need practical pointer targets without reducing the information density expected of a desktop editor.
