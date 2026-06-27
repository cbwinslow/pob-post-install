from __future__ import annotations

import subprocess
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from pob_post_install.models.package import Package, ProviderType


class Provider(ABC):
    @abstractmethod
    def check(self, pkg: Package) -> str:
        raise NotImplementedError

    @abstractmethod
    def install(self, pkg: Package, dry_run: bool = False) -> tuple[bool, str]:
        raise NotImplementedError

    @abstractmethod
    def verify(self, pkg: Package) -> bool:
        raise NotImplementedError

    def run(self, cmd: list[str], dry_run: bool = False) -> tuple[bool, str]:
        if dry_run:
            return True, f"[dry-run] {' '.join(cmd)}"
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )
            ok = result.returncode == 0
            out = result.stdout.strip() or result.stderr.strip()
            return ok, out
        except Exception as e:
            return False, str(e)


class AptProvider(Provider):
    def check(self, pkg: Package) -> str:
        if shutil.which(pkg.id):
            return "installed"
        res = subprocess.run(
            ["dpkg-query", "-W", "-f", "${Status}", pkg.id],
            capture_output=True,
            text=True,
        )
        if res.returncode == 0 and "install ok installed" in res.stdout:
            return "installed"
        return "missing"

    def install(self, pkg: Package, dry_run: bool = False) -> tuple[bool, str]:
        if dry_run:
            return True, f"[dry-run] apt-get install -y {' '.join(pkg.install_args)}"
        ok, out = self.run(["apt-get", "install", "-y", *pkg.install_args], dry_run=False)
        return ok, out

    def verify(self, pkg: Package) -> bool:
        if pkg.verify_cmd:
            ok, _ = self.run(["bash", "-lc", pkg.verify_cmd])
            return ok
        return shutil.which(pkg.id) is not None


class UvProvider(Provider):
    def _tool_name(self) -> str:
        return "uv"

    def check(self, pkg: Package) -> str:
        if shutil.which(self._tool_name()):
            return "installed"
        return "missing"

    def install(self, pkg: Package, dry_run: bool = False) -> tuple[bool, str]:
        args = [self._tool_name(), "tool", "install", *pkg.install_args]
        if dry_run:
            return True, f"[dry-run] {' '.join(args)}"
        ok, out = self.run(args)
        return ok, out

    def verify(self, pkg: Package) -> bool:
        if pkg.verify_cmd:
            ok, _ = self.run(["bash", "-lc", pkg.verify_cmd])
            return ok
        return shutil.which(pkg.id) is not None


class NpmProvider(Provider):
    def check(self, pkg: Package) -> str:
        if shutil.which("npm"):
            return "installed"
        return "missing"

    def install(self, pkg: Package, dry_run: bool = False) -> tuple[bool, str]:
        args = ["npm", "install", "-g", *pkg.install_args]
        if dry_run:
            return True, f"[dry-run] {' '.join(args)}"
        ok, out = self.run(args)
        return ok, out

    def verify(self, pkg: Package) -> bool:
        if pkg.verify_cmd:
            ok, _ = self.run(["bash", "-lc", pkg.verify_cmd])
            return ok
        return shutil.which(pkg.id) is not None


class AnsibleProvider(Provider):
    def check(self, pkg: Package) -> str:
        if shutil.which("ansible-playbook"):
            return "installed"
        return "missing"

    def install(self, pkg: Package, dry_run: bool = False) -> tuple[bool, str]:
        args = [
            "ansible-playbook",
            *pkg.install_args,
        ]
        if dry_run:
            return True, f"[dry-run] {' '.join(args)}"
        ok, out = self.run(args)
        return ok, out

    def verify(self, pkg: Package) -> bool:
        return self.check(pkg) == "installed"


class PulumiProvider(Provider):
    def check(self, pkg: Package) -> str:
        if shutil.which("pulumi"):
            return "installed"
        return "missing"

    def install(self, pkg: Package, dry_run: bool = False) -> tuple[bool, str]:
        args = ["pulumi", *pkg.install_args]
        if dry_run:
            return True, f"[dry-run] {' '.join(args)}"
        ok, out = self.run(args)
        return ok, out

    def verify(self, pkg: Package) -> bool:
        return self.check(pkg) == "installed"


class OpentofuProvider(Provider):
    def check(self, pkg: Package) -> str:
        if shutil.which("tofu"):
            return "installed"
        return "missing"

    def install(self, pkg: Package, dry_run: bool = False) -> tuple[bool, str]:
        args = ["tofu", *pkg.install_args]
        if dry_run:
            return True, f"[dry-run] {' '.join(args)}"
        ok, out = self.run(args)
        return ok, out

    def verify(self, pkg: Package) -> bool:
        return self.check(pkg) == "installed"


