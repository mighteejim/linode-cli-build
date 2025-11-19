"""Implementation for `linode-cli ai templates scaffold` command."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, Any

import yaml

from ..core.llm_instructions_generator import (
    LLMInstructionsGenerator,
    generate_template_stub,
)


def register(subparsers: argparse._SubParsersAction, _config) -> None:
    """Register the scaffold subcommand."""
    parser = subparsers.add_parser(
        "scaffold",
        help="Create a new template with guided prompts"
    )
    parser.add_argument(
        "name",
        help="Template name (e.g., my-api)",
    )
    parser.add_argument(
        "--llm-assist",
        action="store_true",
        help="Generate LLM instructions instead of complete template",
    )
    parser.add_argument(
        "--output-dir",
        help="Output directory (default: current directory)",
        default=".",
    )
    parser.set_defaults(func=_cmd_scaffold)


def _cmd_scaffold(args) -> None:
    """Execute the scaffold command."""
    if args.llm_assist:
        return _scaffold_with_llm_assist(args)
    else:
        return _scaffold_interactive(args)


def _scaffold_with_llm_assist(args) -> None:
    """Scaffold with LLM assistance mode.
    
    This mode creates:
    1. A template stub with basic structure
    2. Comprehensive LLM instructions for completing the template
    """
    print(f"Creating template scaffold for '{args.name}' with LLM assistance...\n")
    
    # Gather high-level requirements from user
    user_input = _gather_user_requirements(args.name)
    
    # Create directory structure
    output_dir = Path(args.output_dir)
    template_dir = output_dir / args.name
    
    try:
        template_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        print(f"Error: Directory '{template_dir}' already exists", file=sys.stderr)
        sys.exit(1)
    
    docs_dir = template_dir / "docs"
    docs_dir.mkdir(exist_ok=True)
    
    # Generate template stub
    stub_data = generate_template_stub(user_input)
    stub_path = template_dir / "template-stub.yml"
    
    with open(stub_path, 'w') as f:
        yaml.dump(stub_data, f, default_flow_style=False, sort_keys=False)
    
    # Generate LLM instructions
    generator = LLMInstructionsGenerator()
    instructions = generator.generate(user_input, str(stub_path))
    instructions_path = template_dir / "llm-instructions.md"
    
    with open(instructions_path, 'w') as f:
        f.write(instructions)
    
    # Create README stub
    readme_path = docs_dir / "README-stub.md"
    with open(readme_path, 'w') as f:
        f.write(f"""# {stub_data['display_name']} Template

TODO: Add comprehensive documentation

## Overview

{stub_data['description']}

## Requirements

TODO: Document requirements

## Quick Start

```bash
linode-cli ai init {args.name}
cd {args.name}
# Configure .env file
linode-cli ai deploy --wait
```

## Configuration

TODO: Document environment variables and configuration options

## Usage

TODO: Add usage examples

## Troubleshooting

