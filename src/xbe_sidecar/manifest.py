from __future__ import annotations

import json
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
) -> Path:
    manifest = workspace / MANIFEST_NAME
    if manifest.exists():
        raise ManifestError(f"{manifest} already exists")

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
    lines.extend(
        [
            "",
            "[prefix]",
            'path = ".sidecar/prefix"',
            "",
            "[player]",
            f"executable = {_toml_string(executable)}",
            'working_directory = "."',
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
    if not isinstance(title, dict) or not isinstance(title.get("name"), str):
        raise ManifestError("[title].name must be a string")
    if not isinstance(runner, dict) or runner.get("type") not in {"wine", "proton"}:
        raise ManifestError('[runner].type must be "wine" or "proton"')
    if "executable" in runner and not isinstance(runner["executable"], str):
        raise ManifestError("[runner].executable must be a string")
    if "proton_path" in runner and not isinstance(runner["proton_path"], str):
        raise ManifestError("[runner].proton_path must be a string")
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

    data["_manifest_path"] = manifest_path.resolve()
    data["_workspace"] = manifest_path.resolve().parent
    return data


def resolve_workspace_path(data: dict[str, Any], value: str) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (data["_workspace"] / path).resolve()


def get_prefix_path(data: dict[str, Any]) -> Path:
    return resolve_workspace_path(data, data["prefix"]["path"])


def get_player_path(data: dict[str, Any]) -> Path:
    return resolve_workspace_path(data, data["player"]["executable"])


def get_working_directory(data: dict[str, Any]) -> Path:
    return resolve_workspace_path(data, data["player"].get("working_directory", "."))
