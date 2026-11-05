from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .manifest import get_prefix_path


@dataclass(frozen=True)
class Runner:
    kind: str
    executable: Path


def _resolve_candidate(candidate: str | None) -> Path | None:
    if not candidate:
        return None
    expanded = Path(candidate).expanduser()
    if expanded.is_file() and os.access(expanded, os.X_OK):
        return expanded.resolve()
    located = shutil.which(candidate)
    return Path(located).resolve() if located else None


def proton_candidates() -> list[Path]:
    home = Path.home()
    roots = [
        home / ".steam/steam/steamapps/common",
        home / ".local/share/Steam/steamapps/common",
        home / ".var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/common",
    ]
    found: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        try:
            found.extend(path / "proton" for path in root.glob("Proton*") if (path / "proton").is_file())
        except OSError:
            continue
    return sorted(set(path.resolve() for path in found))


def discover(kind: str, configured: str | None = None) -> Runner | None:
    if kind == "wine":
        executable = _resolve_candidate(configured or os.environ.get("WINE") or "wine")
    else:
        executable = _resolve_candidate(configured or os.environ.get("PROTON"))
        if executable is None:
            for candidate in proton_candidates():
                if os.access(candidate, os.X_OK):
                    executable = candidate
                    break
    return Runner(kind, executable) if executable else None


def runner_environment(data: dict, runner: Runner) -> dict[str, str]:
    env = os.environ.copy()
    env.update(data.get("environment", {}))
    prefix = get_prefix_path(data)
    if runner.kind == "wine":
        env["WINEPREFIX"] = str(prefix)
        env.setdefault("WINEARCH", "win64")
    else:
        env["STEAM_COMPAT_DATA_PATH"] = str(prefix)
        steam_root = next(
            (
                candidate
                for candidate in (
                    Path.home() / ".steam/steam",
                    Path.home() / ".local/share/Steam",
                    Path.home() / ".var/app/com.valvesoftware.Steam/.local/share/Steam",
                )
                if candidate.is_dir()
            ),
            None,
        )
        if steam_root:
            env.setdefault("STEAM_COMPAT_CLIENT_INSTALL_PATH", str(steam_root))
    return env


def prefix_ready(data: dict, runner: Runner) -> bool:
    prefix = get_prefix_path(data)
    if runner.kind == "wine":
        return (prefix / "system.reg").is_file()
    return (prefix / "pfx/system.reg").is_file()


def setup_command(runner: Runner, data: dict) -> list[str]:
    if runner.kind == "wine":
        wineboot = os.environ.get("WINEBOOT") or shutil.which("wineboot")
        if not wineboot:
            wineboot = str(runner.executable.with_name("wineboot"))
        return [wineboot, "-u"]
    # Proton initializes the compatibility prefix as part of its normal run path.
    return [str(runner.executable), "run", "cmd.exe", "/c", "exit", "0"]


def launch_command(
    runner: Runner, data: dict, executable: Path, arguments: list[str]
) -> list[str]:
    if runner.kind == "wine":
        return [str(runner.executable), str(executable), *arguments]
    return [str(runner.executable), "run", str(executable), *arguments]


def runner_version(runner: Runner) -> str:
    args = [str(runner.executable), "--version"]
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"unavailable ({exc})"
    output = (result.stdout or result.stderr).strip().splitlines()
    return output[0] if output else f"exit {result.returncode}"
