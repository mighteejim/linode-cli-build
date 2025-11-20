"""Deployment monitoring screen with live progress tracking."""

import time
import asyncio
from textual.screen import Screen
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Header, Footer, Static
from textual.binding import Binding
from rich.text import Text

from ..widgets import DeploymentProgress, InstancePanel, LogViewer
from ..api import LinodeAPIClient
from ..utils import format_elapsed_time


class DeployMonitorScreen(Screen):
    """Screen for monitoring deployment progress in real-time."""
    
    BINDINGS = [
        Binding("escape", "quit", "Cancel"),
        Binding("ctrl+c", "quit", "Stop Monitoring"),
    ]
    
    CSS = """
    DeployMonitorScreen {
        background: $surface;
    }
    
    #header-info {
        height: 3;
        background: $primary;
        padding: 1;
    }
    
    #progress-container {
        height: auto;
        padding: 1;
    }
    
    #instance-container {
        height: auto;
        padding: 1;
    }
    
    #logs-container {
        height: 15;
        padding: 1;
    }
    
    #footer-info {
        height: 3;
        background: $panel;
        padding: 1;
    }
    """
    
    def __init__(self, api_client: LinodeAPIClient, instance_id: int = None, app_name: str = "deployment", directory: str = None, config = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_client = api_client
        self.instance_id = instance_id
        self.app_name = app_name
        self.directory = directory
        self.config = config
        self.start_time = time.time()
        self.is_monitoring = True
        self.update_task = None
        self.is_deploying = False
    
    def compose(self):
        """Compose the deployment monitor screen."""
        yield Header(show_clock=True)
        
        # Header info
        yield Static(
            f"Deploying: {self.app_name}",
            id="header-info"
        )
        
        # Progress section
        with Container(id="progress-container"):
            yield DeploymentProgress()
        
        # Instance info section
        with Container(id="instance-container"):
            yield InstancePanel()
        
        # Logs section
        with Container(id="logs-container"):
            yield LogViewer(title="Cloud-Init Output")
        
        # Footer info
        yield Static(
            "Press Ctrl+C to stop monitoring (deployment continues)",
            id="footer-info"
        )
        
        yield Footer()
    
    async def on_mount(self):
        """Start monitoring or deploying when screen is mounted."""
        # Check if we need to start a deployment
        if not self.instance_id:
            # No instance ID means we need to start a new deployment
            await self.start_deployment()
        else:
            # We have an instance ID, just monitor it
            self.update_task = self.set_interval(2.0, self.update_deployment_status)
            # Initial update
            await self.update_deployment_status()
    
    async def start_deployment(self):
        """Start a new deployment."""
        from pathlib import Path
        import yaml
        
        # Check for deploy.yml
        deploy_file = Path(self.directory or ".") / "deploy.yml"
        if not deploy_file.exists():
            from .error import ErrorScreen
            self.app.push_screen(
                ErrorScreen(
                    title="No deploy.yml Found",
                    message=f"No deploy.yml found in {self.directory or 'current directory'}",
                    suggestion="Run 'linode-cli build init <template>' first to initialize a deployment."
                )
            )
            return
        
        # Show informative error screen
        from .error import ErrorScreen
        self.app.push_screen(
            ErrorScreen(
                title="Use 'tui status' to Monitor Deployments",
                message=(
                    "The TUI monitors existing deployments.\n\n"
                    "Use 'linode-cli build tui status' after deployment completes."
                ),
                suggestion=(
                    "Current workflow:\n\n"
                    "1. Deploy: linode-cli build deploy\n"
                    "2. Monitor: linode-cli build tui status\n\n"
                    "Or view all: linode-cli build tui (dashboard)"
                )
            )
        )
    
    async def update_deployment_status(self):
        """Update deployment status from API."""
        if not self.is_monitoring:
            return
        
        try:
            # Fetch instance data
            instance = await self.api_client.get_instance(self.instance_id)
            
            if instance:
                # Update instance panel
                instance_panel = self.query_one(InstancePanel)
                instance_panel.instance_data = instance
                
                # Update progress based on instance status
                progress = self.query_one(DeploymentProgress)
                status = instance.get("status", "")
                
                # Stage progression logic
                if status == "provisioning":
                    progress.set_stage_complete(0, "00:15")  # Created
                    progress.set_stage_active(1)  # Cloud-init
                elif status == "booting":
                    progress.set_stage_complete(0, "00:15")
                    progress.set_stage_complete(1, "00:30")
                    progress.set_stage_active(2)  # Installing
                elif status == "running":
                    # Mark all as complete
                    elapsed = format_elapsed_time(self.start_time)
                    progress.set_stage_complete(0, "00:15")
                    progress.set_stage_complete(1, "00:30")
                    progress.set_stage_complete(2, "02:00")
                    progress.set_stage_complete(3, "02:15")
                    progress.set_stage_active(4)  # Health check
                    
                    # Check if we should transition to status view
                    # For now, just mark health check as complete after a delay
                    await asyncio.sleep(5)
                    progress.set_stage_complete(4, elapsed)
                
                # Update header with elapsed time
                header_info = self.query_one("#header-info", Static)
                elapsed = format_elapsed_time(self.start_time)
                header_info.update(
                    f"Deploying: {self.app_name}    Elapsed: {elapsed}"
                )
                
                # Fetch and display logs (placeholder for now)
                logs = await self.api_client.get_instance_logs(self.instance_id)
                if logs:
                    log_viewer = self.query_one(LogViewer)
                    log_viewer.logs = logs.split('\n')[-20:]  # Last 20 lines
        
        except Exception as e:
            self.notify(f"Error updating status: {e}", severity="error")
    
    def action_quit(self):
        """Handle quit action."""
        self.is_monitoring = False
        if self.update_task:
            self.update_task.stop()
        self.app.exit()
    
    async def on_unmount(self):
        """Clean up when screen is unmounted."""
        self.is_monitoring = False
        if self.update_task:
            self.update_task.stop()
