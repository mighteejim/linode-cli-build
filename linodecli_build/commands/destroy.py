"""Implementation for `linode-cli build destroy`."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from ..core import registry


def register(subparsers: argparse._SubParsersAction, config) -> None:
    parser = subparsers.add_parser("destroy", help="Destroy deployments")
    parser.add_argument("--deployment-id", help="Specific deployment ID to destroy")
    parser.add_argument("--app", help="Filter by app name")
    parser.add_argument("--env", help="Filter by environment")
    parser.add_argument("--force", "-f", action="store_true", help="Skip confirmation prompt")
    parser.set_defaults(func=lambda args: _cmd_destroy(args, config))


def _cmd_destroy(args, config) -> None:
    # If no app provided, try to get from deploy.yml in current directory
    app_name = args.app
    env_name = args.env or "default"
    
    if not app_name:
        deploy_file = Path.cwd() / "deploy.yml"
        if deploy_file.exists():
            try:
                with open(deploy_file, 'r') as f:
                    data = yaml.safe_load(f)
                    if isinstance(data, dict):
                        app_name = data.get("name")
            except Exception:
                pass
    
    deployments = registry.filter_deployments(app_name=app_name, env=env_name)
    if args.deployment_id:
        deployments = [d for d in deployments if d.get("deployment_id") == args.deployment_id]
    if not deployments:
        print("No deployments matched the provided filters.")
        return

    if len(deployments) > 1 and not (args.app or args.env or args.deployment_id):
        raise RuntimeError(
            "Multiple deployments exist. Please specify --app/--env/--deployment-id to narrow selection."
        )

    print("The following deployments will be destroyed:")
    for dep in deployments:
        print(
            f"- {dep['app_name']} ({dep['env']}), linode_id={dep.get('linode_id')} in {dep.get('region')}"
        )

    if not args.force and not _confirm():
        print("Aborted.")
        return

    client = config.client
    for dep in deployments:
        linode_id = dep.get("linode_id")
        if linode_id:
            print(f"Deleting Linode {linode_id}...")
            try:
                status, response = client.call_operation('linodes', 'delete', [str(linode_id)])
                if status not in [200, 204]:
                    print(f"Warning: failed to delete Linode {linode_id}: {response}")
            except Exception as exc:
                print(f"Warning: failed to delete Linode {linode_id}: {exc}")
        registry.remove_deployment(dep["deployment_id"])
        print(f"Removed deployment {dep['deployment_id']}")

    print("Destroy complete.")


def _confirm() -> bool:
    response = input("Type 'delete' to confirm: ").strip().lower()
    return response == "delete"