class ScriptProvider(Provider):
    def check(self, pkg: Package) -> str:
        script = pkg.verify_cmd or pkg.id
        if shutil.which(script):
            return "installed"
        return "missing"

    def install(self, pkg: Package, dry_run: bool = False) -> tuple[bool, str]:
        if not pkg.install_args:
            return False, "No install command specified for script provider"
        cmd = list(pkg.install_args)
        if self._is_docker_pull(cmd) and not self._docker_available():
            return False, "Docker socket not available. Skipping docker pull. If using Podman, alias it to docker."
        if dry_run:
            return True, f"[dry-run] {' '.join(cmd)}"
        ok, out = self.run(cmd)
        return ok, out

    def verify(self, pkg: Package) -> bool:
        return self.check(pkg) == "installed"

    @staticmethod
    def _is_docker_pull(cmd: list[str]) -> bool:
        return any("docker pull" in str(c) for c in cmd)

    @staticmethod
    def _docker_available() -> bool:
        return shutil.which("docker") is not None and Path("/var/run/docker.sock").exists()


class GithubRepoProvider(Provider):
    INSTALLER_FILES = [
        "install.sh",
        "setup.sh",
        "install",
        "setup",
        "Makefile",
        "makefile",
        "setup.py",
        "requirements.txt",
        "package.json",
        "pyproject.toml",
        "install.py",
    ]

    def check(self, pkg: Package) -> str:
        dest = Path(pkg.config.get("clone_dest", f"/opt/{pkg.id}"))
        if dest.exists() and any(dest.iterdir()):
            return "installed"
        return "missing"

    def install(self, pkg: Package, dry_run: bool = False) -> tuple[bool, str]:
        repo_url = pkg.config.get("repo_url") or (pkg.install_args[0] if pkg.install_args else None)
        if not repo_url:
            return False, "No repo_url specified for github_repo provider"
        dest = Path(pkg.config.get("clone_dest", f"/opt/{pkg.id}"))
        if not self._in_container():
            dest = dest
        else:
            fallback = Path.home() / ".local" / "share" / "pob-post-install" / "repos" / pkg.id
            dest = fallback
        installer = pkg.config.get("installer")
        extra_args = pkg.config.get("install_args", [])
        skip_installer = pkg.config.get("skip_installer", False)

        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            cmd = ["git", "clone", repo_url, str(dest)]
            ok, out = self.run(cmd, dry_run=dry_run)
            if not ok:
                return False, f"Clone failed: {out}"
        else:
            out = f"Repo already exists at {dest}"

        if skip_installer:
            return True, f"Cloned to {dest}. Installer skipped per config."

        if installer:
            installer_path = dest / installer
            if not installer_path.exists():
                return False, f"Configured installer not found: {installer_path}"
            return self._run_installer(dest, installer_path, extra_args, dry_run)

        found = self._find_installer(dest)
        if not found:
            return True, f"Cloned to {dest}. No installer file found."

        return self._run_installer(dest, found, extra_args, dry_run)

    def _find_installer(self, dest: Path) -> Optional[Path]:
        for name in self.INSTALLER_FILES:
            candidate = dest / name
            if candidate.exists():
                return candidate
        return None

    def _run_installer(self, repo_path: Path, installer: Path, extra_args: list[str], dry_run: bool) -> tuple[bool, str]:
        suffix = installer.suffix.lower()
        name = installer.name.lower()
        if name == "makefile" or suffix == ".sh":
            cmd = ["bash", str(installer), *extra_args]
        elif name == "setup.py":
            cmd = ["python3", str(installer), "install", *extra_args]
        elif name == "requirements.txt":
            cmd = ["pip", "install", "-r", str(installer), *extra_args]
        elif name == "package.json":
            cmd = ["npm", "install", "--prefix", str(repo_path)]
        elif name == "pyproject.toml":
            cmd = ["pip", "install", str(repo_path)]
        elif name in ("install", "setup"):
            cmd = ["bash", str(installer), *extra_args]
        else:
            cmd = ["bash", str(installer), *extra_args]
        if dry_run:
            return True, f"[dry-run] {' '.join(cmd)}"
        return self.run(cmd)

    def verify(self, pkg: Package) -> bool:
        return self.check(pkg) == "installed"

    @staticmethod
    def _in_container() -> bool:
        return Path("/.dockerenv").exists() or Path("/run/.containerenv").exists()


def get_provider(provider: ProviderType) -> Provider:
    mapping = {
        ProviderType.APT: AptProvider(),
        ProviderType.UV: UvProvider(),
        ProviderType.NPM: NpmProvider(),
        ProviderType.ANSIBLE: AnsibleProvider(),
        ProviderType.PULUMI: PulumiProvider(),
        ProviderType.OPENTOFU: OpentofuProvider(),
        ProviderType.SCRIPT: ScriptProvider(),
        ProviderType.GITHUB_REPO: GithubRepoProvider(),
    }
    return mapping[provider]
