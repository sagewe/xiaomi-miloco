#!/usr/bin/env python3
"""Install the prebuilt miloco-agent-runtime wheel from GitHub Releases."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_REPOSITORY = "XiaoMi/xiaomi-miloco"


def detect_package_version() -> str:
    override = os.getenv("MILOCO_AGENT_RUNTIME_PACKAGE_VERSION")
    if override:
        return override

    project_root = Path(__file__).resolve().parent.parent
    pyproject_file = project_root / "native" / "miloco-agent-runtime" / "pyproject.toml"
    data = tomllib.loads(pyproject_file.read_text(encoding="utf-8"))
    return data["project"]["version"]


def detect_platform_tag() -> str:
    machine = platform.machine().lower()
    if machine in {"x86_64", "amd64"}:
        return "x86_64"
    if machine in {"aarch64", "arm64"}:
        return "aarch64"
    raise RuntimeError(f"Unsupported platform architecture for prebuilt wheel: {machine}")


def resolve_release_wheel_url(version: str) -> str:
    python_tag = f"cp{sys.version_info.major}{sys.version_info.minor}"
    if python_tag != "cp312":
        raise RuntimeError(
            f"Prebuilt wheel release path currently supports Python 3.12 only, got {python_tag}"
        )

    platform_tag = detect_platform_tag()
    repository = os.getenv("MILOCO_AGENT_RUNTIME_REPOSITORY", DEFAULT_REPOSITORY)
    package_version = detect_package_version()
    expected_prefix = f"miloco_agent_runtime-{package_version}-{python_tag}-{python_tag}-"
    release_api_url = f"https://api.github.com/repos/{repository}/releases/tags/{version}"

    request = urllib.request.Request(
        release_api_url,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request) as response:
            release_data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"Unable to resolve GitHub release assets for {repository}@{version}: {exc}"
        ) from exc
    for asset in release_data.get("assets", []):
        asset_name = asset.get("name", "")
        if not asset_name.startswith(expected_prefix) or not asset_name.endswith(".whl"):
            continue
        if platform_tag not in asset_name:
            continue
        return asset["browser_download_url"]

    raise RuntimeError(
        f"Could not find a cp312 Linux wheel for {platform_tag} in release {repository}@{version}"
    )


def main() -> int:
    wheel_url = os.getenv("MILOCO_AGENT_RUNTIME_WHEEL_URL")
    version = os.getenv("MILOCO_AGENT_RUNTIME_VERSION")

    if not wheel_url:
        if not version:
            print("Skipping miloco-agent-runtime install: no version or wheel URL configured")
            return 0
        wheel_url = resolve_release_wheel_url(version)

    print(f"Installing miloco-agent-runtime from {wheel_url}")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--no-deps", wheel_url],
        check=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
