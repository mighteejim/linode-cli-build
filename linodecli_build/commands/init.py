"""Implementation for `linode-cli build init`."""

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
        "2. Deploy with `linode-cli build deploy`.",
    ]
    return "\n".join(content) + "\n"


def _interactive_configure(config, deploy_data: dict) -> dict:
    """Interactively select region and instance type."""
    import sys
    
    client = config.client
    linode_cfg = deploy_data.get("deploy", {}).get("linode", {})
    
    # Get template defaults
    default_region = linode_cfg.get("region_default")
    default_type = linode_cfg.get("type_default")
    
    print()
    print("=== Interactive Configuration ===")
    print()
    
    # Fetch and select region
    try:
        print("Fetching available regions...")
        # call_operation returns (status_code, response_dict)
        status, response = client.call_operation('regions', 'list')
        regions = response.get('data', []) if status == 200 else []
        if regions:
            region = _select_region(regions, default_region)
        else:
            print(f"Warning: No regions returned. Using template default.")
            region = default_region
    except Exception as e:
        print(f"Warning: Could not fetch regions ({e}). Using template default.")
        region = default_region
    
    # Fetch and select instance type
    try:
        print()
        print("Fetching available instance types...")
        # call_operation returns (status_code, response_dict)
        status, response = client.call_operation('linodes', 'types')
        types = response.get('data', []) if status == 200 else []
        if types:
            instance_type = _select_instance_type(types, default_type)
        else:
            print(f"Warning: No types returned. Using template default.")
            instance_type = default_type
    except Exception as e:
        print(f"Warning: Could not fetch instance types ({e}). Using template default.")
        instance_type = default_type
    
    # Update deploy_data with selections
    if region:
        deploy_data["deploy"]["linode"]["region_default"] = region
    if instance_type:
        deploy_data["deploy"]["linode"]["type_default"] = instance_type
    
    print()
    print(f"✓ Selected region: {region or default_region}")
    print(f"✓ Selected instance type: {instance_type or default_type}")
    
    return deploy_data


def _select_region(regions, default: str) -> str:
    """Interactive region selection."""
    import sys
    
    # Sort regions by ID
    sorted_regions = sorted(regions, key=lambda r: r.get('id', ''))
    
    print()
    print("Available Regions:")
    print("-" * 60)
    
    # Display regions in a compact format
    for i, region in enumerate(sorted_regions, 1):
        region_id = region.get('id', 'unknown')
        label = region.get('label', region_id)
        status = region.get('status', 'unknown')
        status_icon = "✓" if status == "ok" else "✗"
        default_marker = " (default)" if region_id == default else ""
        print(f"{i:3}. {status_icon} {region_id:20} - {label}{default_marker}")
    
    print("-" * 60)
    
    # Get user selection
    while True:
        prompt = f"Select region [1-{len(sorted_regions)}] (Enter for default: {default}): "
        choice = input(prompt).strip()
        
        if not choice:
            return default
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(sorted_regions):
                return sorted_regions[idx].get('id')
            else:
                print(f"Invalid choice. Please enter 1-{len(sorted_regions)}")
        except ValueError:
            print("Invalid input. Please enter a number.")


def _select_instance_type(types, default: str) -> str:
    """Interactive instance type selection."""
    import sys
    
    # Filter and categorize types
    gpu_types = [t for t in types if t.get('id', '').startswith('g6-') or t.get('id', '').startswith('g2-gpu')]
    standard_types = [t for t in types if not (t.get('id', '').startswith('g6-') or t.get('id', '').startswith('g2-gpu')) 
                     and t.get('class', '') in ['standard', 'dedicated']]
    
    # Sort by price
    gpu_types.sort(key=lambda t: t.get('price', {}).get('hourly', 0))
    standard_types.sort(key=lambda t: t.get('price', {}).get('hourly', 0))
    
    print()
    print("Available Instance Types:")
    print("=" * 80)
    
    all_types = []
    
    # Show GPU types
    if gpu_types:
        print()
        print("GPU Instances (for AI/ML workloads):")
        print("-" * 80)
        for t in gpu_types:  # Show all GPU types
            type_id = t.get('id', 'unknown')
            default_marker = " (default)" if type_id == default else ""
            idx = len(all_types) + 1
            all_types.append(t)
            price = t.get('price', {}).get('hourly', 0)
            memory = t.get('memory', 0)
            vcpus = t.get('vcpus', 0)
            disk = t.get('disk', 0)
            print(f"{idx:3}. {type_id:30} ${price:6.2f}/hr  "
                  f"{memory:6}MB RAM  {vcpus:2} vCPUs  {disk:8}MB{default_marker}")
    
    # Show standard types
    if standard_types:
        print()
        print("Standard Instances:")
        print("-" * 80)
        for t in standard_types[:25]:  # Show top 25 standard types
            type_id = t.get('id', 'unknown')
            default_marker = " (default)" if type_id == default else ""
            idx = len(all_types) + 1
            all_types.append(t)
            price = t.get('price', {}).get('hourly', 0)
            memory = t.get('memory', 0)
            vcpus = t.get('vcpus', 0)
            disk = t.get('disk', 0)
            print(f"{idx:3}. {type_id:30} ${price:6.2f}/hr  "
                  f"{memory:6}MB RAM  {vcpus:2} vCPUs  {disk:8}MB{default_marker}")
    
    print("=" * 80)
    
    # Get user selection
    while True:
        prompt = f"Select instance type [1-{len(all_types)}] (Enter for default: {default}): "
        choice = input(prompt).strip()
        
        if not choice:
            return default
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(all_types):
                return all_types[idx].get('id')
            else:
                print(f"Invalid choice. Please enter 1-{len(all_types)}")
        except ValueError:
            print("Invalid input. Please enter a number.")
