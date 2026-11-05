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


def discover(kind: str, configured: str | None = None) -> Runner | None:
    if kind == "wine":
        executable = _resolve_candidate(configured or os.environ.get("WINE") or "wine")
    else:
        # Standalone Proton needs the Steam Linux Runtime setup supplied by umu-run.
        executable = _resolve_candidate(configured or os.environ.get("UMU_RUN") or "umu-run")
    return Runner(kind, executable) if executable else None


def runner_environment(data: dict, runner: Runner) -> dict[str, str]:
    env = os.environ.copy()
    env.update(data.get("environment", {}))
    prefix = get_prefix_path(data)
    if runner.kind == "wine":
        env["WINEPREFIX"] = str(prefix)
        env.setdefault("WINEARCH", "win64")
    else:
        env["WINEPREFIX"] = str(prefix)
        env.setdefault("GAMEID", "umu-default")
        proton_path = data["runner"].get("proton_path")
        if proton_path:
            env["PROTONPATH"] = str(Path(proton_path).expanduser())
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
    # umu-run initializes a prefix when passed an empty executable.
    return [str(runner.executable), ""]


def launch_command(
    runner: Runner, data: dict, executable: Path, arguments: list[str]
) -> list[str]:
    if runner.kind == "wine":
        return [str(runner.executable), str(executable), *arguments]
    return [str(runner.executable), str(executable), *arguments]


def runner_version(runner: Runner) -> str:
    if runner.kind == "proton":
        return "umu-managed Proton/runtime"
    args = [str(runner.executable), "--version"]
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"unavailable ({exc})"
    output = (result.stdout or result.stderr).strip().splitlines()
    return output[0] if output else f"exit {result.returncode}"
