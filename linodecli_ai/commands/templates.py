"""Implementation of `linode-cli ai templates` commands."""

from __future__ import annotations

import argparse
import sys
import textwrap
from pathlib import Path
from typing import Sequence, Dict, Any

import yaml

from ..core import templates as template_core
from ..core.template_registry import TemplateRegistryClient, RegistryConfig, RegistryNetworkError
from . import scaffold as scaffold_cmd


def register(subparsers: argparse._SubParsersAction, _config) -> None:
    parser = subparsers.add_parser("templates", help="List and inspect AI templates")
    parser.set_defaults(func=lambda args: parser.print_help())
    templates_subparsers = parser.add_subparsers(dest="templates_cmd")

    list_parser = templates_subparsers.add_parser("list", help="List available templates")
    list_parser.add_argument("--remote", action="store_true", help="Show remote templates only")
    list_parser.add_argument("--cached", action="store_true", help="Show cached templates only")
    list_parser.set_defaults(func=_cmd_list)

    show_parser = templates_subparsers.add_parser("show", help="Show template details")
    show_parser.add_argument("name", help="Template name")
    show_parser.set_defaults(func=_cmd_show)

    update_parser = templates_subparsers.add_parser("update", help="Update templates from remote registry")
    update_parser.add_argument("--force", action="store_true", help="Force update even if cache is fresh")
    update_parser.set_defaults(func=_cmd_update)

    install_parser = templates_subparsers.add_parser("install", help="Download a specific template")
    install_parser.add_argument("name", help="Template name")
    install_parser.add_argument("--version", help="Specific version to download (default: latest)")
    install_parser.set_defaults(func=_cmd_install)

    remove_parser = templates_subparsers.add_parser("remove", help="Remove a cached template")
    remove_parser.add_argument("name", help="Template name")
    remove_parser.set_defaults(func=_cmd_remove)

    clear_parser = templates_subparsers.add_parser("clear-cache", help="Clear all cached templates")
    clear_parser.set_defaults(func=_cmd_clear_cache)

    # Add scaffold subcommand
    scaffold_cmd.register(templates_subparsers, _config)

    # Add validate subcommand
    validate_parser = templates_subparsers.add_parser("validate", help="Validate a template")
    validate_parser.add_argument("path", help="Path to template directory or template.yml")
    validate_parser.set_defaults(func=_cmd_validate)

    # Add test subcommand
    test_parser = templates_subparsers.add_parser("test", help="Test a template")
    test_parser.add_argument("name", help="Template name or path")
    test_parser.add_argument("--dry-run", action="store_true", help="Show cloud-init without deploying")
    test_parser.add_argument("--no-cleanup", action="store_true", help="Don't destroy after testing")
    test_parser.set_defaults(func=_cmd_test)


