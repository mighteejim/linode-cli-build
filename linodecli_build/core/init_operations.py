"""Core initialization operations - reusable logic for both CLI and TUI."""

from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Callable
import yaml

from . import templates as template_core


def load_template_from_name_or_path(name_or_path: str, version: str | None = None):
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


def generate_env_example(template) -> List[str]:
    """Generate .env.example content from template.
    
    Args:
        template: Template instance with env configuration
    
    Returns:
        List of lines for .env.example file
    """
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


def generate_readme(template) -> str:
    """Generate README.md content from template.
    
    Args:
        template: Template instance
    
    Returns:
        README.md content as string
    """
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


def select_region_interactive(
    regions: List[Dict],
    default: str,
    input_func: Callable[[str], str] = input
) -> str:
    """Interactive region selection grouped by geography.
    
    Args:
        regions: List of region dicts from API
        default: Default region ID
        input_func: Function to get user input (for TUI compatibility)
    
    Returns:
        Selected region ID
    """
    from . import colors
    
    # Geographic groupings based on country codes
    geo_groups = {
        'Americas': ['us', 'ca'],
        'South America': ['br', 'cl', 'ar'],
        'Europe': ['gb', 'uk', 'de', 'fr', 'nl', 'se', 'it', 'es', 'pl'],
        'Asia': ['jp', 'sg', 'in', 'id', 'kr', 'ae'],
        'Oceania': ['au', 'nz']
    }
    
    # Group regions by geography
    grouped = {geo: [] for geo in geo_groups}
    other = []
    
    for region in regions:
        region_id = region.get('id', '')
        country_code = region_id.split('-')[0] if '-' in region_id else ''
        
        placed = False
        for geo, codes in geo_groups.items():
            if country_code in codes:
                grouped[geo].append(region)
                placed = True
                break
        
        if not placed:
            other.append(region)
    
    # Build ordered list of all regions
    all_regions = []
    
    print()
    print(colors.header("Available Regions:"))
    print("=" * 70)
    
    # Display each geographic group
    for geo in ['Americas', 'Europe', 'Asia', 'South America', 'Oceania']:
        group_regions = sorted(grouped[geo], key=lambda r: r.get('id', ''))
        if not group_regions:
            continue
            
        print()
        print(colors.bold(f"{geo}:"))
        print("-" * 70)
        
        for region in group_regions:
            region_id = region.get('id', 'unknown')
            label = region.get('label', region_id)
            status = region.get('status', 'unknown')
            status_icon = colors.success("✓") if status == "ok" else colors.error("✗")
            default_marker = colors.default(" (default)") if region_id == default else ""
            idx = len(all_regions) + 1
            all_regions.append(region)
            print(f"{idx:3}. {status_icon} {colors.value(region_id):20} - {label}{default_marker}")
    
    # Display other regions if any
    if other:
        print()
        print("Other:")
        print("-" * 70)
        for region in sorted(other, key=lambda r: r.get('id', '')):
            region_id = region.get('id', 'unknown')
            label = region.get('label', region_id)
            status = region.get('status', 'unknown')
            status_icon = "✓" if status == "ok" else "✗"
            default_marker = " (default)" if region_id == default else ""
            idx = len(all_regions) + 1
            all_regions.append(region)
            print(f"{idx:3}. {status_icon} {region_id:20} - {label}{default_marker}")
    
    print("=" * 70)
    
    # Get user selection
    while True:
        prompt = f"\nSelect region [1-{len(all_regions)}] (Enter for default: {colors.default(default)}): "
        choice = input_func(prompt).strip()
        
        if not choice:
            return default
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(all_regions):
                return all_regions[idx].get('id')
            else:
                print(f"Invalid choice. Please enter 1-{len(all_regions)}")
        except ValueError:
            print("Invalid input. Please enter a number.")


