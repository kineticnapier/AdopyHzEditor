# Consolidated Issue Fix Batch

This branch is the single working branch for accumulating verified fixes to open issues in AdopyHzEditor.

## Workflow

- Before each change, check open/closed issues and existing pull requests to avoid duplicate work.
- Implement fixes on this branch and add focused regression tests.
- Reference each addressed issue in the consolidated pull request and relevant commit messages.
- Do not claim an issue fixed until code and tests support it.
- Do not automatically merge the pull request.
- Preserve the repository's existing behavior and compatibility except for explicitly documented fixes.

## Implemented issues

- #184: Isolate plain shortcuts from Ctrl/Meta/Alt and preserve assigned combinations; dispatcher regression tests added.
- #175: Wire Home to absolute seek(0) using the existing App callback; dispatcher regression tests added.
- #138: Respect horizontal wheel direction while retaining vertical navigation and modifier behavior; five regression tests added.
- #222: Preserve note-extended document duration through CQT/Direct reanalysis and project/audio source commit; six regression tests added.

Validation (code commit `424afdf6`): Web UI check passed (230 Python tests, 11 skipped; 36 frontend tests passed; frontend build passed). Windows package check was still running and physical Windows/pywebview GUI and real-audio checks remain unverified. Issues remain open; PR remains Draft.

## 2026-10-29 UI numeric input follow-up (branch only)

- Refs #80: `ToolDialogs.tsx:Num` and `AdoFAIExportDialogJa.tsx:Num` now keep a draft string until blur/Enter; Escape cancels the field without closing the modal. New `frontend/tests/dialogNumericInput.test.ts` covers both source contracts and numeric model cases.
- Implementation commits: `73bb6cd`, `73760ae`, `ef871b2`, `0ca7328`; test commits: `333d61e`, `ba66cb2`.
- Validation: 20 source-contract / mirrored numeric-model conditions passed using the latest GitHub branch files. **Not run:** repository `npm test`, `npm run build`, CI, React DOM tests, Windows GUI. Issue #80 is open; no `Fixes` claim.
- PR #223 remains **closed, Draft, unmerged**. Branch commits are not in its frozen diff. No new PR, branch, merge, or review-state change.
