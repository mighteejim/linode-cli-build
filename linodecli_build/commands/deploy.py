"""Implementation for `linode-cli build deploy`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..core import colors
from ..core import deploy_operations


def register(subparsers: argparse._SubParsersAction, config) -> None:
    parser = subparsers.add_parser("deploy", help="Deploy current project to Linode")
    parser.add_argument("--region", help="Override region for the Linode")
    parser.add_argument("--linode-type", help="Override Linode type/plan")
    parser.add_argument("--env-file", help="Override env file path")
    parser.add_argument(
        "--image",
        help="Override the Linode disk image (e.g., linode/ubuntu24.04)",
    )
    parser.add_argument(
        "--container-image",
        help="Override the container image defined by the template",
    )
    parser.add_argument("--app-name", help="Override app name for tagging")
    parser.add_argument("--env", dest="env_name", help="Override environment name")
    parser.add_argument("--root-pass", help="Root password to use for the Linode. If omitted, a secure password is generated and saved locally.")
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait for Linode to reach running state and perform health check",
    )
    parser.set_defaults(func=lambda args: _cmd_deploy(args, config))


def _cmd_deploy(args, config) -> None:
    """Deploy command - now using core deploy_operations."""
    
    # Build overrides dict from CLI args
    overrides = {}
    if args.region:
        overrides["region"] = args.region
    if args.linode_type:
        overrides["linode_type"] = args.linode_type
    if args.env_file:
        overrides["env_file"] = args.env_file
    if args.image:
        overrides["image"] = args.image
    if args.container_image:
        overrides["container_image"] = args.container_image
    if args.app_name:
        overrides["app_name"] = args.app_name
    if args.env_name:
        overrides["env_name"] = args.env_name
    if args.root_pass:
        overrides["root_pass"] = args.root_pass
    
    # Progress callback for CLI output
    def print_progress(msg: str, severity: str = "info"):
        if severity == "success":
            print(colors.success(msg))
        elif severity == "error":
            print(colors.error(msg))
        elif severity == "warning":
            print(colors.warning(msg))
        else:
            print(msg)
    
    try:
        # Use core deploy function
        result = deploy_operations.deploy_project(
            config=config,
            directory=Path.cwd(),
            overrides=overrides,
            wait=args.wait,
            progress_callback=print_progress
        )
        
        # Print summary
        print("")
        print(colors.dim(f"   App: {result['app_name']}, Env: {result['env_name']}"))
        print("")
        print(f"Linode ID: {colors.value(result['instance_id'])}")
        print(f"IPv4:      {colors.highlight(result['ipv4'])}")
        print(f"Hostname:  {colors.highlight(result['hostname'])}")
        if result.get('password_file'):
            print(f"Root password saved to: {colors.value(result['password_file'])}")
            print(f"SSH helper created: {colors.success('./connect.sh')} (run {colors.bold('./connect.sh')} to connect)")
        
        # Print next steps guidance
        _print_next_steps_from_result(result)
        
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("Run 'linode-cli build init <template>' first to initialize a deployment.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _print_next_steps_from_result(result: dict) -> None:
    """Print next steps guidance from deployment result.
    
    This loads the deploy.yml to get the guidance section.
    """
    try:
        import yaml
        deploy_file = Path.cwd() / "deploy.yml"
        if deploy_file.exists():
            with open(deploy_file, 'r') as f:
                data = yaml.safe_load(f)
                guidance = data.get("guidance") or {}
                
                if not guidance:
                    return

                summary = guidance.get("summary")
                examples = guidance.get("examples", [])
                print("")
                print(colors.header("📋 Next Steps:"))
                if summary:
                    print(colors.info(summary.strip()))
                    print("")

                hostname = result['hostname']
                for example in examples:
                    desc = example.get("description")
                    command = example.get("command", "").replace("{host}", hostname)
                    if desc:
                        print(f"  {colors.bold('•')} {desc}:")
                    if command:
                        print(f"    {colors.highlight(command.strip())}")
                    print("")
    except Exception:
        pass  # Silently ignore if we can't load guidance
