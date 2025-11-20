"""Implementation for `linode-cli build destroy`."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from ..core import registry
from ..core.deployment_tracker import DeploymentTracker


def register(subparsers: argparse._SubParsersAction, config) -> None:
    parser = subparsers.add_parser("destroy", help="Destroy a deployment")
    parser.add_argument("deployment_id", nargs="?", help="Deployment ID to destroy")
    parser.add_argument("--app", help="App name (if multiple deployments)")
    parser.add_argument("--env", help="Environment (if multiple deployments)")
    parser.add_argument("--force", "-f", action="store_true", help="Skip confirmation prompt")
    parser.set_defaults(func=lambda args: _cmd_destroy(args, config))


def _cmd_destroy(args, config) -> None:
    tracker = DeploymentTracker(config.client)
    
    # If deployment_id provided, use it directly
    if args.deployment_id:
        deployment = tracker.get_deployment(args.deployment_id)
        if not deployment:
            print(f"Deployment {args.deployment_id} not found.")
            return
        deployments = [deployment]
    else:
        # Auto-detect from directory or filters
        if not args.app and not args.env:
            deployment = tracker.find_deployment_for_directory(Path.cwd())
            if deployment:
                deployments = [deployment]
            else:
                print("No deployment found.")
                return
        else:
            deployments = tracker.list_deployments(app_name=args.app, env=args.env)
            if len(deployments) > 1:
                print("Multiple deployments found. Please specify deployment ID:")
                for dep in deployments:
                    print(f"  {dep['deployment_id']}: {dep['app_name']} ({dep['env']})")
                return
            elif not deployments:
                print("No deployment found.")
                return

    print("The following deployment(s) will be destroyed:")
    for dep in deployments:
        print(f"  ID: {dep['deployment_id']}")
        print(f"  App: {dep['app_name']} ({dep['env']})")
        print(f"  Linode: {dep.get('linode_id')} in {dep.get('region')}")

    if not args.force:
        confirm = input("Type 'yes' to confirm: ")
        if confirm.lower() != 'yes':
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
                else:
                    print(f"✓ Deleted deployment {dep['deployment_id']}")
                    # Also remove from old registry for backward compatibility
                    registry.remove_deployment(dep["deployment_id"])
            except Exception as exc:
                print(f"Warning: failed to delete Linode {linode_id}: {exc}")

    print("Destroy complete.")
