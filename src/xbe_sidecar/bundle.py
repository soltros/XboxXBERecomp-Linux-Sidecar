from __future__ import annotations

import os
import re
import shutil
import tarfile
import tempfile
from pathlib import Path

from .manifest import (
    get_player_path,
    get_working_directory,
    write_bundle_manifest,
)


class BundleError(ValueError):
    pass


_RUNTIME_DLLS = ("msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll")
_DOC_FILES = ("README.md", "THIRD_PARTY.txt", "LICENSE", "LICENSE.txt")


def _copy_regular_file(source: Path, destination: Path) -> None:
    if source.is_symlink():
        raise BundleError(f"Refusing to package symlink: {source}")
    if not source.is_file():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _copy_compiler_tree(source: Path, destination: Path) -> None:
    if source.is_symlink() or not source.is_dir():
        raise BundleError(f"Expected the release compiler directory at {source}")
    for current, directories, files in os.walk(source, followlinks=False):
        current_path = Path(current)
        relative = current_path.relative_to(source)
        directories[:] = [
            name
            for name in directories
            if name.lower() != "work" and not (current_path / name).is_symlink()
        ]
        target_directory = destination / relative
        target_directory.mkdir(parents=True, exist_ok=True)
        for filename in files:
            source_file = current_path / filename
            if source_file.is_symlink():
                continue
            _copy_regular_file(source_file, target_directory / filename)


def _write_launcher(package: Path) -> None:
    launcher = package / "run.sh"
    launcher.write_text(
        "#!/bin/sh\n"
        "set -eu\n"
        'APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\n'
        "if ! command -v python3 >/dev/null 2>&1; then\n"
        '    echo "Python 3.11 or newer is required." >&2\n'
        "    exit 127\n"
        "fi\n"
        "if ! python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 11))'; then\n"
        '    echo "Python 3.11 or newer is required." >&2\n'
        "    exit 2\n"
        "fi\n"
        'PYTHONPATH="$APP_DIR/lib${PYTHONPATH:+:$PYTHONPATH}" exec python3 -m xbe_sidecar run "$APP_DIR" "$@"\n',
        encoding="utf-8",
    )
    launcher.chmod(0o755)


def _write_bundle_readme(package: Path, title_name: str) -> None:
    (package / "LINUX-README.txt").write_text(
        f"{title_name} Linux Sidecar bundle\n"
        "================================\n\n"
        "This archive contains the XboxXBERecomp Windows player release and the Linux Sidecar launcher.\n"
        "The executable remains a Windows program and runs through Wine or Proton.\n\n"
        "Requirements:\n"
        "- Linux x86-64\n"
        "- Python 3.11 or newer\n"
        "- umu-launcher (recommended) or Wine\n"
        "- A Vulkan-capable graphics driver for Proton's D3D12 translation\n\n"
        "Run ./run.sh after adding the game files you own to ./assets. The archive intentionally leaves\n"
        "assets empty and does not include game code or data. On the first Proton run, umu may download\n"
        "Proton and the Steam Linux Runtime. Prefixes and logs are stored in the user's XDG data/state\n"
        "directories, not in this bundle.\n\n"
        "This archive does not contain Wine, Proton, UMU, Python, or the Linux graphics driver.\n",
        encoding="utf-8",
    )


def create_bundle(data: dict, output: Path) -> Path:
    player = get_player_path(data)
    working = get_working_directory(data)
    if not player.is_file():
        raise BundleError(f"Windows player not found: {player}")
    if not working.is_dir():
        raise BundleError(f"Player working directory not found: {working}")
    if player.parent != working:
        raise BundleError(
            "For bundling, the player executable must be directly inside its working directory. "
            "Set [player].working_directory in sidecar.toml to the executable's directory."
        )
    compiler = working / "compiler"
    tools = (
        {entry.name.lower(): entry for entry in compiler.iterdir() if not entry.is_symlink()}
        if compiler.is_dir() and not compiler.is_symlink()
        else {}
    )
    for required in ("clang.exe", "lld-link.exe"):
        tool = tools.get(required)
        if tool is None or not tool.is_file():
            raise BundleError(f"Required first-run compiler tool is missing: {compiler / required}")

    output = output.expanduser().resolve()
    if output.exists() or output.is_symlink():
        raise BundleError(f"Output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    title_name = data["title"]["name"]
    safe_name = re.sub(r"[^a-z0-9]+", "-", title_name.lower()).strip("-") or "title"
    with tempfile.TemporaryDirectory(prefix="xbe-sidecar-bundle-") as temporary:
        root = Path(temporary) / safe_name
        root.mkdir()
        _copy_regular_file(player, root / player.name)
        _copy_compiler_tree(compiler, root / "compiler")

        assets = root / "assets"
        assets.mkdir()
        for filename in _RUNTIME_DLLS:
            for candidate in (working / filename, data["_workspace"] / filename):
                if candidate.is_file():
                    _copy_regular_file(candidate, root / filename)
                    break
        for filename in _DOC_FILES:
            source = data["_workspace"] / filename
            if source.is_file():
                _copy_regular_file(source, root / filename)

        write_bundle_manifest(root, data, player.name)
        source_package = Path(__file__).resolve().parent
        package_library = root / "lib" / "xbe_sidecar"
        package_library.mkdir(parents=True)
        for source in source_package.glob("*.py"):
            _copy_regular_file(source, package_library / source.name)
        _write_launcher(root)
        _write_bundle_readme(root, title_name)

        with tempfile.NamedTemporaryFile(
            prefix=output.name + ".", suffix=".partial", dir=output.parent, delete=False
        ) as temporary_file:
            temporary_archive = Path(temporary_file.name)
        try:
            with tarfile.open(temporary_archive, "w:gz") as archive:
                archive.add(root, arcname=safe_name, recursive=True)
            os.replace(temporary_archive, output)
        finally:
            temporary_archive.unlink(missing_ok=True)
    return output
