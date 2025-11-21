"""Implementation for `linode-cli build init`."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

import yaml

from ..core import templates as template_core
from ..core import colors
from ..core import init_operations


# Use the core function (kept for backwards compatibility)
def _load_template_from_name_or_path(name_or_path: str, version: str | None = None):
    """Load template from either a name (bundled/remote) or a local path.
    
    This is now a wrapper around core.init_operations.load_template_from_name_or_path
    """
    return init_operations.load_template_from_name_or_path(name_or_path, version)


def register(subparsers: argparse._SubParsersAction, config) -> None:
    parser = subparsers.add_parser("init", help="Initialize a project from a template")
    parser.add_argument("template", help="Template name (e.g., 'chat-agent') or local path (e.g., './my-template')")
    parser.add_argument(
        "--directory",
        "-d",
        help="Project directory (defaults to current working directory)",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Skip interactive prompts, use template defaults",
    )
    parser.set_defaults(func=lambda args: _cmd_init(args, config))


def _cmd_init(args, config):
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

    # Interactive selection of region and plan (unless --non-interactive)
    deploy_data = template.data.copy()
    if not args.non_interactive:
        deploy_data = _interactive_configure(config, deploy_data)
    
    # Write deploy.yml (complete deployment config, user can edit)
    deploy_yml_path.write_text(
        yaml.safe_dump(deploy_data, sort_keys=False),
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
    print("  3. Run: linode-cli build deploy")
    
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
    """Generate .env.example content - wrapper around core function."""
    return init_operations.generate_env_example(template)


def _render_readme(template) -> str:
    """Generate README.md content - wrapper around core function."""
    return init_operations.generate_readme(template)


def _interactive_configure(config, deploy_data: dict) -> dict:
    """Interactively select region and instance type."""
    import sys
    
    client = config.client
    linode_cfg = deploy_data.get("deploy", {}).get("linode", {})
    
    # Get template defaults
    default_region = linode_cfg.get("region_default")
    default_type = linode_cfg.get("type_default")
    
    print()
    print(colors.header("=== Interactive Configuration ==="))
    print()
    
    # Fetch and select region
    try:
        print(colors.info("Fetching available regions..."))
        # call_operation returns (status_code, response_dict)
        status, response = client.call_operation('regions', 'list')
        regions = response.get('data', []) if status == 200 else []
        if regions:
            region = _select_region(regions, default_region)
        else:
            print(colors.warning(f"Warning: No regions returned. Using template default."))
            region = default_region
    except Exception as e:
        print(colors.warning(f"Warning: Could not fetch regions ({e}). Using template default."))
        region = default_region
    
    # Fetch and select instance type
    try:
        print()
        print(colors.info("Fetching available instance types..."))
        # call_operation returns (status_code, response_dict)
        status, response = client.call_operation('linodes', 'types')
        types = response.get('data', []) if status == 200 else []
        if types:
            instance_type = _select_instance_type(types, default_type)
        else:
            print(colors.warning(f"Warning: No types returned. Using template default."))
            instance_type = default_type
    except Exception as e:
        print(colors.warning(f"Warning: Could not fetch instance types ({e}). Using template default."))
        instance_type = default_type
    
    # Update deploy_data with selections
    if region:
        deploy_data["deploy"]["linode"]["region_default"] = region
    if instance_type:
        deploy_data["deploy"]["linode"]["type_default"] = instance_type
    
    print()
    print(colors.success(f"✓ Selected region: {region or default_region}"))
    print(colors.success(f"✓ Selected instance type: {instance_type or default_type}"))
    
    return deploy_data


def _select_region(regions, default: str) -> str:
    """Interactive region selection - wrapper around core function."""
    return init_operations.select_region_interactive(regions, default, input_func=input)


def _select_instance_type(types, default: str) -> str:
    """Interactive instance type selection - wrapper around core function."""
    return init_operations.select_instance_type_interactive(types, default, input_func=input)
