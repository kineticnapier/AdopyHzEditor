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
