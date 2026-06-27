# Implementation Plan

## Architecture Decision
- Remote target support uses Ansible as backend (avoids duplicating SSH/inventory logic).
- Recipes are JSON/YAML-first; rendered to shell/Ansible/Compose/Pulumi/TOFU at export time.
- Hooks are per-package and global, stored in `~/.config/pob-post-install/hooks/`.
- Time-travel reuses receipt JSON plus optional apt/docker/image snapshots.
- Config editing is read/write through a TUI text editor backed by the local filesystem.

## Completed: Phase 1 — Foundation
- `models/recipe.py`: Recipe dataclass, ExportFormat enum.
- `recipes.py`: Export selected packages to shell script, Ansible playbook, Docker Compose, Pulumi Python, OpenTofu HCL.
- `hooks.py`: Global and per-package pre/post hooks.
- `themes.py`: Theme Manager with dark/light/high-contrast switcher (TUI wired, needs full CSS polish).
- `diff.py`: Compare installed vs desired, generate diff report.
- `timetravel.py`: Browse receipts, diff two runs.
- `health.py`: Package health/security scoring placeholder.
- `updates.py`: Check APT/NPM/PIP for newer versions.
- `editor.py`: Inline config file read/write.
- `remote.py`: Ansible inventory builder and ad-hoc runner.
- `plugins.py`: Plugin registry and external loader.
- `main.py` changes: new Recipes tab, Hooks tab, Theme cycle binding (`t`), Export binding (`e`).

## Next: Phase 2 — Diff and Time-Travel UI
- Add **Diff** tab with desired vs installed comparison.
- Add **Time-Travel** tab with receipt browser and diff view.
- Wire `diff.py` and `timetravel.py` into TUI.

## Next: Phase 3 — Health, Updates, Config Editing
- Add **Health** tab with package scores.
- Add **Updates** tab with available version checks.
- Enable inline config editing from Config tab.

## Next: Phase 4 — Remote and Plugins
- Add **Remote** tab: target list, Ansible run, result viewer.
- Add **Plugins** screen: load external provider scripts.
- Backup before install: snapshot `~/.config/<id>` before modification.

## Next: Phase 5 — Polish
- Batch operations with retry/backoff.
- Integration tests and E2E smoke script.
- Expand health CVE lookup.
