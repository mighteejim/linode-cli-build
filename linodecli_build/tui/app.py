"""Main TUI application for linode-cli build."""

import os
from pathlib import Path
from textual.app import App
from textual.binding import Binding

from .screens import DashboardScreen, DeployMonitorScreen, StatusViewScreen, ErrorScreen
from .api import LinodeAPIClient
from .utils import load_deployment_state


class BuildTUI(App):
    """Main TUI application for monitoring Linode deployments."""
    
    BINDINGS = [
        Binding("escape", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("?", "help", "Help"),
        Binding("ctrl+c", "quit", "Quit"),
    ]
    
    # CSS file path
    CSS_PATH = Path(__file__).parent / "styles.tcss"
    
    def __init__(
        self,
        mode: str,
        client,
        config: dict,
        directory: str = None,
        app: str = None,
        env: str = None,
        instance_id: int = None,
        *args,
        **kwargs
    ):
        """
        Initialize TUI application.
        
        Args:
            mode: Mode to run in ('deploy' or 'status')
            client: Linode CLI client
            config: Configuration dictionary
            directory: Project directory (for deploy mode)
            app: Application name (for status mode)
            env: Environment (for status mode)
            instance_id: Linode instance ID (optional, will be loaded from state)
        """
        super().__init__(*args, **kwargs)
        self.mode = mode
        self.config = config
        self.directory = directory or os.getcwd()
        self.app_name = app or "app"
        self.environment = env or "production"
        self.instance_id = instance_id
        
        # Initialize API client
        self.api_client = LinodeAPIClient(client)
        
        # Load deployment state if not provided
        if not self.instance_id:
            self._load_instance_from_state()
    
    def _load_instance_from_state(self):
        """Load instance ID using DeploymentTracker."""
        from ..core.deployment_tracker import DeploymentTracker
        from pathlib import Path
        
        tracker = DeploymentTracker(self.api_client.client)
        
        # Find deployment for current directory
        deployment = tracker.find_deployment_for_directory(Path(self.directory))
        
        if deployment:
            self.instance_id = deployment['linode_id']
            self.app_name = deployment['app_name']
            self.environment = deployment['env']
    
    def on_mount(self):
        """Called when app is mounted."""
        # Push the appropriate screen based on mode
        if self.mode == "deploy":
            # For deploy mode, we'll start the deployment from within the DeployMonitorScreen
            # Pass the instance_id if it exists (for monitoring existing deployment)
            # Otherwise, the screen will trigger a new deployment
            self.push_screen(
                DeployMonitorScreen(
                    self.api_client,
                    self.instance_id,  # May be None - screen will handle it
                    self.app_name,
                    directory=self.directory,
                    config=self.config
                )
            )
        elif self.mode == "status":
            if not self.instance_id:
                # Show error screen instead of immediately exiting
                self.push_screen(
                    ErrorScreen(
                        title="No Deployment Found",
                        message="No active deployment found in this directory.",
                        suggestion="First run: linode-cli build deploy\nOr use: linode-cli build tui (dashboard) to see all deployments"
                    )
                )
                return
            
            self.push_screen(
                StatusViewScreen(
                    self.api_client,
                    self.instance_id,
                    self.app_name,
                    self.environment
                )
            )
        elif self.mode == "dashboard":
            # Dashboard mode - show list of deployments
            self.push_screen(
                DashboardScreen(
                    self.api_client,
                    self.directory
                )
            )
        else:
            self.push_screen(
                ErrorScreen(
                    title="Invalid Mode",
                    message=f"Unknown TUI mode: {self.mode}",
                    suggestion="Valid modes: deploy, status, dashboard"
                )
            )
    
    def action_refresh(self):
        """Refresh action (delegated to active screen)."""
        screen = self.screen
        if hasattr(screen, 'action_refresh'):
            screen.action_refresh()
    
    def action_help(self):
        """Show help message."""
        help_text = """
TUI Keyboard Shortcuts:

  Esc / Ctrl+C  - Exit
  R             - Refresh
  S             - SSH (status view)
  D             - Destroy (status view)
  ?             - Show this help

Navigation:
  Use arrow keys to scroll
  Tab to switch between panels
"""
        self.notify(help_text, timeout=10)
    
    async def on_unmount(self):
        """Clean up when app is unmounted."""
        await self.api_client.close()


def run_tui(mode: str, client, config: dict, **kwargs):
    """
    Run the TUI application.
    
    Args:
        mode: Mode to run in ('deploy' or 'status')
        client: Linode CLI client
        config: Configuration dictionary
        **kwargs: Additional arguments (directory, app, env, instance_id)
    """
    app = BuildTUI(
        mode=mode,
        client=client,
        config=config,
        **kwargs
    )
    app.run()