TODO: Add common issues and solutions
""")
    
    # Create .env.example
    env_example_path = template_dir / ".env.example"
    with open(env_example_path, 'w') as f:
        f.write("# Environment variables for this template\n\n")
        
        if stub_data.get('env', {}).get('required'):
            f.write("# Required environment variables\n")
            for var in stub_data['env']['required']:
                desc = var.get('description', '')
                if desc:
                    # Write description as comment
                    f.write(f"# {desc}\n")
                # Required vars are NOT commented out
                f.write(f"{var.get('name')}=\n")
            f.write("\n")
        
        if stub_data.get('env', {}).get('optional'):
            f.write("# Optional environment variables\n")
            for var in stub_data['env']['optional']:
                desc = var.get('description', '')
                if desc:
                    # Write description as comment
                    f.write(f"# {desc}\n")
                # Optional vars ARE commented out
                f.write(f"# {var.get('name')}=\n")
    
    # Print success message with next steps
    print(f"✓ Created {template_dir}/ directory")
    print(f"✓ Created template-stub.yml with basic structure")
    print(f"✓ Created llm-instructions.md with full context")
    print(f"✓ Created docs/README-stub.md")
    print(f"✓ Created .env.example")
    print()
    print("Next steps:")
    print()
    print("  1. Review llm-instructions.md to understand the template system")
    print()
    print("  2. Feed it to your LLM (Cursor/Claude/GPT-4) with:")
    print(f"     '@{instructions_path} complete this template'")
    print()
    print("  3. Review the generated template.yml and make adjustments")
    print()
    print("  4. Complete the README.md documentation")
    print()
    print(f"  5. Validate: linode-cli ai templates validate {template_dir}")
    print()
    print(f"  6. Test: linode-cli ai templates test {args.name} --dry-run")
    print()


def _scaffold_interactive(args) -> None:
    """Interactive scaffolding mode (traditional approach).
    
    This mode asks detailed questions and generates a complete template.
    """
    print(f"Creating template '{args.name}' interactively...\n")
    
    # Gather detailed information
    print("Answer the following questions to generate your template:")
    print()
    
    user_input = _gather_detailed_requirements(args.name)
    
    # Create directory structure
    output_dir = Path(args.output_dir)
    template_dir = output_dir / args.name
    
    try:
        template_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        print(f"Error: Directory '{template_dir}' already exists", file=sys.stderr)
        sys.exit(1)
    
    docs_dir = template_dir / "docs"
    docs_dir.mkdir(exist_ok=True)
    
    # Generate complete template
    template_data = _generate_complete_template(user_input)
    template_path = template_dir / "template.yml"
    
    with open(template_path, 'w') as f:
        yaml.dump(template_data, f, default_flow_style=False, sort_keys=False)
    
    # Generate README
    readme_path = docs_dir / "README.md"
    readme_content = _generate_readme(user_input, template_data)
    with open(readme_path, 'w') as f:
        f.write(readme_content)
    
    # Generate .env.example
    env_example_path = template_dir / ".env.example"
    with open(env_example_path, 'w') as f:
        f.write("# Environment variables\n\n")
        
        # Required variables (not commented out)
        required_vars = template_data.get('env', {}).get('required', [])
        if required_vars:
            f.write("# Required environment variables\n")
            for var in required_vars:
                desc = var.get('description', '')
                if desc:
                    f.write(f"# {desc}\n")
                f.write(f"{var['name']}=\n")
            f.write("\n")
        
        # Optional variables (commented out)
        optional_vars = template_data.get('env', {}).get('optional', [])
        if optional_vars:
            f.write("# Optional environment variables\n")
            for var in optional_vars:
                desc = var.get('description', '')
                if desc:
                    f.write(f"# {desc}\n")
                f.write(f"# {var['name']}=\n")
    
    print()
    print(f"✓ Created {template_dir}/")
    print(f"✓ Created template.yml")
    print(f"✓ Created docs/README.md")
    print(f"✓ Created .env.example")
    print()
    print("Next steps:")
    print(f"  1. Review and customize {template_path}")
    print(f"  2. Test: linode-cli ai templates test {args.name} --dry-run")
    print(f"  3. Deploy: linode-cli ai init {args.name} && cd {args.name} && linode-cli ai deploy")


def _gather_user_requirements(template_name: str) -> Dict[str, Any]:
    """Gather high-level requirements for LLM-assisted mode.
    
    Args:
        template_name: Name of the template being created
        
    Returns:
        Dictionary with user's answers
    """
    user_input = {"template_name": template_name}
    
    print("Answer a few questions to generate LLM instructions:\n")
    
    # Service description
    service_desc = input("What service do you want to deploy?\n> ").strip()
    user_input['service_description'] = service_desc or "AI service"
    
    # GPU requirement
    gpu_input = input("\nDoes it require GPU? [y/n]: ").strip().lower()
    user_input['requires_gpu'] = gpu_input in ['y', 'yes']
    
    # Dependencies
    dependencies = input("\nAny special dependencies? (e.g., CUDA, Redis, PostgreSQL)\n> ").strip()
    user_input['dependencies'] = dependencies or "None"
    
    # Container image
    print("\nContainer image:")
    print("  - Enter a Docker Hub image (e.g., 'pytorch/pytorch:latest')")
    print("  - Or 'custom' if you need a custom Dockerfile")
    container_image = input("> ").strip()
    user_input['container_image'] = container_image or "custom"
    
    # Health check
    health_path = input("\nHealth check endpoint (e.g., /health, /api/health):\n> ").strip()
    user_input['health_check_path'] = health_path or "/health"
    
    # Startup time
    startup = input("\nExpected startup time in seconds (for health check timing):\n> ").strip()
    try:
        user_input['startup_time'] = int(startup)
    except ValueError:
        user_input['startup_time'] = 60
    
    return user_input


def _gather_detailed_requirements(template_name: str) -> Dict[str, Any]:
    """Gather detailed requirements for interactive mode."""
    user_input = {"template_name": template_name}
    
    # Display name
    display = input(f"Display name [{template_name.title()}]: ").strip()
    user_input['display_name'] = display or template_name.title()
    
    # Description
    print("\nDescription (multi-line, press Ctrl+D when done):")
    desc_lines = []
    try:
        while True:
            line = input()
            desc_lines.append(line)
    except EOFError:
        pass
    user_input['description'] = '\n'.join(desc_lines) or f"{template_name} service"
    
    # Runtime
    print("\nRuntime?")
    print("  1. docker (containerized)")
    print("  2. native (no container)")
    runtime_choice = input("[1]: ").strip() or "1"
    user_input['runtime'] = 'docker' if runtime_choice == '1' else 'native'
    
    # GPU
    gpu = input("\nRequires GPU? [y/n]: ").strip().lower()
    user_input['requires_gpu'] = gpu in ['y', 'yes']
    
    # Container details (if Docker)
    if user_input['runtime'] == 'docker':
        user_input['container_image'] = input("Container image: ").strip()
        user_input['internal_port'] = int(input("Internal port [8000]: ").strip() or "8000")
        user_input['external_port'] = int(input("External port [80]: ").strip() or "80")
        user_input['health_check_path'] = input("Health check path [/health]: ").strip() or "/health"
    
    return user_input


def _generate_complete_template(user_input: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a complete template from detailed user input."""
    # This is a simplified version - could be expanded
    return generate_template_stub(user_input)


def _generate_readme(user_input: Dict[str, Any], template_data: Dict[str, Any]) -> str:
    """Generate README content."""
    name = template_data['name']
    display_name = template_data['display_name']
    description = template_data['description']
    
    return f"""# {display_name} Template

{description}

## Quick Start

```bash
linode-cli ai init {name}
cd {name}

# Configure environment variables
cp .env.example .env
# Edit .env with your settings

# Deploy
linode-cli ai deploy --wait
```

## Configuration

See `.env.example` for available environment variables.

## Usage

After deployment, check status:

```bash
linode-cli ai status
```

## Troubleshooting

### Service not starting

Check the Linode console for boot logs and cloud-init output.

### Health check failing

Give the service more time to start, especially if loading large models.
"""
