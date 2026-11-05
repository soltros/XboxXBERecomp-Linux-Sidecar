from __future__ import annotations

import os
import shutil
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path

from .manifest import get_prefix_path, get_state_path


class PrefixOperationError(ValueError):
    pass


def safe_prefix_path(data: dict) -> Path:
    prefix = get_prefix_path(data)
    workspace = data["_workspace"].resolve()
    home = Path.home().resolve()
    raw_path = data["prefix"]["path"]
    substitutions = {
        "${XDG_DATA_HOME}": os.environ.get("XDG_DATA_HOME", str(home / ".local/share")),
        "${XDG_STATE_HOME}": os.environ.get("XDG_STATE_HOME", str(home / ".local/state")),
        "$XDG_DATA_HOME": os.environ.get("XDG_DATA_HOME", str(home / ".local/share")),
        "$XDG_STATE_HOME": os.environ.get("XDG_STATE_HOME", str(home / ".local/state")),
    }
    lexical_path = raw_path
    for variable, replacement in substitutions.items():
        lexical_path = lexical_path.replace(variable, replacement)
    configured = Path(os.path.expandvars(lexical_path)).expanduser()
    if not configured.is_absolute():
        configured = workspace / configured
    configured = Path(os.path.abspath(configured))
    if configured != prefix:
        raise PrefixOperationError(f"Refusing prefix paths that traverse a symbolic link: {configured}")
    if (
        prefix == Path(prefix.anchor)
        or prefix == home
        or prefix == workspace
        or prefix in home.parents
    ):
        raise PrefixOperationError(f"Refusing unsafe prefix path: {prefix}")
    if prefix in workspace.parents or workspace in prefix.parents:
        raise PrefixOperationError(
            f"Prefix and title workspace must not contain one another: {prefix} and {workspace}"
        )
    if prefix.is_symlink():
        raise PrefixOperationError(f"Refusing to operate on a symlink prefix: {prefix}")
    return prefix


def create_prefix_backup(data: dict, output: Path | None = None) -> Path:
    prefix = safe_prefix_path(data)
    if not prefix.is_dir():
        raise PrefixOperationError(f"Prefix does not exist: {prefix}")
    if output is None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output = get_state_path(data) / "backups" / f"prefix-{stamp}.tar.gz"
    output = output.expanduser().resolve()
    if output.exists() or output.is_symlink():
        raise PrefixOperationError(f"Backup destination already exists: {output}")
    if output == prefix or prefix in output.parents:
        raise PrefixOperationError("Backup archive must be stored outside the prefix")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=output.name + ".", suffix=".partial", dir=output.parent, delete=False
    ) as temporary_file:
        temporary_archive = Path(temporary_file.name)
    try:
        with tarfile.open(temporary_archive, "w:gz") as archive:
            archive.add(prefix, arcname=prefix.name, recursive=True)
        os.replace(temporary_archive, output)
    finally:
        temporary_archive.unlink(missing_ok=True)
    return output


def reset_prefix(data: dict) -> Path:
    prefix = safe_prefix_path(data)
    if not prefix.exists():
        return prefix
    if not prefix.is_dir():
        raise PrefixOperationError(f"Prefix path is not a directory: {prefix}")
    shutil.rmtree(prefix)
    return prefix
