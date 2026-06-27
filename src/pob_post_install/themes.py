from __future__ import annotations

THEMES = {
    "dark": """
    Screen { background: $background; }
    Horizontal { height: 1fr; }
    #sidebar { width: 30; dock: left; padding: 1; background: $panel; border: thick $primary; }
    #main { height: 1fr; padding: 1; }
    #packages { height: 1fr; border: thick $primary; background: $boost; }
    #packages PackageTable { background: $boost; }
    #packages PackageTable > .datatable--cursor { background: $primary; color: $text; }
    #packages PackageTable > .datatable--hover { background: $primary 15%; }
    #log { height: 15; border: thick $primary; background: $boost; padding: 1; }
    #progress-container { height: 5; padding: 0 1; }
    .sidebar-title { text-style: bold; background: $primary; color: $text; padding: 0 1; margin-top: 1; }
    #status-bar { height: 1; background: $panel; color: $text; padding: 0 1; text-style: bold; }
    .section-title { text-style: bold; background: $primary; color: $text; padding: 0 1; margin-top: 1; }
    .config-path { color: $accent; text-style: bold; }
    .config-file { color: $text; padding-left: 2; }
    #search-results { height: 1fr; border: thick $primary; background: $boost; }
    #container-status { color: $accent; text-style: bold; }
    #spinner-indicator { width: 3; content-align: center middle; text-style: bold; color: $accent; }
    """,
    "light": """
    Screen { background: $background; }
    Horizontal { height: 1fr; }
    #sidebar { width: 30; dock: left; padding: 1; background: $panel; border: thick $primary; }
    #main { height: 1fr; padding: 1; }
    #packages { height: 1fr; border: thick $primary; background: $boost; }
    #packages PackageTable { background: $boost; }
    #packages PackageTable > .datatable--cursor { background: $primary; color: $text; }
    #packages PackageTable > .datatable--hover { background: $primary 15%; }
    #log { height: 15; border: thick $primary; background: $boost; padding: 1; }
    #progress-container { height: 5; padding: 0 1; }
    .sidebar-title { text-style: bold; background: $primary; color: $text; padding: 0 1; margin-top: 1; }
    #status-bar { height: 1; background: $panel; color: $text; padding: 0 1; text-style: bold; }
    .section-title { text-style: bold; background: $primary; color: $text; padding: 0 1; margin-top: 1; }
    .config-path { color: $accent; text-style: bold; }
    .config-file { color: $text; padding-left: 2; }
    #search-results { height: 1fr; border: thick $primary; background: $boost; }
    #container-status { color: $accent; text-style: bold; }
    #spinner-indicator { width: 3; content-align: center middle; text-style: bold; color: $accent; }
    """,
    "high_contrast": """
    Screen { background: black; color: white; }
    Horizontal { height: 1fr; }
    #sidebar { width: 30; dock: left; padding: 1; background: white; color: black; border: thick black; }
    #main { height: 1fr; padding: 1; }
    #packages { height: 1fr; border: thick black; background: white; color: black; }
    #packages PackageTable { background: white; color: black; }
    #packages PackageTable > .datatable--cursor { background: black; color: white; }
    #packages PackageTable > .datatable--hover { background: black; color: white; }
    #log { height: 15; border: thick black; background: white; color: black; padding: 1; }
    #progress-container { height: 5; padding: 0 1; }
    .sidebar-title { text-style: bold; background: black; color: white; padding: 0 1; margin-top: 1; }
    #status-bar { height: 1; background: white; color: black; padding: 0 1; text-style: bold; }
    .section-title { text-style: bold; background: black; color: white; padding: 0 1; margin-top: 1; }
    .config-path { color: blue; text-style: bold; }
    .config-file { color: black; padding-left: 2; }
    #search-results { height: 1fr; border: thick black; background: white; color: black; }
    #container-status { color: blue; text-style: bold; }
    #spinner-indicator { width: 3; content-align: center middle; text-style: bold; color: blue; }
    """,
}


class ThemeManager:
    @staticmethod
    def get_theme(name: str) -> str:
        return THEMES.get(name, THEMES["dark"])

    @staticmethod
    def available_themes() -> list[str]:
        return list(THEMES.keys())
