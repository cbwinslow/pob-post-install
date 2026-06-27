from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional, List, Tuple


class HistoryDiscovery:
    """Scans shell and tool history to discover installed packages."""

    PATTERNS = [
        (re.compile(r"\bapt-get\s+install\s+(?:-[^ ]+\s+)*([^\s-]+)"), "apt"),
        (re.compile(r"\bapt\s+install\s+(?:-[^ ]+\s+)*([^\s-]+)"), "apt"),
        (re.compile(r"\bnpm\s+install\s+-g\s+([^\s]+)"), "npm"),
        (re.compile(r"\byarn\s+global\s+add\s+([^\s]+)"), "npm"),
        (re.compile(r"\bpip(?:\d)?\s+install\s+([^\s]+)"), "pip"),
        (re.compile(r"\buv\s+tool\s+install\s+([^\s]+)"), "uv"),
        (re.compile(r"\bgh\s+extension\s+install\s+([^\s]+)"), "github"),
        (re.compile(r"\bgit\s+clone\s+.*\/([^\/]+?)(?:\.git)?\s"), "git"),
        (re.compile(r"\bcurl\s+.*\|\s*(?:bash|sh)\b"), "script"),
        (re.compile(r"\bdocker\s+pull\s+([^\s]+)"), "docker"),
        (re.compile(r"\bdocker\s+run\s+.*\s+([a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+)"), "docker"),
        (re.compile(r"\bsnap\s+install\s+([^\s]+)"), "snap"),
    ]

    def discover(self) -> List[dict]:
        findings: List[dict] = []
        seen: set = set()
        sources = self._collect_history_sources()
        for source, line in sources:
            matched = self._match_line(line)
            if not matched:
                continue
            pkg_id, provider, evidence = matched
            key = f"{provider}:{pkg_id.lower()}"
            if key in seen:
                continue
            seen.add(key)
            findings.append(
                {
                    "id": pkg_id,
                    "provider": provider,
                    "source": source,
                    "evidence": evidence,
                    "name": pkg_id,
                    "description": f"Discovered from {source}",
                    "category": "Discovered",
                }
            )
        return findings

    def _collect_history_sources(self) -> List[Tuple[str, str]]:
        sources: List[Tuple[str, str]] = []
        sources.extend(self._read_bash_history())
        sources.extend(self._read_zsh_history())
        sources.extend(self._read_fish_history())
        sources.extend(self._read_atuin_db())
        return sources

    def _read_bash_history(self) -> List[Tuple[str, str]]:
        paths = [
            Path.home() / ".bash_history",
            Path.home() / ".histfile",
        ]
        return self._read_text_files(paths, "bash_history")

    def _read_zsh_history(self) -> List[Tuple[str, str]]:
        path = Path.home() / ".zsh_history"
        out: List[Tuple[str, str]] = []
        if not path.exists():
            return out
        try:
            for line in path.read_text(errors="ignore").splitlines():
                line = line.strip()
                if not line:
                    continue
                if line.startswith(":"):
                    try:
                        _ts, cmd = line.split(";", 1)
                        out.append(("zsh_history", cmd.strip()))
                    except ValueError:
                        continue
                else:
                    out.append(("zsh_history", line))
        except OSError:
            pass
        return out

    def _read_fish_history(self) -> List[Tuple[str, str]]:
        path = Path.home() / ".local" / "share" / "fish" / "fish_history"
        out: List[Tuple[str, str]] = []
        if not path.exists():
            return out
        try:
            for line in path.read_text(errors="ignore").splitlines():
                line = line.strip()
                if line.startswith("- cmd: "):
                    out.append(("fish_history", line[len("- cmd: "):]))
        except OSError:
            pass
        return out

    def _read_atuin_db(self) -> List[Tuple[str, str]]:
        db_path = Path.home() / ".local" / "share" / "atuin" / "history.db"
        if not db_path.exists():
            return []
        try:
            import sqlite3

            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()
            cur.execute("SELECT command FROM history ORDER BY timestamp DESC LIMIT 20000")
            rows = cur.fetchall()
            conn.close()
            return [("atuin", row[0]) for row in rows if row[0]]
        except Exception:
            return []

    def _read_text_files(self, paths: List[Path], source: str) -> List[Tuple[str, str]]:
        out: List[Tuple[str, str]] = []
        for path in paths:
            if not path.exists():
                continue
            try:
                for line in path.read_text(errors="ignore").splitlines():
                    line = line.strip()
                    if line:
                        out.append((source, line))
            except OSError:
                continue
        return out

    def _match_line(self, line: str) -> Optional[Tuple[str, str, str]]:
        if "#" in line:
            line = line.split("#", 1)[0]
        for pattern, provider in HistoryDiscovery.PATTERNS:
            m = pattern.search(line)
            if not m:
                continue
            raw = m.group(1).strip()
            pkg_id = self._normalize_pkg_id(raw, provider)
            if not pkg_id:
                continue
            if provider in ("npm", "pip", "uv"):
                pkg_id = re.split(r"[>=<@]", pkg_id, 1)[0]
            evidence = line.strip()[:240]
            return pkg_id, provider, evidence
        return None

    def _normalize_pkg_id(self, raw: str, provider: str) -> str:
        if provider == "apt":
            parts = raw.split()
            return parts[0] if parts else ""
        if provider == "git":
            return raw.strip().strip("/")
        return raw.strip()

    def to_json(self, items: List[dict]) -> str:
        return json.dumps(items, indent=2)

    def save(self, path: Path, items: List[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(items))


class AnsibleDiscovery:
    """Parse Ansible playbooks/roles for package/install references."""

    MODULE_KEYWORDS = {"apt", "npm", "pip", "yarn", "gem", "package", "command", "shell", "git", "uri", "unarchive"}

    def discover(self, roots: list[Path]) -> list[dict]:
        findings: list[dict] = []
        seen: set = set()
        playbooks = []
        for root in roots:
            if not root.exists():
                continue
            playbooks.extend(root.rglob("*.yml"))
            playbooks.extend(root.rglob("*.yaml"))
        for path in playbooks:
            try:
                text = path.read_text(errors="ignore")
            except OSError:
                continue
            for item in self._extract_from_text(text):
                key = f"ansible:{item['id'].lower()}"
                if key in seen:
                    continue
                seen.add(key)
                findings.append(
                    {
                        "id": item["id"],
                        "provider": item["provider"],
                        "source": f"ansible:{path}",
                        "evidence": item["evidence"],
                        "name": item["id"],
                        "description": f"Discovered from Ansible playbook {path.name}",
                        "category": "Discovered",
                    }
                )
        return findings

    def _extract_from_text(self, text: str) -> list[dict]:
        import yaml

        out: list[dict] = []
        try:
            docs = list(yaml.safe_load_all(text))
        except Exception:
            return out
        for doc in docs or []:
            if not isinstance(doc, dict):
                continue
            tasks = doc.get("tasks", doc.get("pre_tasks", []))
            if not isinstance(tasks, list):
                continue
            for task in tasks:
                if not isinstance(task, dict):
                    continue
                name = list(task.keys())[0] if task else None
                if not name:
                    continue
                module = str(name).split(".")[-1]
                if module not in self.MODULE_KEYWORDS:
                    continue
                cfg = task.get(name, {}) if isinstance(task.get(name), dict) else {}
                evidence = yaml.dump({name: cfg}, default_flow_style=False)[:240]
                name_val = cfg.get("name", cfg.get("pkg", cfg.get("package", "")))
                if not name_val:
                    continue
                name_val = str(name_val).strip()
                if not name_val:
                    continue
                if module == "apt":
                    out.append({"id": name_val.split()[0], "provider": "apt", "evidence": evidence})
                elif module in {"npm", "yarn"}:
                    out.append({"id": name_val, "provider": "npm", "evidence": evidence})
                elif module == "pip":
                    out.append({"id": name_val, "provider": "pip", "evidence": evidence})
                elif module == "git":
                    out.append(
                        {
                            "id": Path(str(name_val)).name.replace(".git", ""),
                            "provider": "git",
                            "evidence": evidence,
                        }
                    )
                elif module in {"command", "shell"}:
                    cmd = cfg.get("cmd", cfg.get("cmd", cfg.get("free_form", ""))) or ""
                    cmd = str(cmd)
                    matched = False
                    for pat, prov in [
                        (r"apt-get install\\s+(\\S+)", "apt"),
                        (r"npm install -g\\s+(\\S+)", "npm"),
                        (r"pip install\\s+(\\S+)", "pip"),
                    ]:
                        import re

                        m2 = re.search(pat, cmd)
                        if m2:
                            out.append({"id": m2.group(1), "provider": prov, "evidence": evidence})
                            matched = True
                            break
                    if not matched:
                        out.append({"id": name_val or cmd.split()[0], "provider": "script", "evidence": evidence})
        return out