def _cmd_list(args):
    rows = []
    
    # Show bundled templates unless --remote is specified
    if not args.remote:
        records = template_core.list_template_records()
        for record in records:
            try:
                template = template_core.load_template(record.name)
                source = "bundled" if not args.cached else None
                if source:
                    rows.append(
                        (
                            template.name,
                            template.version,
                            source,
                            template.description.strip().replace("\n", " "),
                        )
                    )
            except Exception:
                continue
    
    # Show remote/cached templates unless --bundled is specified
    if not hasattr(args, 'bundled') or not args.bundled:
        try:
            client = TemplateRegistryClient(RegistryConfig.load_from_file())
            
            if args.cached:
                # Show only cached templates
                cached = client.list_cached_templates()
                for entry in cached:
                    rows.append(
                        (
                            entry["name"],
                            entry["version"],
                            "cached",
                            "(locally cached)",
                        )
                    )
            elif args.remote:
                # Show only remote templates
                registry = client.fetch_index()
                for entry in registry.templates:
                    verified = "✓" if entry.verified else ""
                    rows.append(
                        (
                            entry.name,
                            entry.version,
                            f"remote{verified}",
                            entry.description.strip().replace("\n", " "),
                        )
                    )
            else:
                # Show both: merge remote with cached status
                registry = client.fetch_index()
                cached_names = {t["name"]: t["version"] for t in client.list_cached_templates()}
                
                for entry in registry.templates:
                    if entry.name in cached_names:
                        source = f"cached (v{cached_names[entry.name]})"
                    else:
                        source = "remote"
                    
                    if entry.verified:
                        source += " ✓"
                    
                    rows.append(
                        (
                            entry.name,
                            entry.version,
                            source,
                            entry.description.strip().replace("\n", " "),
                        )
                    )
        except RegistryNetworkError:
            print("Warning: Could not fetch remote templates (network error)", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Error fetching remote templates: {e}", file=sys.stderr)

    if not rows:
        print("No templates found.")
        return

    _print_table(("NAME", "VERSION", "SOURCE", "DESCRIPTION"), rows)


def _cmd_show(args):
    template = template_core.load_template(args.name)
    linode_cfg = template.data.get("deploy", {}).get("linode", {})
    container = linode_cfg.get("container", {})
    env_cfg = template.data.get("env", {})

    print(f"Name:        {template.name}")
    print(f"Display:     {template.display_name}")
    print(f"Version:     {template.version}")
    print(f"Target:      {template.data.get('deploy', {}).get('target', 'linode')}")
    print(f"Region:      {linode_cfg.get('region_default')}")
    print(f"Linode type: {linode_cfg.get('type_default')}")
    print(f"OS image:    {linode_cfg.get('image')}")
    print("")
    print("Description:")
    print(textwrap.fill(template.description, width=80))
    print("")
    print("Container:")
    print(f"  Image:           {container.get('image')}")
    print(f"  Ports:           {container.get('external_port')} -> {container.get('internal_port')}")
    if "post_start_script" in container:
        print("  Post-start hook: provided")
    if container.get("env"):
        print("  Default Env:")
        for key, value in container["env"].items():
            print(f"    - {key}={value}")
    print("")
    print("Env requirements:")
    required = env_cfg.get("required", [])
    optional = env_cfg.get("optional", [])
    if required:
        print("  Required:")
        for item in required:
            print(f"    - {item.get('name')}: {item.get('description', '')}")
    else:
        print("  Required: none")
    if optional:
        print("  Optional:")
        for item in optional:
            print(f"    - {item.get('name')}: {item.get('description', '')}")
    else:
        print("  Optional: none")


def _cmd_update(args):
    """Update templates from remote registry."""
    print("Updating templates from registry...")
    
    try:
        client = TemplateRegistryClient(RegistryConfig.load_from_file())
        updated_count = client.update_templates(force=args.force)
        
        if updated_count > 0:
            print(f"✓ Updated {updated_count} template(s)")
        else:
            print("✓ All templates are up to date")
    
    except RegistryNetworkError as e:
        print(f"Error: Could not connect to template registry: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error updating templates: {e}", file=sys.stderr)
        sys.exit(1)


def _cmd_install(args):
    """Download a specific template."""
    template_name = args.name
    version = getattr(args, 'version', None)
    
    print(f"Downloading template '{template_name}'...")
    
    try:
        client = TemplateRegistryClient(RegistryConfig.load_from_file())
        template_dir = client.download_template(template_name, version=version)
        
        print(f"✓ Template downloaded to {template_dir}")
        print(f"\nTo use this template, run:")
        print(f"  linode-cli ai init {template_name}")
    
    except RegistryNetworkError as e:
        print(f"Error: Could not connect to template registry: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error downloading template: {e}", file=sys.stderr)
        sys.exit(1)


def _cmd_remove(args):
    """Remove a cached template."""
    template_name = args.name
    
    try:
        client = TemplateRegistryClient(RegistryConfig.load_from_file())
        client.remove_template(template_name)
        
        print(f"✓ Removed template '{template_name}' from cache")
    
    except Exception as e:
        print(f"Error removing template: {e}", file=sys.stderr)
        sys.exit(1)


def _cmd_clear_cache(_args):
    """Clear all cached templates."""
    try:
        client = TemplateRegistryClient(RegistryConfig.load_from_file())
        client.clear_cache()
        
        print("✓ Cleared template cache")
    
    except Exception as e:
        print(f"Error clearing cache: {e}", file=sys.stderr)
        sys.exit(1)


def _print_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> None:
    widths = [len(h) for h in headers]
    for row in rows:
        widths = [max(widths[idx], len(str(value))) for idx, value in enumerate(row)]
    header_line = "  ".join(h.ljust(widths[idx]) for idx, h in enumerate(headers))
    print(header_line)
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(str(value).ljust(widths[idx]) for idx, value in enumerate(row)))


