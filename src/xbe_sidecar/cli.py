from __future__ import annotations

import argparse
import platform
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .bundle import BundleError, create_bundle
from .manifest import (
    ManifestError,
    create_manifest,
    get_player_path,
    get_prefix_path,
    get_state_path,
    get_working_directory,
    load_manifest,
)
from .runners import (
    discover,
    launch_command,
    prefix_ready,
    runner_environment,
    runner_version,
    setup_command,
)
from .prefix_ops import (
    PrefixOperationError,
    create_prefix_backup,
    reset_prefix,
    safe_prefix_path,
)


class SidecarError(RuntimeError):
    pass


def _print_process(command: list[str], cwd: Path, env: dict[str, str], log_path: Path) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"$ {shlex.join(command)}")
    print(f"Log: {log_path}")
    try:
        with log_path.open("a", encoding="utf-8", errors="replace") as log:
            log.write(f"\n[{datetime.now(timezone.utc).isoformat()}] $ {shlex.join(command)}\n")
            process = subprocess.Popen(
                command,
                cwd=cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                errors="replace",
                bufsize=1,
            )
            assert process.stdout is not None
            try:
                for line in process.stdout:
                    print(line, end="")
                    log.write(line)
                    log.flush()
                return process.wait()
            except KeyboardInterrupt:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                return 130
    except OSError as exc:
        raise SidecarError(f"Could not start runner: {exc}") from exc


