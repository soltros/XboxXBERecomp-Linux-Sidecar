from __future__ import annotations

import hashlib
import json
import os
import re
import tomllib
from pathlib import Path
from typing import Any


MANIFEST_NAME = "sidecar.toml"


class ManifestError(ValueError):
    pass


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def create_manifest(
    workspace: Path,
    *,
    name: str,
    executable: str,
    runner: str,
    runner_executable: str | None,
    proton_path: str | None,
    umu_folders_path: str | None,
) -> Path:
    manifest = workspace / MANIFEST_NAME
    if manifest.exists():
        raise ManifestError(f"{manifest} already exists")

    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "title"
    identity = hashlib.sha256(
        f"{workspace.resolve()}\0{name}\0{executable}".encode("utf-8")
    ).hexdigest()[:10]
    data_root = f"$XDG_DATA_HOME/xbe-sidecar/{slug}-{identity}"
    state_root = f"$XDG_STATE_HOME/xbe-sidecar/{slug}-{identity}"
    executable_path = Path(executable).expanduser()
    if executable_path.is_absolute():
        try:
            working_directory = executable_path.resolve().parent.relative_to(workspace.resolve()).as_posix()
        except ValueError:
            working_directory = str(executable_path.resolve().parent)
    else:
        working_directory = executable_path.parent.as_posix() or "."

    lines = [
        "[title]",
        f"name = {_toml_string(name)}",
        "",
        "[runner]",
        f"type = {_toml_string(runner)}",
    ]
    if runner_executable:
        lines.append(f"executable = {_toml_string(runner_executable)}")
    if proton_path:
        lines.append(f"proton_path = {_toml_string(proton_path)}")
    if umu_folders_path:
        lines.append(f"umu_folders_path = {_toml_string(umu_folders_path)}")
    lines.extend(
        [
            "",
            "[prefix]",
            f"path = {_toml_string(data_root + '/prefix')}",
            "",
            "[storage]",
            f"state = {_toml_string(state_root)}",
            "",
            "[player]",
            f"executable = {_toml_string(executable)}",
            f"working_directory = {_toml_string(working_directory)}",
            "arguments = []",
            "",
            "[environment]",
            "",
        ]
    )
    manifest.write_text("\n".join(lines), encoding="utf-8")
    return manifest


def load_manifest(path: Path) -> dict[str, Any]:
    manifest_path = path / MANIFEST_NAME if path.is_dir() else path
    if not manifest_path.is_file():
        raise ManifestError(f"No {MANIFEST_NAME} found at {manifest_path}")
    try:
        data = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ManifestError(f"Could not read {manifest_path}: {exc}") from exc

    title = data.get("title")
    runner = data.get("runner")
    prefix = data.get("prefix")
    player = data.get("player")
    environment = data.get("environment", {})
    storage = data.get("storage", {})
    if not isinstance(title, dict) or not isinstance(title.get("name"), str):
        raise ManifestError("[title].name must be a string")
    if not isinstance(runner, dict) or runner.get("type") not in {"wine", "proton"}:
        raise ManifestError('[runner].type must be "wine" or "proton"')
    if "executable" in runner and not isinstance(runner["executable"], str):
        raise ManifestError("[runner].executable must be a string")
    if "proton_path" in runner and not isinstance(runner["proton_path"], str):
        raise ManifestError("[runner].proton_path must be a string")
    if "umu_folders_path" in runner and not isinstance(runner["umu_folders_path"], str):
        raise ManifestError("[runner].umu_folders_path must be a string")
    if not isinstance(prefix, dict) or not isinstance(prefix.get("path"), str):
        raise ManifestError("[prefix].path must be a string")
    if not isinstance(player, dict) or not isinstance(player.get("executable"), str):
        raise ManifestError("[player].executable must be a string")
    if not isinstance(player.get("working_directory", "."), str):
        raise ManifestError("[player].working_directory must be a string")
    arguments = player.get("arguments", [])
    if not isinstance(arguments, list) or not all(isinstance(arg, str) for arg in arguments):
        raise ManifestError("[player].arguments must be an array of strings")
    if not isinstance(environment, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in environment.items()
    ):
        raise ManifestError("[environment] values must be strings")
    if not isinstance(storage, dict) or (
        "state" in storage and not isinstance(storage["state"], str)
    ):
        raise ManifestError("[storage].state must be a string")

    data["_manifest_path"] = manifest_path.resolve()
    data["_workspace"] = manifest_path.resolve().parent
    return data


def resolve_workspace_path(data: dict[str, Any], value: str) -> Path:
    substitutions = {
        "${XDG_DATA_HOME}": os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")),
        "${XDG_STATE_HOME}": os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state")),
        "$XDG_DATA_HOME": os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")),
        "$XDG_STATE_HOME": os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state")),
    }
    expanded = value
    for key, replacement in substitutions.items():
        expanded = expanded.replace(key, replacement)
    path = Path(os.path.expandvars(expanded)).expanduser()
    return path.resolve() if path.is_absolute() else (data["_workspace"] / path).resolve()


def get_prefix_path(data: dict[str, Any]) -> Path:
    return resolve_workspace_path(data, data["prefix"]["path"])


def get_state_path(data: dict[str, Any]) -> Path:
    storage = data.get("storage", {})
    if isinstance(storage.get("state"), str):
        return resolve_workspace_path(data, storage["state"])
    return data["_workspace"] / ".sidecar"


def get_player_path(data: dict[str, Any]) -> Path:
    return resolve_workspace_path(data, data["player"]["executable"])


def get_working_directory(data: dict[str, Any]) -> Path:
    return resolve_workspace_path(data, data["player"].get("working_directory", "."))


def write_bundle_manifest(workspace: Path, data: dict[str, Any], executable_name: str) -> Path:
    """Write a sanitized manifest for a relocatable title bundle."""
    name = data["title"]["name"]
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "title"
    identity = hashlib.sha256(f"{data['_workspace']}\0{name}".encode("utf-8")).hexdigest()[:10]
    data_root = f"$XDG_DATA_HOME/xbe-sidecar/{slug}-{identity}"
    state_root = f"$XDG_STATE_HOME/xbe-sidecar/{slug}-{identity}"
    runner = data["runner"]
    lines = [
        "[title]",
        f"name = {_toml_string(name)}",
        "",
        "[runner]",
        f"type = {_toml_string(runner['type'])}",
    ]
    proton_path = runner.get("proton_path")
    if proton_path and "/" not in proton_path and "\\" not in proton_path and not proton_path.startswith("~"):
        lines.append(f"proton_path = {_toml_string(proton_path)}")
    lines.extend(
        [
            "",
            "[prefix]",
            f"path = {_toml_string(data_root + '/prefix')}",
            "",
            "[storage]",
            f"state = {_toml_string(state_root)}",
            "",
            "[player]",
            f"executable = {_toml_string(executable_name)}",
            'working_directory = "."',
            "arguments = " + json.dumps(data["player"].get("arguments", []), ensure_ascii=False),
            "",
            "[environment]",
            "",
        ]
    )
    manifest = workspace / MANIFEST_NAME
    manifest.write_text("\n".join(lines), encoding="utf-8")
    return manifest