def _cmd_validate(args) -> None:
    """Validate a template for correctness."""
    path = Path(args.path)
    
    # Determine template file path
    if path.is_dir():
        template_file = path / "template.yml"
    elif path.is_file() and path.name in ["template.yml", "template-stub.yml"]:
        template_file = path
    else:
        print(f"Error: '{path}' is not a template directory or .yml file", file=sys.stderr)
        sys.exit(1)
    
    if not template_file.exists():
        print(f"Error: Template file not found: {template_file}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Validating template: {template_file}\n")
    
    # Load and parse YAML
    try:
        with open(template_file, 'r') as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"✗ YAML parsing error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error reading file: {e}", file=sys.stderr)
        sys.exit(1)
    
    if not isinstance(data, dict):
        print("✗ Template must be a YAML object/dictionary", file=sys.stderr)
        sys.exit(1)
    
    # Validation checks
    errors = []
    warnings = []
    
    # Required fields
    required_fields = {
        "name": str,
        "display_name": str,
        "version": str,
        "description": str,
        "deploy": dict,
    }
    
    for field, expected_type in required_fields.items():
        if field not in data:
            errors.append(f"Missing required field: {field}")
        elif not isinstance(data[field], expected_type):
            errors.append(f"Field '{field}' must be {expected_type.__name__}")
    
    # Validate deploy section
    if "deploy" in data and isinstance(data["deploy"], dict):
        deploy = data["deploy"]
        
        if deploy.get("target") != "linode":
            errors.append("deploy.target must be 'linode'")
        
        if "linode" not in deploy:
            errors.append("Missing deploy.linode section")
        else:
            linode = deploy["linode"]
            
            # Required Linode fields
            for field in ["image", "region_default", "type_default"]:
                if field not in linode:
                    errors.append(f"Missing deploy.linode.{field}")
            
            # Validate container section for Docker runtime
            capabilities = data.get("capabilities", {})
            runtime = capabilities.get("runtime", "docker")
            
            if runtime == "docker":
                if "container" not in linode:
                    errors.append("Missing deploy.linode.container section for Docker runtime")
                else:
                    container = linode["container"]
                    
                    # Required container fields
                    for field in ["image", "internal_port", "external_port"]:
                        if field not in container:
                            errors.append(f"Missing deploy.linode.container.{field}")
                    
                    # Recommend health check
                    if "health" not in container:
                        warnings.append("No health check defined (recommended)")
                    else:
                        health = container["health"]
                        if health.get("type") == "http" and "path" not in health:
                            errors.append("HTTP health check missing 'path' field")
                        if "port" not in health:
                            warnings.append("Health check missing 'port' field")
    
    # Validate capabilities
    if "capabilities" in data:
        cap = data["capabilities"]
        
        if "runtime" in cap:
            valid_runtimes = ["docker", "native", "k3s"]
            if cap["runtime"] not in valid_runtimes:
                errors.append(f"Invalid runtime: {cap['runtime']} (must be one of {valid_runtimes})")
        
        if "features" in cap:
            if not isinstance(cap["features"], list):
                errors.append("capabilities.features must be a list")
        
        if "packages" in cap:
            if not isinstance(cap["packages"], list):
                errors.append("capabilities.packages must be a list")
    
    # Validate env section
    if "env" in data:
        env = data["env"]
        
        for section in ["required", "optional"]:
            if section in env:
                if not isinstance(env[section], list):
                    errors.append(f"env.{section} must be a list")
                else:
                    for idx, item in enumerate(env[section]):
                        if not isinstance(item, dict):
                            errors.append(f"env.{section}[{idx}] must be an object")
                        elif "name" not in item:
                            errors.append(f"env.{section}[{idx}] missing 'name' field")
    
    # Version format
    if "version" in data:
        version = str(data["version"])
        parts = version.split(".")
        if len(parts) != 3 or not all(p.isdigit() for p in parts):
            warnings.append(f"Version '{version}' should follow semantic versioning (X.Y.Z)")
    
    # GPU recommendations
    if "deploy" in data and isinstance(data["deploy"], dict):
        linode = data["deploy"].get("linode", {})
        container = linode.get("container", {})
        capabilities_cfg = data.get("capabilities", {})
        
        # Check for legacy requires_gpu
        if container.get("requires_gpu"):
            warnings.append(
                "Using deprecated 'requires_gpu: true'. "
                "Consider using capabilities.features: [gpu-nvidia]"
            )
        
        # Check GPU instance type
        instance_type = linode.get("type_default", "")
        has_gpu_cap = "gpu-nvidia" in capabilities_cfg.get("features", [])
        has_gpu_legacy = container.get("requires_gpu", False)
        
        if (has_gpu_cap or has_gpu_legacy) and not instance_type.startswith("g6-"):
            warnings.append(
                f"GPU capability enabled but instance type '{instance_type}' "
                "doesn't appear to be a GPU instance (should start with 'g6-')"
            )
        
        # Check base image for GPU
        base_image = linode.get("image", "")
        if (has_gpu_cap or has_gpu_legacy) and "ubuntu22.04" not in base_image.lower():
            warnings.append(
                f"GPU instances work best with ubuntu22.04, but using '{base_image}'"
            )
    
    # Print results
    if errors:
        print("Validation FAILED:\n")
        for error in errors:
            print(f"  ✗ {error}")
        print()
    else:
        print("✓ All required fields present")
        print("✓ Schema validation passed")
        print()
    
    if warnings:
        print("Warnings:\n")
        for warning in warnings:
            print(f"  ⚠ {warning}")
        print()
    
    if errors:
        sys.exit(1)
    else:
        if not warnings:
            print("✓ Template validation successful!")
        else:
            print("✓ Template is valid (with warnings)")


