from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Label,
    Log,
    ProgressBar,
    RadioButton,
    RadioSet,
    Static,
    Switch,
    TabbedContent,
    TabPane,
    Input,
)
from textual.binding import Binding
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual import on

from pob_post_install.models.package import Category, Package
from pob_post_install.providers.base import get_provider
from pob_post_install.receipts import ReceiptLogger
from pob_post_install.rollback import RollbackManager
from pob_post_install.inventory import InventoryCollector
from pob_post_install.history_discovery import HistoryDiscovery
from pob_post_install.diff import DiffEngine
from pob_post_install.timetravel import TimeTravel
from pob_post_install.themes import ThemeManager
from pob_post_install.hooks import HookManager
from pob_post_install.recipes import RecipeExporter, Recipe
from pob_post_install.models.recipe import ExportFormat


class CategorySidebar(Static):
    CATEGORY_ICONS = {
        Category.SYSTEM: "⚙️",
        Category.SECURITY: "🔒",
        Category.TERMINAL: "💻",
        Category.NETWORKING: "🌐",
        Category.DEV: "🛠️",
        Category.LANGUAGES: "🧑‍💻",
        Category.DATABASES: "🗄️",
        Category.CONTAINERS: "📦",
        Category.DOCKER: "🐳",
        Category.WEB: "🌍",
        Category.AI: "🤖",
        Category.IAC: "🏗️",
        Category.MONITORING: "📊",
        Category.GITHUB: "🐙",
        Category.CUSTOM: "⚡",
    }

    def __init__(self, categories: list[Category], **kwargs):
        super().__init__(**kwargs)
        self.categories = categories

    def compose(self) -> ComposeResult:
        yield Static("Categories", classes="sidebar-title")
        yield RadioSet(*[RadioButton(f"{self.CATEGORY_ICONS.get(c, '')} {c.value}", id=f"cat-{c.value}") for c in self.categories])


class SearchInput(Input):
    pass


class PackageTable(DataTable):
    pass


class StatusSpinner(Static):
    BRAILLE_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def __init__(self, **kwargs):
        super().__init__("", **kwargs)
        self._frame_index = 0
        self._running = False

    def spin(self, text: str = "Running") -> None:
        self._running = True
        self._text = text
        self._update_frame()

    def stop(self) -> None:
        self._running = False
        self.update("")

    def _update_frame(self) -> None:
        if not self._running:
            return
        frame = self.BRAILLE_FRAMES[self._frame_index % len(self.BRAILLE_FRAMES)]
        self.update(f"{frame} {self._text}")
        self._frame_index += 1
        self.set_interval(0.08, self._update_frame, name="braille-spin")


class SummaryScreen(ModalScreen):
    CSS = """
    SummaryScreen {
        align: center middle;
    }
    #summary-dialog {
        width: 80;
        height: 24;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    #summary-text {
        height: 1fr;
        overflow-y: auto;
    }
    """

    def __init__(self, receipt: dict, **kwargs):
        super().__init__(**kwargs)
        self.receipt = receipt

    def compose(self) -> ComposeResult:
        yield Static("Run Summary", classes="modal-title")
        container = Vertical(id="summary-dialog")
        yield container
        with container:
            yield Static(self._render(), id="summary-text")
            with Horizontal():
                yield Button("Close", variant="primary", id="btn-close")
                yield Button("Retry Failures", variant="error", id="btn-retry")

    def _render(self) -> str:
        r = self.receipt
        s = r.get("summary", {})
        lines = [
            f"Run ID: {r.get('run_id', '?')}",
            f"Host:   {r.get('host', '?')} on {r.get('started_at', '?')}",
            f"Total:  {s.get('total', 0)}   OK: {s.get('ok', 0)}   Fail: {s.get('fail', 0)}   Skipped: {s.get('skipped', 0)}",
            "",
        ]
        for item in r.get("items", []):
            status = "OK " if item.get("ok") else "FAIL"
            lines.append(f"[{status}] {item.get('id', '?')} — {item.get('message', '')[:120]}")
        return "\n".join(lines)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close":
            self.app.pop_screen()
        elif event.button.id == "btn-retry":
            self.app.pop_screen()
            self.app.action_retry_failures()


