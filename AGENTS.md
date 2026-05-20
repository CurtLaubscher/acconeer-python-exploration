# AGENTS.md

Use the repo-managed runtime and tooling defined in `pyproject.toml`.

## Environment Rules

- Check `pyproject.toml` before running tools, tests, or GUI utilities.
- Use the repo-defined Hatch environments and scripts from `pyproject.toml` instead of guessing runtime commands.
- Prefer repo-managed environments over bare `python`, `pytest`, or ad hoc `pip install`.

## Dependency Rules

- Keep `pyproject.toml` up to date when code introduces new runtime dependencies.
- Add dependencies to the appropriate sections in `pyproject.toml` so runtime and tooling stay reproducible.
- Do not install missing packages only into the ambient user interpreter as a fix for repo code. Fix the Hatch-managed environment definition instead.

## Test And Tooling Rules

- Prefer repo-defined scripts and environments from `pyproject.toml` for tests and tooling.
- If you must run a one-off module directly, first check whether `pyproject.toml` already defines a better command or environment for it.
- When documenting launch commands in code or docs, keep the concrete command in `pyproject.toml` and avoid duplicating script inventories here.

## OpenSpec Git Rules

- For OpenSpec implementation branches, use `<user-account>/<openspec-change-name>`, where `<user-account>` is the local user account name rather than a hard-coded branch owner.
- When merging an OpenSpec branch into `master`, use a no-fast-forward merge so the merge commit preserves the OpenSpec change name in history.
- Prefer merge commit messages that include the OpenSpec change name, such as `Merge OpenSpec <openspec-change-name>`.