def _cmd_test(args) -> None:
    """Test a template by deploying or showing cloud-init."""
    print(f"Testing template: {args.name}\n")
    
    if args.dry_run:
        _test_dry_run(args)
    else:
        _test_deploy(args)


def _test_dry_run(args) -> None:
    """Show generated cloud-init without deploying."""
    from ..core import cloud_init, capabilities
    
    # Load template
    path = Path(args.name)
    if path.is_dir():
        template_file = path / "template.yml"
    elif path.is_file():
        template_file = path
    else:
        # Try loading as template name
        try:
            template = template_core.load_template(args.name)
            print(f"Loaded bundled template: {template.name} v{template.version}\n")
            _show_dry_run_for_template(template)
            return
        except Exception as e:
            print(f"Error: Could not load template '{args.name}': {e}", file=sys.stderr)
            sys.exit(1)
    
    # Load from file
    if not template_file.exists():
        print(f"Error: Template file not found: {template_file}", file=sys.stderr)
        sys.exit(1)
    
    try:
        with open(template_file, 'r') as f:
            data = yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading template: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Create template object
    template = template_core.Template(
        name=data.get("name", "test"),
        display_name=data.get("display_name", "Test"),
        version=data.get("version", "0.0.0"),
        description=data.get("description", ""),
        data=data,
    )
    
    _show_dry_run_for_template(template)


def _show_dry_run_for_template(template: template_core.Template) -> None:
    """Generate and display cloud-init for a template."""
    from ..core import cloud_init, capabilities
    
    linode_cfg = template.data.get("deploy", {}).get("linode", {})
    container_cfg = linode_cfg.get("container", {})
    
    # Build minimal config
    container_image = container_cfg.get("image", "placeholder:latest")
    internal_port = container_cfg.get("internal_port", 8000)
    external_port = container_cfg.get("external_port", 80)
    requires_gpu = container_cfg.get("requires_gpu", False)
    
    # Create capability manager
    capability_manager = capabilities.create_capability_manager(template.data)
    
    # Get custom setup
    setup_cfg = template.data.get("setup", {})
    custom_setup_script = setup_cfg.get("script")
    custom_files = []
    for file_spec in setup_cfg.get("files", []):
        custom_files.append({
            "path": file_spec.get("path"),
            "permissions": file_spec.get("permissions", "0644"),
            "owner": file_spec.get("owner", "root:root"),
            "content": file_spec.get("content", ""),
        })
    
    # Create test env vars
    test_env = {
        "BUILD_AI_APP_NAME": template.name,
        "BUILD_AI_ENV": "test",
    }
    
    config_obj = cloud_init.CloudInitConfig(
        container_image=container_image,
        internal_port=internal_port,
        external_port=external_port,
        env_vars=test_env,
        post_start_script=container_cfg.get("post_start_script"),
        command=container_cfg.get("command"),
        requires_gpu=requires_gpu,
        capability_manager=capability_manager,
        custom_setup_script=custom_setup_script,
        custom_files=custom_files,
    )
    
    user_data = cloud_init.generate_cloud_init(config_obj)
    
    print("Generated cloud-init configuration:\n")
    print("=" * 80)
    print(user_data)
    print("=" * 80)
    print()
    
    # Show summary
    print("Summary:")
    print(f"  Template: {template.display_name} v{template.version}")
    print(f"  Container: {container_image}")
    print(f"  Ports: {external_port} -> {internal_port}")
    print(f"  GPU: {'Yes' if requires_gpu or capability_manager else 'No'}")
    if capability_manager:
        print(f"  Capabilities: {len(capability_manager.capabilities)} configured")


def _test_deploy(args) -> None:
    """Actually deploy and test the template."""
    print("Deploy testing not yet implemented.")
    print("Use --dry-run to see generated cloud-init.")
    print()
    print("To test deployment manually:")
    print(f"  1. linode-cli ai init {args.name}")
    print(f"  2. cd {args.name}")
    print("  3. Configure .env file")
    print("  4. linode-cli ai deploy --wait")
    print("  5. linode-cli ai status")
    print()
    if not args.no_cleanup:
        print("  6. linode-cli ai destroy (when done)")
