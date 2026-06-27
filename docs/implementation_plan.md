# Implementation Plan

## Architecture Decision
- Use Ansible as the backend for remote target support (12/14 items). Native SSH is deferred.
- Recipes are JSON/YAML-first; rendered to shell/Ansible/Compose/Pulumi/TOFU at export time.
- Hooks are per-package and global, stored alongside receipts.
- Time-travel reuses receipt JSON plus optional apt/docker/image snapshots.
- Config editing is read/write through a TUI text editor backed by the local filesystem; remote editing goes through Ansible delegated tasks.

## Phased Delivery

### Phase 1 — Foundation
1. `models/recipe.py`: Recipe dataclass, ExportFormat enum, provider adapters.
2. `recipes.py`: Export selected packages to shell script, Ansible playbook, Docker Compose, Pulumi Python, OpenTofu HCL.
3. `hooks.py`: Global and per-package pre/post hooks; hook discovery in `~/.config/pob-post-install/hooks/`.
4. `themes.py`: Theme Manager, light/dark/high-contrast CSS switcher.
5. TUI: Add Recipes tab, Hooks tab, Theme switcher binding.

### Phase 2 — Diff and Time-Travel
6. `diff.py`: Compare installed vs desired, generate diff report, highlight extras.
7. `timetravel.py`: Browse receipts, diff two runs, replay from checkpoint.
8. TUI: Add Diff tab, Time-Travel tab, receipt browser modal.

### Phase 3 — Health, Updates, Config Editing
9. `health.py`: Score packages by popularity (APT downloads / npm / PyPI), flag EOL packages, optional CVE lookup placeholder.
10. `updates.py`: Query APT/NPM/PIP/PUIPM/TOFU for newer versions.
11. `editor.py`: Inline text editor for config files in Config tab.
12. TUI: Add Health tab, Updates tab, inline config editor.

### Phase 4 — Remote and Plugins
13. `remote.py`: Ansible inventory builder, ad-hoc runner, result parser.
14. `plugins.py`: Plugin registry, external script/provider registration, plugin loader.
15. TUI: Add Remote tab, plugin manager screen.

### Phase 5 — Polish
16. Backup before install (snapshot `~/.config/<id>` and `/opt/<id>` for github_repo).
17. Batch operation improvements with retry/backoff.
18. Integration tests and E2E smoke test script.
