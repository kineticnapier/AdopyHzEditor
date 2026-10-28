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

- #184: Isolate plain shortcuts from Ctrl/Meta/Alt and preserve assigned combinations; dispatcher regression tests added.\n- #175: Wire Home to absolute seek(0) using the existing App callback; dispatcher regression tests added.\n\nValidation: source changes and tests committed; CI and Windows/pywebview GUI results must be checked before claiming full verification.
