"""Implementation for `linode-cli ai init`."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

import yaml

from ..core import templates as template_core


def _load_template_from_name_or_path(name_or_path: str, version: str | None = None):
    """Load template from either a name (bundled/remote) or a local path.
    
    Args:
        name_or_path: Template name (e.g., 'llm-api') or local path (e.g., './my-template' or '/abs/path')
        version: Version for named templates (ignored for paths)
    
    Returns:
        Template instance
    """
    # Check if it's a file path
    # Paths: ./ ../ / ~ or just . or ..
    is_path = (
        name_or_path in ('.', '..') or
        name_or_path.startswith(('./', '../', '/', '~')) or
        '/' in name_or_path  # Contains slash = probably a path
    )
    
    if is_path:
        path = Path(name_or_path).expanduser().resolve()
        
        # If it's a directory, look for template.yml or template-stub.yml
        if path.is_dir():
            template_file = path / "template.yml"
            if not template_file.exists():
                # Try template-stub.yml
                template_file = path / "template-stub.yml"
                if not template_file.exists():
                    raise FileNotFoundError(
                        f"No template.yml or template-stub.yml found in {path}"
                    )
        elif path.is_file() and path.suffix in ['.yml', '.yaml']:
            template_file = path
        else:
            raise FileNotFoundError(f"Template path not found: {path}")
        
        # Load the template from file
        try:
            with open(template_file, 'r') as f:
                data = yaml.safe_load(f)
        except Exception as e:
            raise template_core.TemplateError(f"Error loading template from {template_file}: {e}")
        
        if not isinstance(data, dict):
            raise template_core.TemplateError(f"Template file must contain a YAML object: {template_file}")
        
        # Create Template instance
        return template_core.Template(
            name=data.get("name", path.stem),
            display_name=data.get("display_name", data.get("name", path.stem)),
            version=str(data.get("version", "0.0.0")),
            description=data.get("description", "").strip(),
            data=data,
        )
    else:
        # It's a template name, use the standard loader
        return template_core.load_template(name_or_path, version=version)


def register(subparsers: argparse._SubParsersAction, _config) -> None:
    parser = subparsers.add_parser("init", help="Initialize a project from a template")
    parser.add_argument("template", help="Template name (e.g., 'chat-agent') or local path (e.g., './my-template')")
    parser.add_argument(
        "--directory",
        "-d",
        help="Project directory (defaults to current working directory)",
    )
    parser.set_defaults(func=_cmd_init)


def _cmd_init(args):
    # Parse template name and version (e.g., 'chat-agent@0.2.0')
    template_spec = args.template
    version = None
    if '@' in template_spec:
        template_name, version = template_spec.split('@', 1)
    else:
        template_name = template_spec
    
    # Check if template_name is a local path
    template = _load_template_from_name_or_path(template_name, version)
    target_dir = _resolve_directory(args.directory)

    # Files to create
    deploy_yml_path = target_dir / "deploy.yml"
    env_example_path = target_dir / ".env.example"
    readme_path = target_dir / "README.md"

    _ensure_can_write(deploy_yml_path)
    _ensure_can_write(env_example_path)

    # Write deploy.yml (complete deployment config, user can edit)
    deploy_yml_path.write_text(
        yaml.safe_dump(template.data, sort_keys=False),
        encoding="utf-8",
    )

    env_lines = _render_env_example(template)
    env_example_path.write_text("\n".join(env_lines) + ("\n" if env_lines else ""), encoding="utf-8")

    if not readme_path.exists():
        readme_content = _render_readme(template)
        readme_path.write_text(readme_content, encoding="utf-8")

    print(f"✓ Initialized {template.display_name} in {target_dir}")
    print()
    print("Files created:")
    print(f"  - deploy.yml        (deployment configuration - customize as needed)")
    print(f"  - .env.example      (environment variables template)")
    print(f"  - README.md         (usage instructions)")
    print()
    print("Next steps:")
    print("  1. Review and customize deploy.yml (region, instance type, etc.)")
    print("  2. Copy .env.example to .env and fill in required values")
    print("  3. Run: linode-cli ai deploy")
    
    # Print guidance if available
    guidance = template.data.get("guidance", {})
    if guidance.get("summary"):
        print()
        print(guidance["summary"])


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
    deploy_yml = target / "deploy.yml"
    if deploy_yml.exists():
        raise FileExistsError(
            f"{deploy_yml} already exists in the current directory. Use --directory to target another path."
        )
    return target


def _ensure_can_write(path: Path) -> None:
    if path.exists():
        raise FileExistsError(f"{path} already exists")
    path.parent.mkdir(parents=True, exist_ok=True)


def _render_env_example(template) -> List[str]:
    env_cfg = template.data.get("env", {})
    lines: List[str] = []
    
    # Add required variables
    required = env_cfg.get("required", [])
    if required:
        lines.append("# Required environment variables")
        for item in required:
            name = item.get("name")
            desc = item.get("description", "")
            if desc:
                # Handle multi-line descriptions - prefix each line with #
                for line in desc.strip().split('\n'):
                    lines.append(f"# {line}")
            lines.append(f"{name}=")
            lines.append("")
    
    # Add optional variables
    optional = env_cfg.get("optional", [])
    if optional:
        if required:
            lines.append("")
        lines.append("# Optional environment variables")
        for item in optional:
            name = item.get("name")
            desc = item.get("description", "")
            if desc:
                # Handle multi-line descriptions - prefix each line with #
                for line in desc.strip().split('\n'):
                    lines.append(f"# {line}")
            lines.append(f"# {name}=")
            lines.append("")
    
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