class InstallerApp(App):
    CSS = """
    Screen {
        background: $background;
    }
    Horizontal {
        height: 1fr;
    }
    #sidebar {
        width: 30;
        dock: left;
        padding: 1;
        background: $panel;
        border: thick $primary;
    }
    #main {
        height: 1fr;
        padding: 1;
    }
    #packages {
        height: 1fr;
        border: thick $primary;
        background: $boost;
    }
    #packages PackageTable {
        background: $boost;
    }
    #packages PackageTable > .datatable--cursor {
        background: $primary;
        color: $text;
    }
    #packages PackageTable > .datatable--hover {
        background: $primary 15%;
    }
    #log {
        height: 15;
        border: thick $primary;
        background: $boost;
        padding: 1;
    }
    #progress-container {
        height: 5;
        padding: 0 1;
    }
    .sidebar-title {
        text-style: bold;
        background: $primary;
        color: $text;
        padding: 0 1;
        margin-top: 1;
    }
    #status-bar {
        height: 1;
        background: $panel;
        color: $text;
        padding: 0 1;
        text-style: bold;
    }
    #config-panel {
        padding: 1;
        height: 1fr;
        overflow-y: auto;
    }
    .section-title {
        text-style: bold;
        background: $primary;
        color: $text;
        padding: 0 1;
        margin-top: 1;
    }
    .config-path {
        color: $accent;
        text-style: bold;
    }
    .config-file {
        color: $text;
        padding-left: 2;
    }
    #inventory-panel {
        padding: 1;
        height: 1fr;
        overflow-y: auto;
    }
    #search-controls {
        height: 3;
        padding: 1;
    }
    #search-results {
        height: 1fr;
        border: thick $primary;
        background: $boost;
    }
    #container-status {
        color: $accent;
        text-style: bold;
    }
    #spinner-indicator {
        width: 3;
        content-align: center middle;
        text-style: bold;
        color: $accent;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh_status", "Refresh"),
        Binding("a", "select_all", "Select All"),
        Binding("n", "select_none", "Select None"),
        Binding("enter", "run_selected", "Install Selected"),
        Binding("slash", "focus_search", "Focus Search"),
        Binding("c", "toggle_config", "Config"),
        Binding("p", "save_profile", "Save Profile"),
        Binding("l", "load_profile", "Load Profile"),
        Binding("u", "undo_last", "Undo Last Run"),
        Binding("f", "check_conflicts", "Check Conflicts"),
        Binding("ctrl+u", "self_update", "Self Update"),
        Binding("i", "refresh_inventory", "Inventory"),
        Binding("d", "scan_history", "Scan History"),
        Binding("shift+d", "scan_ansible", "Scan Ansible"),
        Binding("e", "export_recipe", "Export Recipe"),
        Binding("t", "cycle_theme", "Cycle Theme"),
        Binding("shift+d", "run_diff", "Run Diff"),
        Binding("shift+t", "load_timetravel", "Time Travel"),
    ]

    packages: list[Package] = []
    current_category: reactive[Optional[Category]] = reactive(None)
    is_running: reactive[bool] = reactive(False)
    progress: reactive[float] = reactive(0.0)
    search_query: reactive[str] = reactive("")
    dry_run: reactive[bool] = reactive(False)
    selected_map: reactive[dict[str, bool]] = reactive({})
    conflict_errors: reactive[list[str]] = reactive([])
    dependency_warnings: reactive[list[str]] = reactive([])
    container_runtime: reactive[str] = reactive("unknown")
    inventory: reactive[dict[str, Any]] = reactive({})
    _discovery_items: list[dict] = []
    _diff_result: dict[str, Any] = {}
    _timetravel_receipts: list[Path] = []

    def __init__(self, packages: list[Package], **kwargs):
        super().__init__(**kwargs)
        self._packages = packages
        self._receipt_logger = ReceiptLogger()
        self._rollback_manager: RollbackManager | None = None
        self._last_receipt_path: Path | None = None
        self._mounted = False
        self._hook_manager = HookManager()
        self._theme = "dark"
        self._recipies: list[Recipe] = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="sidebar"):
                yield CategorySidebar(
                    categories=sorted({p.category for p in self._packages}),
                )
                yield Static("Search", classes="sidebar-title")
                yield SearchInput(placeholder="Search packages...", id="search-input")
                yield Static("Options", classes="sidebar-title")
                yield Switch(value=False, id="dry-run-switch")
                yield Label("Dry Run")
                yield Static("Status", classes="sidebar-title")
                yield Static("Unknown", id="container-status")
            with Vertical(id="main"):
                with Horizontal(id="progress-container"):
                    yield Static("Progress:", id="progress-label")
                    yield ProgressBar(total=100, show_eta=False, id="progress-bar")
                    yield StatusSpinner(id="spinner-indicator")
                yield Static("[b]Idle[/b]", id="status-bar")
                with TabbedContent(id="tabbed"):
                    with TabPane("Packages", id="tab-packages"):
                        yield PackageTable(id="packages", cursor_type="row")
                    with TabPane("Config", id="tab-config"):
                        with ScrollableContainer(id="config-scroll"):
                            yield Static("Select packages on the Packages tab to browse their configuration files.", id="config-panel")
                    with TabPane("Search", id="tab-search"):
                        yield Static("Search APT or PyPI packages and inspect them before adding.", id="search-hint")
                        yield Horizontal(
                            Input(placeholder="Search query...", id="search-query"),
                            Button("Search APT", id="btn-search-apt", variant="primary"),
                            Button("Search PyPI", id="btn-search-pypi", variant="success"),
                            id="search-controls"
                        )
                        yield DataTable(id="search-results", cursor_type="row")
                    with TabPane("Log", id="tab-log"):
                        yield Log(id="log", auto_scroll=True, max_lines=500)
                    with TabPane("Inventory", id="tab-inventory"):
                        yield Static("System inventory will appear here. Press 'i' to refresh.", id="inventory-panel")
                    with TabPane("Discovery", id="tab-discovery"):
                        with Horizontal(id="discovery-controls"):
                            yield Button("Scan History", id="btn-scan-history", variant="primary")
                            yield Button("Scan Ansible", id="btn-scan-ansible", variant="warning")
                            yield Button("Import Selected", id="btn-import-discovery", variant="success")
                        yield Static("Press Scan History to inspect terminal history for installs.", id="discovery-hint")
                        yield PackageTable(id="discovery-table", cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        self._mounted = True
        self._detect_container_runtime()
        table = self.query_one("#packages", PackageTable)
        table.add_column("Selected", key="selected", width=8)
        table.add_column("Name", key="name")
        table.add_column("Description", key="desc")
        table.add_column("Provider", key="provider")
        table.add_column("Status", key="status")
        table.zebra_stripes = True
        table.cursor_type = "row"
        self.packages = self._packages
        self.write_log("Ready. Select packages and press Enter to install.")
        self.write_log(f"Container runtime detected: {self.container_runtime}")

    def _detect_container_runtime(self) -> None:
        runtime = "unknown"
        if os.path.exists("/var/run/docker.sock"):
            runtime = "docker"
        elif shutil.which("podman"):
            runtime = "podman"
        elif shutil.which("nerdctl"):
            runtime = "nerdctl"
        self.container_runtime = runtime
        status = self.query_one("#container-status", Static)
        status.update(f"{runtime}")

    def watch_current_category(self, old: Optional[Category], new: Optional[Category]) -> None:
        if self._mounted:
            self.refresh_package_list()

    def watch_search_query(self, old: str, new: str) -> None:
        if self._mounted:
            self.refresh_package_list()

    def watch_progress(self, old: float, new: float) -> None:
        if self._mounted:
            bar = self.query_one("#progress-bar", ProgressBar)
            bar.progress = new

    def watch_is_running(self, old: bool, new: bool) -> None:
        if not self._mounted:
            return
        self.query_one("#packages").disabled = new
        status = self.query_one("#status-bar", Static)
        spinner = self.query_one("#spinner-indicator", StatusSpinner)
        if new:
            status.update("[bold yellow]Running...[/]")
            spinner.spin("Installing")
        else:
            status.update("[bold green]Idle[/]")
            spinner.stop()

    def watch_selected_map(self, old: dict[str, bool], new: dict[str, bool]) -> None:
        pass

    def watch_conflict_errors(self, old: list[str], new: list[str]) -> None:
        if self._mounted and new:
            self.write_log(f"[WARN] {len(new)} conflict(s) detected. Press 'f' to review.")

    def watch_dependency_warnings(self, old: list[str], new: list[str]) -> None:
        if self._mounted and new:
            self.write_log(f"[INFO] {len(new)} dependency note(s). Press 'f' to review.")

    def watch_inventory(self, old: dict[str, Any], new: dict[str, Any]) -> None:
        if self._mounted:
            self._render_inventory(new)

    def write_log(self, message: str) -> None:
        log = self.query_one("#log", Log)
        log.write_line(message)

    def refresh_package_list(self) -> None:
        table = self.query_one("#packages", PackageTable)
        table.clear(columns=False)
        filtered = self.packages
        if self.current_category:
            filtered = [p for p in self.packages if p.category == self.current_category]
        if self.search_query:
            q = self.search_query.lower()
            filtered = [
                p
                for p in filtered
                if q in p.name.lower() or q in p.description.lower() or q in p.id.lower()
            ]
        for pkg in filtered:
            provider = get_provider(pkg.provider)
            status = provider.check(pkg)
            pkg.status = status
            status_icon = {"installed": "✅", "missing": "⬜", "error": "❌"}.get(status, "❓")
            selected = "[x]" if self.selected_map.get(pkg.id, False) else "[ ]"
            try:
                table.add_row(
                    selected,
                    pkg.name,
                    pkg.description,
                    pkg.provider.value,
                    status_icon,
                    key=pkg.id,
                )
            except Exception:
                pass

    def action_refresh_status(self) -> None:
        self.write_log("Refreshing package status...")
        self.refresh_package_list()
        self.write_log("Status refreshed.")

    def action_select_all(self) -> None:
        table = self.query_one("#packages", PackageTable)
        for row in table.rows:
            key = row.value
            self.selected_map[key] = True
        self.refresh_package_list()

    def action_select_none(self) -> None:
        table = self.query_one("#packages", PackageTable)
        for row in table.rows:
            key = row.value
            self.selected_map[key] = False
        self.refresh_package_list()

    def action_focus_search(self) -> None:
        self.query_one("#search-input", SearchInput).focus()

    def action_toggle_config(self) -> None:
        tabbed = self.query_one("#tabbed", TabbedContent)
        config_tab = self.query_one("#tab-config", TabPane)
        tabbed.active = config_tab
        self._render_config()

    def _render_config(self) -> None:
        selected_ids = [k for k, v in self.selected_map.items() if v]
        container = self.query_one("#config-container", Vertical)
        container.remove_children()
        if not selected_ids:
            container.mount(Static("Select packages on the Packages tab to browse their configuration files."))
            return
        for pkg_id in selected_ids:
            pkg = next((p for p in self.packages if p.id == pkg_id), None)
            if not pkg:
                continue
            container.mount(Static(f"[b]{pkg.name}[/b] ({pkg.id})", classes="section-title"))
            info_lines = [f"Provider: {pkg.provider.value}"]
            if pkg.config:
                for k, v in pkg.config.items():
                    info_lines.append(f"  {k} = {v}")
            if pkg.install_args:
                info_lines.append(f"Install args: {' '.join(pkg.install_args)}")
            if pkg.verify_cmd:
                info_lines.append(f"Verify: {pkg.verify_cmd}")
            if pkg.post_install_msg:
                info_lines.append(f"[yellow]Post-install note:[/yellow] {pkg.post_install_msg}")
            if pkg.dependencies:
                info_lines.append(f"[cyan]Dependencies:[/cyan] {', '.join(pkg.dependencies)}")
            if pkg.conflicts:
                info_lines.append(f"[red]Conflicts:[/red] {', '.join(pkg.conflicts)}")
            container.mount(Static("\n".join(info_lines)))
            config_found = self._scan_and_mount_config(container, pkg_id)
            if not config_found:
                container.mount(Static("  No configuration directories found in ~/.config or home.", classes="config-file"))

    def _scan_config_lines(self, pkg_id: str) -> list[str]:
        home = Path.home()
        candidate_dirs = [
            home / ".config" / pkg_id,
            home / f".{pkg_id}",
            home / ".local" / "share" / pkg_id,
        ]
        lines: list[str] = []
        found_any = False
        for config_dir in candidate_dirs:
            if not config_dir.exists() or not config_dir.is_dir():
                continue
            found_any = True
            lines.append(f"[bold cyan]{config_dir}[/bold cyan]")
            try:
                entries = sorted(config_dir.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
                for entry in entries[:100]:
                    icon = "📄" if entry.is_file() else "📁"
                    size = ""
                    if entry.is_file():
                        try:
                            size = f" ({entry.stat().st_size} bytes)"
                        except OSError:
                            size = ""
                    lines.append(f"  {icon} {entry.name}{size}")
                if len(entries) > 100:
                    lines.append(f"  ... and {len(entries) - 100} more entries")
            except PermissionError:
                lines.append("  [red]Permission denied[/red]")
            except OSError as e:
                lines.append(f"  [red]Error: {e}[/red]")
        if not found_any:
            lines.append("  No configuration directories found in ~/.config or home.")
        return lines

    def _scan_and_mount_config(self, container: Vertical, pkg_id: str) -> bool:
        home = Path.home()
        candidate_dirs = [
            home / ".config" / pkg_id,
            home / f".{pkg_id}",
            home / ".local" / "share" / pkg_id,
        ]
        found_any = False
        for config_dir in candidate_dirs:
            if not config_dir.exists() or not config_dir.is_dir():
                continue
            found_any = True
            container.mount(Static(f"[bold cyan]{config_dir}[/bold cyan]", classes="config-path"))
            try:
                entries = sorted(config_dir.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
                for entry in entries[:100]:
                    icon = "📄" if entry.is_file() else "📁"
                    size = ""
                    if entry.is_file():
                        try:
                            size = f" ({entry.stat().st_size} bytes)"
                        except OSError:
                            size = ""
                    container.mount(Static(f"  {icon} {entry.name}{size}", classes="config-file"))
                if len(entries) > 100:
                    container.mount(Static(f"  ... and {len(entries) - 100} more entries", classes="config-file"))
            except PermissionError:
                container.mount(Static("  [red]Permission denied[/red]", classes="config-file"))
            except OSError as e:
                container.mount(Static(f"  [red]Error: {e}[/red]", classes="config-file"))
        return found_any

    async def action_refresh_inventory(self) -> None:
        self.write_log("Scanning system inventory...")
        collector = InventoryCollector()
        data = await collector.collect()
        self.inventory = data
        self.write_log(f"Inventory collected: {sum(len(v) if isinstance(v, list) else 1 for v in data.values())} groups")
        tabbed = self.query_one("#tabbed", TabbedContent)
        inv_tab = self.query_one("#tab-inventory", TabPane)
        tabbed.active = inv_tab

    def _render_inventory(self, data: dict[str, Any]) -> None:
        panel = self.query_one("#inventory-panel", Static)
        lines: list[str] = []
        os_info = data.get("os", {})
        if os_info:
            lines.append("[b]System[/b]")
            for k in ("distro", "version", "kernel", "hostname"):
                if k in os_info:
                    lines.append(f"  {k}: {os_info[k]}")
            lines.append("")
        apt = data.get("apt", [])
        if apt:
            lines.append(f"[b]APT Packages[/b] ({len(apt)} installed)")
            for pkg in apt[:20]:
                lines.append(f"  {pkg.get('name', '?')} {pkg.get('version', '?')}")
            if len(apt) > 20:
                lines.append(f"  ... and {len(apt) - 20} more")
            lines.append("")
        python = data.get("python", [])
        if python:
            lines.append(f"[b]Python Packages[/b] ({len(python)} installed)")
            for pkg in python[:20]:
                lines.append(f"  {pkg.get('name', '?')} {pkg.get('version', '?')} ({pkg.get('source', '?')})")
            if len(python) > 20:
                lines.append(f"  ... and {len(python) - 20} more")
            lines.append("")
        node = data.get("node", [])
        if node:
            lines.append(f"[b]Node Packages[/b] ({len(node)} installed)")
            for pkg in node[:20]:
                lines.append(f"  {pkg.get('name', '?')} {pkg.get('version', '?')}")
            if len(node) > 20:
                lines.append(f"  ... and {len(node) - 20} more")
            lines.append("")
        docker = data.get("docker", {})
        if docker:
            images = docker.get("images", [])
            containers = docker.get("containers", [])
            lines.append("[b]Docker[/b]")
            lines.append(f"  Images: {len(images)}")
            for img in images[:10]:
                lines.append(f"    {img.get('repository', '?')}:{img.get('tag', '?')} ({img.get('size', '?')})")
            if len(images) > 10:
                lines.append(f"    ... and {len(images) - 10} more")
            lines.append(f"  Containers: {len(containers)}")
            for c in containers[:10]:
                lines.append(f"    {c.get('name', '?')} {c.get('status', '?')}")
            if len(containers) > 10:
                lines.append(f"    ... and {len(containers) - 10} more")
            lines.append("")
        podman = data.get("podman", {})
        if podman:
            images = podman.get("images", [])
            containers = podman.get("containers", [])
            lines.append("[b]Podman[/b]")
            lines.append(f"  Images: {len(images)}   Containers: {len(containers)}")
            lines.append("")
        snap = data.get("snap", [])
        if snap:
            lines.append(f"[b]Snap Packages[/b] ({len(snap)} installed)")
            for pkg in snap[:20]:
                lines.append(f"  {pkg.get('name', '?')} {pkg.get('version', '?')}")
            if len(snap) > 20:
                lines.append(f"  ... and {len(snap) - 20} more")
            lines.append("")
        flatpak = data.get("flatpak", [])
        if flatpak:
            lines.append(f"[b]Flatpak Apps[/b] ({len(flatpak)} installed)")
            for pkg in flatpak[:20]:
                lines.append(f"  {pkg.get('name', '?')} {pkg.get('version', '?')}")
            if len(flatpak) > 20:
                lines.append(f"  ... and {len(flatpak) - 20} more")
            lines.append("")
        services = data.get("services", [])
        if services:
            lines.append(f"[b]Running Systemd Services[/b] ({len(services)})")
            for svc in services[:20]:
                lines.append(f"  {svc.get('unit', '?')} ({svc.get('active', '?')})")
            if len(services) > 20:
                lines.append(f"  ... and {len(services) - 20} more")
            lines.append("")
        binaries = data.get("binaries", [])
        if binaries:
            lines.append(f"[b]Local Binaries[/b] ({len(binaries)} found)")
            for b in binaries[:30]:
                lines.append(f"  {b.get('name', '?')} -> {b.get('path', '?')}")
            if len(binaries) > 30:
                lines.append(f"  ... and {len(binaries) - 30} more")
            lines.append("")
        panel.update("\n".join(lines))

    def action_check_conflicts(self) -> None:
        selected_ids = [k for k, v in self.selected_map.items() if v]
        if not selected_ids:
            self.write_log("Nothing selected to check.")
            return
        selected = [p for p in self.packages if p.id in selected_ids]
        errors, warnings = self._preflight_check(selected)
        self.conflict_errors = errors
        self.dependency_warnings = warnings
        if errors:
            self.write_log("[WARN] Conflicts found:")
            for e in errors:
                self.write_log(f"  - {e}")
        else:
            self.write_log("[OK] No conflicts detected.")
        if warnings:
            self.write_log("[INFO] Dependency notes:")
            for w in warnings:
                self.write_log(f"  - {w}")
        else:
            self.write_log("[OK] All selected dependencies appear met or auto-resolvable.")

    def _preflight_check(self, selected: list[Package]) -> tuple[list[str], list[str]]:
        errors: list[str] = []
        warnings: list[str] = []
        selected_ids = {p.id for p in selected}
        for pkg in selected:
            for dep in pkg.dependencies:
                if dep not in selected_ids:
                    warnings.append(f"{pkg.id} depends on {dep} (not selected)")
            for conflict in pkg.conflicts:
                if conflict in selected_ids:
                    errors.append(f"{pkg.id} conflicts with {conflict}")
        return errors, warnings

    async def action_run_selected(self) -> None:
        self._run_selected()

    def _run_selected(self) -> None:
        selected_ids = [k for k, v in self.selected_map.items() if v]
        if not selected_ids:
            self.write_log("Nothing selected.")
            return
        selected = [p for p in self.packages if p.id in selected_ids]
        errors, warnings = self._preflight_check(selected)
        if errors:
            self.write_log("[ABORT] Resolve conflicts before running:")
            for e in errors:
                self.write_log(f"  - {e}")
            return
        if warnings:
            self.write_log("[WARN] Dependency notes:")
            for w in warnings:
                self.write_log(f"  - {w}")
            self.write_log("Continuing anyway. Use 'f' to review before proceeding.")
        self.is_running = True
        self.progress = 0.0
        self._receipt_logger = ReceiptLogger()
        self._rollback_manager = RollbackManager(self._receipt_logger)
        self._receipt_logger.record_snapshot()
        apt_tx = self._capture_apt_transaction()
        self._receipt_logger.set_apt_transaction(apt_tx)
        total = len(selected)
        completed = 0
        for pkg in selected:
            self.write_log(f"Installing {pkg.name}...")
            provider = get_provider(pkg.provider)
            try:
                ok, out = provider.install(pkg, dry_run=self.dry_run)
                if ok:
                    self.write_log(f"[OK] {pkg.name}: {(out or 'done')[:300]}")
                    if pkg.post_install_msg:
                        self.write_log(f"  -> {pkg.post_install_msg}")
                else:
                    self.write_log(f"[FAIL] {pkg.name}: {(out or 'unknown error')[:300]}")
                self._receipt_logger.record_item(pkg, ok, out or "", dry_run=self.dry_run)
                if not self.dry_run:
                    if pkg.provider.value == "apt":
                        self._rollback_manager.plan_apt_remove(pkg)
                    elif pkg.provider.value == "github_repo":
                        self._rollback_manager.plan_github_remove(pkg)
            except Exception as e:
                self.write_log(f"[ERROR] {pkg.name}: {e}")
                self._receipt_logger.record_item(pkg, False, str(e), dry_run=self.dry_run)
            completed += 1
            self.progress = (completed / total) * 100
            self.refresh_package_list()
        self._last_receipt_path = Path(self._receipt_logger.LOG_DIR) / f"{self._receipt_logger.run_id}.json"
        if self._rollback_manager:
            self._rollback_manager.save(self._last_receipt_path)
        receipt = self._receipt_logger.finalize()
        self.is_running = False
        self.write_log("Run complete. Receipt saved.")
        self.push_screen(SummaryScreen(receipt))

    def _capture_apt_transaction(self) -> str | None:
        try:
            result = subprocess.run(
                ["apt-get", "-s", "install", "-y", "dummy-package-not-exists"],
                capture_output=True,
                text=True,
                check=False,
            )
            for line in result.stderr.splitlines() + result.stdout.splitlines():
                if "E: " in line:
                    return line.strip()
        except Exception:
            pass
        return None

    def action_retry_failures(self) -> None:
        failed = []
        if self._receipt_logger:
            for item in self._receipt_logger._receipt.get("items", []):
                if not item.get("ok") and not item.get("dry_run"):
                    failed.append(item["id"])
        if not failed:
            self.write_log("No failures to retry.")
            return
        for pkg_id in failed:
            self.selected_map[pkg_id] = not self.selected_map.get(pkg_id, False)
        self.refresh_package_list()
        self.write_log(f"Retrying {len(failed)} failed package(s)...")
        self._run_selected()

    def action_undo_last(self) -> None:
        if self._rollback_manager is None:
            self.write_log("No rollback plan available. Run installs first.")
            return
        self.write_log("Rolling back last run...")
        ok, out = self._rollback_manager.execute_rollback(dry_run=self.dry_run)
        self.write_log(f"[{'OK' if ok else 'FAIL'}] Rollback: {out[:300]}")

    async def action_self_update(self) -> None:
        self.write_log("Self-updating pob-post-install...")
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "pob-post-install"]
        if self.dry_run:
            self.write_log(f"[dry-run] {' '.join(cmd)}")
            return
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await proc.communicate()
            out = stdout.decode("utf-8", errors="ignore").strip()
            self.write_log(out[:500])
        except Exception as e:
            self.write_log(f"Self-update failed: {e}")

    def action_scan_history(self) -> None:
        tabbed = self.query_one("#tabbed", TabbedContent)
        disc_tab = self.query_one("#tab-discovery", TabPane)
        tabbed.active = disc_tab
        self.write_log("Scanning terminal history for installs...")
        discovery = HistoryDiscovery()
        items = discovery.discover()
        self._discovery_items = items
        self._render_discovery_table()
        self.write_log(f"Discovery complete: {len(items)} unique installs found from history.")

    def action_scan_ansible(self) -> None:
        tabbed = self.query_one("#tabbed", TabbedContent)
        disc_tab = self.query_one("#tab-discovery", TabPane)
        tabbed.active = disc_tab
        roots = [Path.home() / "ansible", Path.home() / "projects", Path.cwd()]
        self.write_log("Scanning Ansible playbooks...")
        try:
            from pob_post_install.history_discovery import AnsibleDiscovery
            finder = AnsibleDiscovery()
            items = finder.discover(roots)
            self._discovery_items.extend(items)
            self._render_discovery_table()
            self.write_log(f"Ansible discovery complete: {len(items)} items found.")
        except Exception as e:
            self.write_log(f"Ansible discovery failed: {e}")
        tabbed = self.query_one("#tabbed", TabbedContent)
        disc_tab = self.query_one("#tab-discovery", TabPane)
        tabbed.active = disc_tab
        self.write_log("Scanning terminal history for installs...")
        discovery = HistoryDiscovery()
        items = discovery.discover()
        self._discovery_items = items
        self._render_discovery_table()
        self.write_log(f"Discovery complete: {len(items)} unique installs found from history.")

    def _render_discovery_table(self) -> None:
        table = self.query_one("#discovery-table", PackageTable)
        table.clear(columns=False)
        table.add_column("Selected", key="selected", width=8)
        table.add_column("Name", key="name")
        table.add_column("Provider", key="provider")
        table.add_column("Source", key="source")
        table.add_column("Evidence", key="evidence")
        table.zebra_stripes = True
        table.cursor_type = "row"
        for item in self._discovery_items:
            selected = "[ ]"
            table.add_row(
                selected,
                item["id"],
                item["provider"],
                item["source"],
                item["evidence"][:100],
                key=f"disc-{item['id']}",
            )
        if not self._discovery_items:
            table.add_row("", "No installs discovered", "", "", "", key="disc-empty")

    def action_import_discovery(self) -> None:
        if not self._discovery_items:
            self.write_log("Nothing discovered to import. Run Scan History first.")
            return
        added = 0
        for item in self._discovery_items:
            if item["id"] in {p.id for p in self.packages}:
                continue
            from pob_post_install.models.package import ProviderType
            provider_map = {
                "apt": ProviderType.APT,
                "npm": ProviderType.NPM,
                "pip": ProviderType.APT,
                "uv": ProviderType.UV,
                "github": ProviderType.GITHUB_REPO,
                "git": ProviderType.GITHUB_REPO,
                "script": ProviderType.SCRIPT,
                "docker": ProviderType.SCRIPT,
                "snap": ProviderType.APT,
            }
            provider = provider_map.get(item["provider"], ProviderType.SCRIPT)
            pkg = Package(
                id=item["id"],
                name=item["name"],
                description=item["description"],
                category=Category.DISCOVERED if hasattr(Category, 'DISCOVERED') else Category.CUSTOM,
                provider=provider,
                install_args=[item["id"]] if provider in {ProviderType.APT, ProviderType.NPM, ProviderType.SCRIPT} else [],
                verify_cmd=None,
            )
            self.packages.append(pkg)
            added += 1
        self.refresh_package_list()
        self.write_log(f"Imported {added} discovered packages into Packages tab.")

    def action_cycle_theme(self) -> None:
        themes = ThemeManager.available_themes()
        idx = themes.index(self._theme) + 1
        idx %= len(themes)
        self._theme = themes[idx]
        self.css = ThemeManager.get_theme(self._theme)
        self.write_log(f"Theme switched to: {self._theme}")

    def action_run_diff(self) -> None:
        tabbed = self.query_one("#tabbed", TabbedContent)
        diff_tab = self.query_one("#tab-diff", TabPane)
        tabbed.active = diff_tab
        desired_ids = {p.id for p in self.packages}
        installed = {}
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            collector = InventoryCollector()
            installed = loop.run_until_complete(collector.collect())
        except Exception as e:
            self.write_log(f"Diff failed: {e}")
            return
        result = DiffEngine.compare(desired_ids, installed)
        self._diff_result = result
        panel = self.query_one("#diff-result", Static)
        lines = [
            f"Desired: {result['summary']['desired_count']} packages",
            f"Installed: {result['summary']['installed_count']} packages",
            f"Missing: {result['summary']['missing_count']}",
            f"Extra: {result['summary']['extra_count']}",
            "",
        ]
        if result["missing"]:
            lines.append("[red]Missing packages:[/red]")
            for pkg in result["missing"][:50]:
                lines.append(f"  - {pkg}")
        if result["extra"]:
            lines.append("[yellow]Extra packages:[/yellow]")
            for pkg in result["extra"][:50]:
                lines.append(f"  - {pkg}")
        panel.update(chr(10).join(lines))
        self.write_log(f"Diff complete: {result['summary']['missing_count']} missing, {result['summary']['extra_count']} extra")

    def action_load_timetravel(self) -> None:
        tabbed = self.query_one("#tabbed", TabbedContent)
        tt_tab = self.query_one("#tab-timetravel", TabPane)
        tabbed.active = tt_tab
        self._timetravel_receipts = TimeTravel.list_receipts()
        table = self.query_one("#timetravel-table", PackageTable)
        table.clear(columns=False)
        table.add_column("Selected", key="selected", width=8)
        table.add_column("Run ID", key="run_id")
        table.add_column("Started", key="started")
        table.add_column("Total", key="total")
        table.add_column("OK", key="ok")
        table.add_column("Fail", key="fail")
        table.zebra_stripes = True
        table.cursor_type = "row"
        for path in self._timetravel_receipts:
            data = TimeTravel.load(path)
            run_id = data.get("run_id", path.stem)
            started = data.get("started_at", "")
            summary = data.get("summary", {})
            table.add_row(
                "[ ]",
                run_id,
                started,
                str(summary.get("total", 0)),
                str(summary.get("ok", 0)),
                str(summary.get("fail", 0)),
                key=path.name,
            )
        if not self._timetravel_receipts:
            table.add_row("", "No receipts found", "", "", "", "", key="tt-empty")

    def action_export_recipe(self) -> None:
        selected_ids = [k for k, v in self.selected_map.items() if v]
        if not selected_ids:
            self.write_log("Select packages to export first.")
            return
        selected = [p for p in self.packages if p.id in selected_ids]
        recipe = Recipe(
            name="exported-recipe",
            description="Exported from TUI",
            packages=[
                {
                    "id": p.id,
                    "name": p.name,
                    "provider": p.provider.value,
                    "install_args": p.install_args,
                }
                for p in selected
            ],
        )
        out = Path("recipes") / f"{recipe.name}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(recipe.to_dict(), indent=2))
        self.write_log(f"Recipe exported to {out}")

    def action_import_recipe(self) -> None:
        self.write_log("Recipe import not yet implemented. Use JSON recipe files under recipes/.")

    def action_save_profile(self) -> None:
        from pathlib import Path
        import json
        profile_dir = Path("/home/cbwinslow/pob-post-install/profiles")
        profile_dir.mkdir(parents=True, exist_ok=True)
        name = f"profile-{time.strftime('%Y%m%d-%H%M%S')}.json"
        path = profile_dir / name
        payload = {
            "name": name,
            "selected": list(self.selected_map.items()),
            "dry_run": self.dry_run,
            "category": self.current_category.value if self.current_category else None,
            "search_query": self.search_query,
        }
        path.write_text(json.dumps(payload, indent=2))
        self.write_log(f"Profile saved: {path}")

    def action_load_profile(self) -> None:
        from pathlib import Path
        import json
        profile_dir = Path("/home/cbwinslow/pob-post-install/profiles")
        if not profile_dir.exists():
            self.write_log("No profiles directory.")
            return
        profiles = sorted(profile_dir.glob("*.json"))
        if not profiles:
            self.write_log("No profiles found.")
            return
        latest = profiles[-1]
        payload = json.loads(latest.read_text())
        self.dry_run = payload.get("dry_run", False)
        self.search_query = payload.get("search_query", "")
        cat = payload.get("category")
        if cat:
            self.current_category = next((c for c in {p.category for p in self.packages} if c.value == cat), None)
        selected = payload.get("selected", [])
        self.selected_map = {k: v for k, v in selected}
        self.refresh_package_list()
        self.write_log(f"Loaded profile: {latest.name}")

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        value = event.pressed.label.plain
        cat = next((c for c in {p.category for p in self.packages} if c.value == value), None)
        self.current_category = cat

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-input":
            self.search_query = event.value

    def on_switch_changed(self, event: Switch.Changed) -> None:
        if event.switch.id == "dry-run-switch":
            self.dry_run = event.value

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        key = event.row_key.value
        self.selected_map[key] = not self.selected_map.get(key, False)
        self.refresh_package_list()
        self._render_config()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn-scan-history":
            self.action_scan_history()
            return
        if btn_id == "btn-scan-ansible":
            self.action_scan_ansible()
            return
        if btn_id == "btn-import-discovery":
            self.action_import_discovery()
            return
        if btn_id == "btn-export-recipe":
            self.action_export_recipe()
            return
        if btn_id == "btn-import-recipe":
            self.action_import_recipe()
            return
        if btn_id == "btn-run-diff":
            self.action_run_diff()
            return
        if btn_id == "btn-load-receipts":
            self.action_load_timetravel()
            return
        if btn_id == "btn-diff-receipts":
            self.write_log("Select two receipts in the table first.")
            return
        if btn_id in ("btn-search-apt", "btn-search-pypi"):
            query = self.query_one("#search-query", Input).value.strip()
            if not query:
                self.write_log("Enter a search query first.")
                return
            table = self.query_one("#search-results", PackageTable)
            table.clear(columns=False)
            if btn_id == "btn-search-apt":
                self.write_log(f"Searching APT for: {query}")
                ok, out = await self._run_async(["apt-cache", "search", query])
                if ok:
                    for line in out.splitlines()[:20]:
                        parts = line.split(" - ", 1)
                        if len(parts) == 2:
                            pkg_name, desc = parts
                            table.add_row(pkg_name.strip(), desc.strip(), "apt", key=pkg_name.strip())
                else:
                    self.write_log(f"APT search failed: {out}")
            elif btn_id == "btn-search-pypi":
                self.write_log(f"Searching PyPI for: {query}")
                ok, out = await self._run_async([
                    "python3", "-m", "pip", "index", "versions", query
                ])
                if ok:
                    lines = out.splitlines()
                    for line in lines[:20]:
                        table.add_row(line, "PyPI package", "uv/pip", key=line)
                else:
                    self.write_log(f"PyPI search failed: {out}")

    async def _run_async(self, cmd: list[str]) -> tuple[bool, str]:
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            out = (stdout or b"").decode("utf-8", errors="ignore").strip()
            err = (stderr or b"").decode("utf-8", errors="ignore").strip()
            return proc.returncode == 0, out or err
        except Exception as e:
            return False, str(e)


def build_app(packages: list[Package]) -> App:
    return InstallerApp(packages=packages)


if __name__ == "__main__":
    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.resolve()))
    from run_pob_post_install import main as _main
    _main()
