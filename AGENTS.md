# AGENTS.md

## General rules

- Prefer small, focused changes.
- Do not rewrite unrelated files.
- Do not perform broad refactors unless explicitly requested.
- Explain the cause or plan briefly before making non-trivial changes.
- After editing, run the minimum relevant check needed to confirm the change.
- If a change may affect existing behavior, explain the risk before applying it.
- Preserve existing public APIs, file structure, and keyboard shortcuts unless explicitly asked to change them.

## Ignore directories

- Do not inspect or modify files inside `.venv`, `.vscode`, or `__pycache__`.
- These directories are environment, editor, or cache files and are not relevant to the application logic.
- Also avoid `dist`, `build`, and `.git` unless explicitly requested.

## Python environment

* When running Python commands, use the project virtual environment.
* On Windows, prefer `.venv\Scripts\python.exe`.
* Do not activate, inspect, or modify files inside `.venv` unless explicitly requested.
* Do not install new packages unless necessary.
* If a new package is required, explain why before installing it.

Examples:

```powershell
.\.venv\Scripts\python.exe main.py
.\.venv\Scripts\python.exe -m pytest
```

## Project rules

* Keep UI logic, audio preview logic, MIDI export logic, and ADOFAI export logic separated when possible.
* Do not change note positions on the grid unless explicitly requested.
* Visual note positions and playback/export pitch must be treated separately.
* Octave offset should affect preview audio, MIDI export, and ADOFAI export.
* Octave offset must not move notes visually on the grid.
* Avoid assigning new actions to the Space key unless explicitly requested, because it is likely to conflict with existing shortcuts.
* When adding or changing keyboard shortcuts, check for conflicts with existing shortcuts first.
* Keep the UI compact when possible.
* Avoid unnecessary icons or decorative elements that increase horizontal width.

## Debugging rules

* Reproduce the issue before changing code when possible.
* Prefer fixing the root cause instead of hiding errors.
* Do not silence exceptions unless there is a clear reason.
* If an error is caused by missing dependencies, environment setup, or working directory issues, explain that instead of rewriting unrelated code.
* When a command fails, read the error message and fix only the relevant issue.

## Output rules

* Summarize changed files after editing.
* Mention what checks were run.
* If checks were not run, explain why.
* Keep explanations concise.