def _log_path(data: dict, operation: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return get_state_path(data) / "logs" / f"{operation}-{stamp}.log"


def _get_runner(data: dict):
    section = data["runner"]
    runner = discover(section["type"], section.get("executable"))
    if runner is None:
        variable = "WINE" if section["type"] == "wine" else "UMU_RUN"
        raise SidecarError(
            f"Could not find {section['type']} runner. Set [runner].executable in sidecar.toml "
            f"or the {variable} environment variable."
        )
    return runner


def _ensure_prefix(data: dict, runner) -> None:
    if prefix_ready(data, runner):
        return
    prefix = get_prefix_path(data)
    prefix.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        prefix.chmod(0o700)
    except OSError:
        pass
    command = setup_command(runner, data)
    env = runner_environment(data, runner)
    rc = _print_process(command, data["_workspace"], env, _log_path(data, "setup"))
    if rc:
        raise SidecarError(f"Runner prefix setup failed with exit status {rc}")
    if not prefix_ready(data, runner):
        raise SidecarError(
            f"Runner returned successfully but did not create its prefix at {prefix}. "
            "Check the runner log and runtime requirements."
        )


def command_init(args: argparse.Namespace) -> int:
    workspace = args.workspace.expanduser().resolve()
    if not workspace.is_dir():
        raise SidecarError(f"Workspace directory does not exist: {workspace}")
    try:
        manifest = create_manifest(
            workspace,
            name=args.name or workspace.name,
            executable=args.exe,
            runner=args.runner,
            runner_executable=args.runner_executable,
            proton_path=args.proton_path,
            umu_folders_path=args.umu_folders_path,
        )
    except ManifestError as exc:
        raise SidecarError(str(exc)) from exc
    data = load_manifest(manifest)
    (get_state_path(data) / "logs").mkdir(parents=True, exist_ok=True)
    print(f"Created {manifest}")
    print("Next: xbe-sidecar doctor " + str(workspace))
    print("Then: xbe-sidecar setup " + str(workspace))
    return 0


def command_runners(_: argparse.Namespace) -> int:
    wine = discover("wine")
    if wine:
        print(f"Wine:   {wine.executable} ({runner_version(wine)})")
    else:
        print("Wine:   not found")
    proton_env = discover("proton")
    if proton_env:
        print(f"Proton:  via {proton_env.executable} (umu-run)")
    else:
        print("Proton:  umu-run not found (install umu-launcher)")
    return 0


def command_doctor(args: argparse.Namespace) -> int:
    try:
        data = load_manifest(args.workspace.expanduser())
    except ManifestError as exc:
        raise SidecarError(str(exc)) from exc
    runner = discover(data["runner"]["type"], data["runner"].get("executable"))
    player = get_player_path(data)
    working = get_working_directory(data)
    prefix = get_prefix_path(data)
    state = get_state_path(data)
    print(f"Sidecar:     {__version__}")
    print(f"Title:       {data['title']['name']}")
    print(f"Workspace:   {data['_workspace']}")
    print(f"Host:        {platform.system()} {platform.release()} ({platform.machine()})")
    print(f"Runner:      {data['runner']['type']}")
    if runner:
        print(f"Runner path: {runner.executable}")
        print(f"Version:     {runner_version(runner)}")
    else:
        print("Runner path: MISSING")
    print(f"Prefix:      {prefix} ({'ready' if runner and prefix_ready(data, runner) else 'not initialized'})")
    print(f"State:       {state}")
    print(f"Player:      {player} ({'found' if player.is_file() else 'MISSING'})")
    print(f"Working dir: {working} ({'found' if working.is_dir() else 'MISSING'})")
    assets = working / "assets"
    compiler = working / "compiler"
    print(f"Assets dir:  {assets} ({'found' if assets.is_dir() else 'not found'})")
    print(f"Compiler:    {compiler} ({'found' if compiler.is_dir() else 'not found'})")
    if data["runner"]["type"] == "proton":
        print("Proton:      managed by umu-run (Steam not required)")
    return 0 if runner and player.is_file() and working.is_dir() else 1


def command_setup(args: argparse.Namespace) -> int:
    try:
        data = load_manifest(args.workspace.expanduser())
    except ManifestError as exc:
        raise SidecarError(str(exc)) from exc
    runner = _get_runner(data)
    if prefix_ready(data, runner):
        print(f"Prefix already initialized: {get_prefix_path(data)}")
        return 0
    _ensure_prefix(data, runner)
    print(f"Prefix ready: {get_prefix_path(data)}")
    return 0


def command_run(args: argparse.Namespace) -> int:
    try:
        data = load_manifest(args.workspace.expanduser())
    except ManifestError as exc:
        raise SidecarError(str(exc)) from exc
    runner = _get_runner(data)
    player = get_player_path(data)
    working = get_working_directory(data)
    if not player.is_file():
        raise SidecarError(f"Windows player not found: {player}")
    if not working.is_dir():
        raise SidecarError(f"Player working directory not found: {working}")
    _ensure_prefix(data, runner)
    arguments = [*data["player"].get("arguments", []), *args.arguments]
    command = launch_command(runner, data, player, arguments)
    env = runner_environment(data, runner)
    return _print_process(command, working, env, _log_path(data, "run"))


def command_bundle(args: argparse.Namespace) -> int:
    try:
        data = load_manifest(args.workspace.expanduser())
        output = create_bundle(data, args.output)
    except (ManifestError, BundleError) as exc:
        raise SidecarError(str(exc)) from exc
    except OSError as exc:
        raise SidecarError(f"Could not create bundle: {exc}") from exc
    print(f"Created Linux launcher archive: {output}")
    print("The archive excludes game assets and Wine/Proton runtime files.")
    return 0


def command_backup(args: argparse.Namespace) -> int:
    try:
        data = load_manifest(args.workspace.expanduser())
        output = create_prefix_backup(data, args.output)
    except (ManifestError, PrefixOperationError) as exc:
        raise SidecarError(str(exc)) from exc
    except OSError as exc:
        raise SidecarError(f"Could not back up prefix: {exc}") from exc
    print(f"Prefix backup created: {output}")
    return 0


def command_reset(args: argparse.Namespace) -> int:
    try:
        data = load_manifest(args.workspace.expanduser())
        prefix = safe_prefix_path(data)
        if not prefix.exists():
            print(f"Prefix does not exist; nothing to reset: {prefix}")
            return 0
        if not args.yes:
            answer = input(
                f"Delete this title's Windows prefix at {prefix}? Saves and settings stored there will be deleted. [y/N] "
            )
            if answer.strip().lower() not in {"y", "yes"}:
                print("Reset cancelled.")
                return 1
        removed = reset_prefix(data)
    except (ManifestError, PrefixOperationError) as exc:
        raise SidecarError(str(exc)) from exc
    except EOFError:
        print("Reset cancelled: confirmation was not provided.", file=sys.stderr)
        return 1
    except OSError as exc:
        raise SidecarError(f"Could not reset prefix: {exc}") from exc
    print(f"Prefix removed: {removed}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="xbe-sidecar",
        description="Manage Linux Wine/Proton launches for XboxXBERecomp Windows releases.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="register a Windows player workspace")
    init.add_argument("workspace", type=Path)
    init.add_argument("--name")
    init.add_argument("--exe", required=True, help="player executable, relative to workspace or absolute")
    init.add_argument("--runner", choices=("wine", "proton"), default="proton")
    init.add_argument("--runner-executable", help="explicit Wine binary or umu-run executable")
    init.add_argument("--proton-path", help="Proton path or codename for umu-run")
    init.add_argument("--umu-folders-path", help="base directory for umu's Proton/runtime files")
    init.set_defaults(handler=command_init)

    runners = sub.add_parser("runners", help="list discoverable Wine and Proton runners")
    runners.set_defaults(handler=command_runners)

    doctor = sub.add_parser("doctor", help="inspect a registered title workspace")
    doctor.add_argument("workspace", type=Path)
    doctor.set_defaults(handler=command_doctor)

    setup = sub.add_parser("setup", help="create the title's isolated compatibility prefix")
    setup.add_argument("workspace", type=Path)
    setup.set_defaults(handler=command_setup)

    run = sub.add_parser("run", help="launch the registered Windows player")
    run.add_argument("workspace", type=Path)
    run.add_argument("arguments", nargs=argparse.REMAINDER, help="arguments forwarded to the Windows player")
    run.set_defaults(handler=command_run)

    bundle = sub.add_parser("bundle", help="package a Windows release with a Linux launcher")
    bundle.add_argument("workspace", type=Path)
    bundle.add_argument("--output", required=True, type=Path, help="destination .tar.gz path")
    bundle.set_defaults(handler=command_bundle)

    backup = sub.add_parser("backup", help="archive the title's Windows prefix")
    backup.add_argument("workspace", type=Path)
    backup.add_argument("--output", type=Path, help="destination .tar.gz path (default: Sidecar state directory)")
    backup.set_defaults(handler=command_backup)

    reset = sub.add_parser("reset", help="delete the title's Windows prefix")
    reset.add_argument("workspace", type=Path)
    reset.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    reset.set_defaults(handler=command_reset)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.handler(args)
    except SidecarError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

