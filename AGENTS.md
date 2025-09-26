# Agent Instructions

Welcome! These guidelines apply to the entire repository.

## Coding Style
- Prefer Python 3.11 compatible syntax for backend code.
- Format Python code with `ruff format` and lint using `ruff check` before submission when possible.
- Keep imports sorted using `ruff check --select I`.

## Testing
- Run the most relevant test suite for the area you changed. At minimum, execute `pytest` for backend changes and `npm test` for UI work when applicable.

## Documentation
- Update associated README or docs when behavior changes.
- Include meaningful commit messages and PR descriptions summarizing the impact of the change.

## Miscellaneous
- Avoid committing secrets or large binary assets unless necessary.
- Ensure new files include appropriate licenses or headers if required.

Thank you for contributing!
