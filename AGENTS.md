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

## Collaboration Rules

- After exploratory discussion, planning, or proposing commit-sized work, wait for the user's explicit implementation green light before editing files, creating branches, or committing.
- Treat clear confirmations such as "ok", "green light", "go ahead", or equivalent wording as permission to proceed with the agreed implementation scope.
- Before moving from discussion into implementation, make the transition clear so the user can correct scope or sequencing first.

## Ideas Document Rules

- Treat `openspec/specs/heatmap-alignment-gui/ideas.md` as a living planning file, not an archive of completed work.
- When a branch fixes, rejects, supersedes, or deliberately defers an item from `ideas.md`, update that file in the same branch when practical.
- Keep the `Current Triage` section synchronized with the detailed themed sections below it.
- Remove fixed bug bullets instead of leaving them in place as historical notes unless remaining context is still actionable.

## Git Branch Rules

- Before editing files for branch-scoped work, check the current branch.
- If the current branch is `master` or otherwise unrelated to the requested work, create or switch to an appropriately named branch before editing.
- Prefer branch names that identify the owner/account and the work, such as `<user-account>/<work-name>` or a user-requested branch pattern.
- For OpenSpec implementation branches, use the OpenSpec change name as the work name when practical.

## Git Commit Rules

- When creating non-merge commits, use the `$commit-bullets` skill if available.
- Keep commits commit-sized and focused.
- Do not include unrelated cleanup in a commit unless it is required for the change.

## Git Merge Rules

- Use no-fast-forward merges (`git merge --no-ff`) for branch integration.
- When creating a merge commit, use the `$commit-bullets` skill if available.
- For non-trivial merges, include a merge commit body that summarizes the merged branch as a whole, not just the final commit or conflict resolution.
- Merge commit bodies should briefly cover scope, motivation, validation, and known limits or follow-up work when relevant.
- Keep merge subject lines concise, such as `Merge <branch-name>`, `Merge <work-summary>`, or for OpenSpec changes `Merge OpenSpec <openspec-change-name>`.

## OpenSpec Git Rules

- For OpenSpec implementation work, keep the branch name tied to the OpenSpec change name when practical.
- Prefer merge subjects that include the OpenSpec change name, such as `Merge OpenSpec <openspec-change-name>`.
- OpenSpec merges still follow the general Git Merge Rules above, including no-fast-forward merges and branch-level merge message bodies for non-trivial work.
