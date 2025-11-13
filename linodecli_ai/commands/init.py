"""Implementation for `linode-cli ai init`."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

import yaml

from ..core import templates as template_core
from ..core.project import DEFAULT_MANIFEST


def register(subparsers: argparse._SubParsersAction, _config) -> None:
    parser = subparsers.add_parser("init", help="Initialize a project from a template")
    parser.add_argument("template", help="Template name to initialize")
    parser.add_argument(
        "--directory",
        "-d",
        help="Project directory (defaults to current working directory)",
    )
    parser.set_defaults(func=_cmd_init)


def _cmd_init(args):
    template = template_core.load_template(args.template)
    target_dir = _resolve_directory(args.directory)

    manifest_path = target_dir / DEFAULT_MANIFEST
    env_example_path = target_dir / ".env.example"
    readme_path = target_dir / "README.md"

    _ensure_can_write(manifest_path)
    _ensure_can_write(env_example_path)

    defaults = template.manifest_defaults()
    manifest_path.write_text(
        yaml.safe_dump(defaults, sort_keys=False),
        encoding="utf-8",
    )

    env_lines = _render_env_example(template)
    env_example_path.write_text("\n".join(env_lines) + ("\n" if env_lines else ""), encoding="utf-8")

    if not readme_path.exists():
        readme_content = _render_readme(template)
        readme_path.write_text(readme_content, encoding="utf-8")

    print(f"Initialized {template.display_name} in {target_dir}")


def _resolve_directory(directory: str | None) -> Path:
    if directory:
        target = Path(directory).expanduser()
        if target.exists():
            if any(target.iterdir()):
                raise FileExistsError(f"Directory is not empty: {target}")
        else:
            target.mkdir(parents=True, exist_ok=False)
        return target

    target = Path.cwd()
    manifest = target / DEFAULT_MANIFEST
    if manifest.exists():
        raise FileExistsError(
            f"{manifest} already exists in the current directory. Use --directory to target another path."
        )
    return target


def _ensure_can_write(path: Path) -> None:
    if path.exists():
        raise FileExistsError(f"{path} already exists")
    path.parent.mkdir(parents=True, exist_ok=True)


def _render_env_example(template) -> List[str]:
    env_cfg = template.data.get("env", {})
    lines: List[str] = []
    for item in env_cfg.get("required", []):
        name = item.get("name")
        lines.append(f"{name}=")
    for item in env_cfg.get("optional", []):
        name = item.get("name")
        lines.append(f"# Optional: {name}=")
    if not lines:
        lines.append("# No environment variables required for this template.")
    return lines


def _render_readme(template) -> str:
    description = template.description or template.display_name
    content = [
        f"# {template.display_name}",
        "",
        description,
        "",
        "## Quickstart",
        "",
        "1. Copy `.env.example` to `.env` and fill in any required values.",
        "2. Deploy with `linode-cli ai deploy`.",
    ]
    return "\n".join(content) + "\n"