def select_instance_type_interactive(
    types: List[Dict],
    default: str,
    input_func: Callable[[str], str] = input
) -> str:
    """Interactive instance type selection grouped by plan type.
    
    Args:
        types: List of instance type dicts from API
        default: Default instance type ID
        input_func: Function to get user input (for TUI compatibility)
    
    Returns:
        Selected instance type ID
    """
    from . import colors
    
    # Categorize types by plan type
    categorized = {
        'GPU Linodes': [],
        'Accelerated Linodes': [],
        'Premium Linodes': [],
        'High Memory Linodes': [],
        'Dedicated CPU': [],
        'Shared CPU': []
    }
    
    for t in types:
        type_id = t.get('id', '')
        type_class = t.get('class', '')
        
        if type_class == 'gpu':
            categorized['GPU Linodes'].append(t)
        elif type_class == 'accelerated':
            categorized['Accelerated Linodes'].append(t)
        elif type_class == 'premium' or type_id.startswith('g7-premium'):
            categorized['Premium Linodes'].append(t)
        elif 'highmem' in type_id:
            categorized['High Memory Linodes'].append(t)
        elif 'dedicated' in type_id or type_class == 'dedicated':
            categorized['Dedicated CPU'].append(t)
        elif type_class == 'standard':
            categorized['Shared CPU'].append(t)
    
    # Sort each category by price
    for category in categorized:
        categorized[category].sort(key=lambda t: t.get('price', {}).get('hourly', 0))
    
    print()
    print(colors.header("Available Instance Types:"))
    print("=" * 90)
    
    all_types = []
    
    # Display categories in order
    category_order = [
        'GPU Linodes',
        'Accelerated Linodes', 
        'Premium Linodes',
        'High Memory Linodes',
        'Dedicated CPU',
        'Shared CPU'
    ]
    
    for category in category_order:
        category_types = categorized[category]
        if not category_types:
            continue
            
        print()
        print(colors.bold(f"{category}:"))
        print("-" * 90)
        
        # Limit displayed items for large categories
        display_limit = len(category_types) if category in ['GPU Linodes', 'Accelerated Linodes'] else 15
        
        for t in category_types[:display_limit]:
            type_id = t.get('id', 'unknown')
            default_marker = colors.default(" (default)") if type_id == default else ""
            idx = len(all_types) + 1
            all_types.append(t)
            price = t.get('price', {}).get('hourly', 0)
            memory = t.get('memory', 0)
            vcpus = t.get('vcpus', 0)
            disk = t.get('disk', 0)
            gpus = t.get('gpus', 0)
            
            # Show GPU count for GPU instances
            gpu_info = colors.info(f"  {gpus} GPUs") if gpus > 0 else ""
            
            print(f"{idx:3}. {colors.value(type_id):30} {colors.info(f'${price:7.2f}/hr')}  "
                  f"{memory:6}MB RAM  {vcpus:2} vCPUs  {disk:8}MB{gpu_info}{default_marker}")
        
        if len(category_types) > display_limit:
            print(colors.dim(f"     ... and {len(category_types) - display_limit} more"))
    
    print("=" * 90)
    
    # Get user selection
    while True:
        prompt = f"\nSelect instance type [1-{len(all_types)}] (Enter for default: {colors.default(default)}): "
        choice = input_func(prompt).strip()
        
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


def initialize_project(
    template,
    directory: Path,
    region: str,
    instance_type: str,
    deploy_data: Dict | None = None
) -> None:
    """Core initialization logic - write deploy.yml, .env.example, README.md.
    
    Args:
        template: Template instance
        directory: Project directory
        region: Selected region ID
        instance_type: Selected instance type ID
        deploy_data: Optional deploy data (defaults to template.data)
    """
    # Use template data if no deploy_data provided
    if deploy_data is None:
        deploy_data = template.data.copy()
    
    # Ensure directory exists
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    
    # Update deploy data with selections
    if region:
        deploy_data.setdefault("deploy", {}).setdefault("linode", {})["region_default"] = region
    if instance_type:
        deploy_data.setdefault("deploy", {}).setdefault("linode", {})["type_default"] = instance_type
    
    # Files to create
    deploy_yml_path = directory / "deploy.yml"
    env_example_path = directory / ".env.example"
    readme_path = directory / "README.md"
    
    # Check for existing files
    if deploy_yml_path.exists():
        raise FileExistsError(f"{deploy_yml_path} already exists")
    if env_example_path.exists():
        raise FileExistsError(f"{env_example_path} already exists")
    
    # Ensure parent directories exist
    deploy_yml_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write deploy.yml
    deploy_yml_path.write_text(
        yaml.safe_dump(deploy_data, sort_keys=False),
        encoding="utf-8",
    )
    
    # Write .env.example
    env_lines = generate_env_example(template)
    env_example_path.write_text(
        "\n".join(env_lines) + ("\n" if env_lines else ""),
        encoding="utf-8"
    )
    
    # Write README.md (only if it doesn't exist)
    if not readme_path.exists():
        readme_content = generate_readme(template)
        readme_path.write_text(readme_content, encoding="utf-8")
