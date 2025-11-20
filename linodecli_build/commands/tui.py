"""TUI command registration for linode-cli build."""

import os


def register(subparsers, config):
    """
    Register TUI commands.
    
    Args:
        subparsers: Argparse subparsers object
        config: Configuration dictionary
    """
    parser = subparsers.add_parser(
        "tui",
        help="Launch interactive TUI (Terminal User Interface). Run without arguments for dashboard."
    )
    
    # Create subcommands for tui
    tui_subparsers = parser.add_subparsers(
        dest="tui_command",
        help="TUI command to run"
    )
    
    # tui deploy - Monitor a deployment in progress
    deploy_parser = tui_subparsers.add_parser(
        "deploy",
        help="Monitor deployment progress in real-time"
    )
    deploy_parser.add_argument(
        "--directory",
        help="Project directory (defaults to current directory)",
        default=os.getcwd()
    )
    deploy_parser.add_argument(
        "--instance-id",
        type=int,
        help="Linode instance ID (optional, will load from state)"
    )
    
    # tui status - View status of existing deployment
    status_parser = tui_subparsers.add_parser(
        "status",
        help="View live status of deployed application"
    )
    status_parser.add_argument(
        "--app",
        help="Application name"
    )
    status_parser.add_argument(
        "--env",
        help="Environment (e.g., production, staging)",
        default="production"
    )
    status_parser.add_argument(
        "--directory",
        help="Project directory (defaults to current directory)",
        default=os.getcwd()
    )
    status_parser.add_argument(
        "--instance-id",
        type=int,
        help="Linode instance ID (optional, will load from state)"
    )
    
    # Set the command handler
    parser.set_defaults(func=lambda args: _cmd_tui(args, config))


def _cmd_tui(args, config):
    """
    Execute TUI command.
    
    Args:
        args: Parsed command-line arguments
        config: Configuration dictionary
    """
    # Import here to avoid loading Textual unless needed
    from ..tui.app import run_tui
    
    # Check if tui_command is specified, default to dashboard
    tui_command = getattr(args, 'tui_command', None)
    
    # Get the Linode client from the PluginContext
    client = config.client
    
    if tui_command is None:
        # Default to dashboard view
        print("Launching TUI Dashboard...")
        run_tui("dashboard", client, config, directory=os.getcwd())
        return
    
    # Prepare kwargs for TUI
    kwargs = {}
    
    if tui_command == "deploy":
        kwargs["directory"] = args.directory
        if hasattr(args, 'instance_id') and args.instance_id:
            kwargs["instance_id"] = args.instance_id
        
        # Run deploy monitor
        run_tui("deploy", client, config, **kwargs)
    
    elif tui_command == "status":
        kwargs["directory"] = args.directory
        if hasattr(args, 'app') and args.app:
            kwargs["app"] = args.app
        if hasattr(args, 'env') and args.env:
            kwargs["env"] = args.env
        if hasattr(args, 'instance_id') and args.instance_id:
            kwargs["instance_id"] = args.instance_id
        
        # Run status view
        run_tui("status", client, config, **kwargs)
    
    else:
        print(f"Unknown TUI command: {tui_command}")
        print("Usage: linode-cli build tui {deploy|status}")
        print("  Or run 'linode-cli build tui' for the dashboard")
