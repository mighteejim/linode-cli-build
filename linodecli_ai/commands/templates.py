"""Implementation of `linode-cli ai templates` commands."""

from __future__ import annotations

import argparse
import sys
import textwrap
from typing import Sequence

from ..core import templates as template_core
from ..core.registry import TemplateRegistryClient, RegistryConfig, RegistryNetworkError


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
