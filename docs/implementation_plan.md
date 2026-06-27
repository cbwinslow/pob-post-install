# Implementation Plan

## Architecture Decision
- Remote target support uses Ansible as backend (avoids duplicating SSH/inventory logic).
- Recipes are JSON/YAML-first; rendered to shell/Ansible/Compose/Pulumi/TOFU at export time.
- Hooks are per-package and global, stored in `~/.config/pob-post-install/hooks/`.
- Time-travel reuses receipt JSON plus optional apt/docker/image snapshots.
- Config editing is read/write through a TUI text editor backed by the local filesystem.

## Progress

### Phase 1 — Foundation ✅
- `models/recipe.py`: Recipe dataclass, ExportFormat enum.
- `recipes.py`: Export selected packages to shell script, Ansible playbook, Docker Compose, Pulumi Python, OpenTofu HCL.
- `hooks.py`: Global and per-package pre/post hooks.
- `themes.py`: Theme Manager with dark/light/high-contrast switcher (TUI wired).
- `diff.py`: Compare installed vs desired, generate diff report.
- `timetravel.py`: Browse receipts, diff two runs.
- `health.py`: Package health/security scoring placeholder.
- `updates.py`: Check APT/NPM/PIP for newer versions.
- `editor.py`: Inline config file read/write.
- `remote.py`: Ansible inventory builder and ad-hoc runner.
- `plugins.py`: Plugin registry and external loader.

### Phase 2 — Diff and Time-Travel UI ✅
- Added **Diff** tab (`Ctrl+D`) showing desired vs installed counts, missing packages, extra packages.
- Added **Time Travel** tab (`Shift+T`) listing receipt JSON files.
- New buttons: Run Diff, Load Receipts, Diff Selected.

### Phase 3 — Health, Updates, Config Editing, Remote, Plugins ✅
- **Health** tab (`Ctrl+H`) with package score table.
- **Updates** tab (`Ctrl+U`) with available version checks for APT/NPM/PIP.
- **Config Editor** modal: open text editor for config files from the Config tab.
- **Remote** tab: Ansible ad-hoc runner with target input and result table.
- **Plugins** tab: load external provider scripts from `~/.config/pob-post-install/plugins/`.

### Phase 4 — Remaining Items
- Recipe marketplace: share/import community package lists.
- Backup before install: snapshot `~/.config/<id>` before modification.
- Batch operation improvements with retry/backoff.
- Expand health CVE lookup.
- Wire more providers into History Discovery.

## Commands
- `make run` — launch TUI
- `make test` — run tests
- `make typecheck` — run type checker
