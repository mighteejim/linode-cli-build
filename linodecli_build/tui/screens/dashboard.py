"""Dashboard screen showing list of deployments."""

import os
import asyncio
from datetime import datetime
from pathlib import Path
from textual.screen import Screen
from textual.containers import Container, Vertical, ScrollableContainer, Horizontal
from textual.widgets import Header, Footer, Static, DataTable
from textual.binding import Binding
from rich.text import Text

from ..utils import load_deployment_state, format_timestamp
from ..api import LinodeAPIClient


class DashboardScreen(Screen):
    """Main dashboard screen showing all deployments."""
    
    BINDINGS = [
        Binding("escape", "quit", "Quit"),
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("enter", "view_selected", "View Status"),
        Binding("d", "destroy_selected", "Destroy"),
        Binding("?", "help", "Help"),
        Binding("ctrl+c", "quit", "Quit"),
    ]
    
    # Animation state for blinking indicators
    _blink_state = False
    
    CSS = """
    DashboardScreen {
        background: $surface;
    }
    
    #header-info {
        height: 1;
        background: $primary;
        padding: 0 1;
        layout: horizontal;
    }
    
    .header-section {
        width: 1fr;
        content-align: center middle;
    }
    
    #header-left {
        content-align: left middle;
    }
    
    #header-center {
        content-align: center middle;
    }
    
    #header-right {
        content-align: right middle;
    }
    
    #deployments-container {
        height: 1fr;
        padding: 1;
    }
    
    #deployments-panel {
        height: 1fr;
        border: solid $primary;
        background: $panel;
    }
    
    DataTable {
        height: 1fr;
        background: $panel;
    }
    
    #help-text {
        height: 3;
        padding: 0 1;
        background: $panel;
    }
    
    #footer-info {
        height: 1;
        background: $panel;
        padding: 0 1;
    }
    """
    
    def __init__(self, api_client: LinodeAPIClient, current_dir: str = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_client = api_client
        self.current_dir = current_dir or os.getcwd()
        self.deployments = []
        self._animation_timer = None
    
    def compose(self):
        """Compose the dashboard screen."""
        # Enhanced header with version, title, and date
        from ... import PLUGIN_VERSION
        
        with Horizontal(id="header-info"):
            yield Static(
                "🚀 Linode Build - Deployments",
                id="header-left",
                classes="header-section"
            )
            yield Static(
                f"build-tui (v{PLUGIN_VERSION})",
                id="header-center",
                classes="header-section"
            )
            yield Static(
                "",  # Will be updated with time in on_mount
                id="header-right",
                classes="header-section"
            )
        
        # Deployments table with border
        with Container(id="deployments-container"):
            with Container(id="deployments-panel"):
                yield DataTable()
        
        # Help text
        yield Static(
            "↑↓ Navigate  [Enter] View Status  [D] Destroy  [R] Refresh  [Q] Quit  [?] Help",
            id="help-text"
        )
        
        # Footer
        yield Static(
            f"Found {{count}} deployment(s) | {self.current_dir}",
            id="footer-info"
        )
        
        yield Footer()
    
    def on_mount(self):
        """Initialize the dashboard when mounted."""
        self.load_deployments()
        self.refresh_table()
        # Start animation timer for blinking status indicators
        self._animation_timer = self.set_interval(0.5, self._animate_status)
        # Start auto-refresh timer for API updates
        self._refresh_timer = self.set_interval(3.0, self._auto_refresh_status)
        # Start clock update timer
        self._clock_timer = self.set_interval(1.0, self._update_clock)
        # Initial clock update
        self._update_clock()
    
    def _update_clock(self):
        """Update the clock in the header."""
        try:
            header_right = self.query_one("#header-right", Static)
            current_time = datetime.now().strftime("%H:%M:%S")
            header_right.update(current_time)
        except Exception:
            pass  # Ignore if widget not found
    
    def _animate_status(self):
        """Toggle blink state and refresh table for animation effect."""
        DashboardScreen._blink_state = not DashboardScreen._blink_state
        # Only refresh if we have deployments with transitional status
        if any(d.get("status", "").lower() in ["provisioning", "booting", "rebooting", "migrating", "busy"] 
               for d in self.deployments):
            self.refresh_table()
    
    def _auto_refresh_status(self):
        """Auto-refresh deployment status from API every 3 seconds."""
        self.load_deployments()
        self.refresh_table()
    
    def load_deployments(self):
        """Load all deployments from API."""
        from ...core.deployment_tracker import DeploymentTracker
        
        tracker = DeploymentTracker(self.api_client.client)
        
        # Get all deployments
        api_deployments = tracker.list_deployments()
        
        self.deployments = []
        for dep in api_deployments:
            self.deployments.append({
                "deployment_id": dep['deployment_id'],
                "name": dep['app_name'],
                "environment": dep['env'],
                "instance_id": dep['linode_id'],
                "status": dep['status'],
                "region": dep['region'],
                "plan": dep.get('type', 'unknown'),
                "created": dep.get('created', ''),
                "directory": dep.get('created_from', self.current_dir),
            })
    
    def _get_status_indicator(self, status: str) -> Text:
        """Get a styled status indicator with icon and color."""
        status_lower = status.lower()
        
        # Status mappings with icons and colors
        if status_lower == "running":
            # Solid green for running instances
            return Text("● running", style="bold green")
        elif status_lower == "provisioning":
            # Blinking yellow for provisioning
            if DashboardScreen._blink_state:
                return Text("◉ provisioning", style="bold yellow blink")
            else:
                return Text("◯ provisioning", style="bold yellow")
        elif status_lower == "booting":
            # Blinking green for booting
            if DashboardScreen._blink_state:
                return Text("◉ booting", style="bold green blink")
            else:
                return Text("◯ booting", style="bold green")
        elif status_lower in ["rebooting", "migrating", "busy"]:
            # Blinking yellow for other in-progress states
            if DashboardScreen._blink_state:
                return Text(f"◉ {status_lower}", style="bold yellow blink")
            else:
                return Text(f"◯ {status_lower}", style="bold yellow")
        elif status_lower in ["offline", "stopped"]:
            return Text("○ stopped", style="dim white")
        elif status_lower == "failed":
            return Text("✕ failed", style="bold red")
        else:
            return Text(f"? {status}", style="dim")
    
    def refresh_table(self):
        """Refresh the deployments table."""
        table = self.query_one(DataTable)
        table.clear(columns=True)
        
        # Add columns
        table.add_column("ID", width=10)
        table.add_column("Application", width=18)
        table.add_column("Environment", width=12)
        table.add_column("Plan", width=16)
        table.add_column("Region", width=10)
        table.add_column("Status", width=18)
        table.add_column("Directory", width=40)
        
        # Add rows
        if not self.deployments:
            # Show message if no deployments found
            table.add_row("", "No deployments found", "", "", "", "", "")
            table.add_row("", "", "", "", "", "", "")
            table.add_row("", "Run 'linode-cli build init <template>' to create one", "", "", "", "", "")
        else:
            for deployment in self.deployments:
                status = deployment.get("status", "unknown")
                status_text = self._get_status_indicator(status)
                
                table.add_row(
                    deployment["deployment_id"][:8],  # Show short ID
                    deployment["name"],
                    deployment["environment"],
                    deployment.get("plan", "unknown"),
                    deployment.get("region", ""),
                    status_text,  # Use styled status indicator
                    deployment.get("directory", "")
                )
        
        # Update footer with count
        footer = self.query_one("#footer-info", Static)
        count = len([d for d in self.deployments if d["instance_id"]])
        footer.update(f"Found {count} deployment(s) | {self.current_dir}")
    
    def action_refresh(self):
        """Refresh the deployments list."""
        self.notify("Refreshing deployments...", timeout=1)
        self.load_deployments()
        self.refresh_table()
    
    def action_view_selected(self):
        """View the selected deployment."""
        table = self.query_one(DataTable)
        
        if not self.deployments:
            self.notify("No deployments available", severity="warning")
            return
        
        # Get selected row
        cursor_row = table.cursor_row
        
        # Handle None or invalid cursor position
        if cursor_row is None:
            self.notify("Please select a deployment first", severity="warning")
            return
        
        if cursor_row < 0 or cursor_row >= len(self.deployments):
            self.notify(f"Invalid selection (row {cursor_row}, total {len(self.deployments)})", severity="warning")
            return
        
        deployment = self.deployments[cursor_row]
        
        if not deployment.get("instance_id"):
            self.notify("No instance ID found for this deployment", severity="warning")
            return
        
        # Switch to status view
        from .status_view import StatusViewScreen
        
        try:
            self.app.push_screen(
                StatusViewScreen(
                    self.api_client,
                    deployment["instance_id"],
                    deployment["name"],
                    deployment["environment"],
                    deployment_id=deployment["deployment_id"],
                    region=deployment.get("region", "unknown"),
                    plan=deployment.get("plan", "unknown"),
                    directory=deployment.get("directory", "")
                )
            )
        except Exception as e:
            self.notify(f"Error opening status view: {e}", severity="error", timeout=5)
    
    def action_destroy_selected(self):
        """Destroy the selected deployment with confirmation."""
        table = self.query_one(DataTable)
        
        if not self.deployments:
            self.notify("No deployments available", severity="warning")
            return
        
        # Get selected row
        cursor_row = table.cursor_row
        if cursor_row >= len(self.deployments):
            self.notify("Invalid selection", severity="warning")
            return
        
        deployment = self.deployments[cursor_row]
        
        if not deployment["instance_id"]:
            self.notify("No instance ID found for this deployment", severity="warning")
            return
        
        # Run the async destroy in a worker
        self.run_worker(self._destroy_deployment(deployment), exclusive=True)
    
    async def _destroy_deployment(self, deployment: dict):
        """Actually destroy the deployment (async worker)."""
        from ..widgets import ConfirmModal
        
        details = f"""  Deployment ID: {deployment['deployment_id']}
  Application: {deployment['name']}
  Environment: {deployment['environment']}
  Instance: {deployment['instance_id']}
  Region: {deployment['region']}"""
        
        confirmed = await self.app.push_screen_wait(
            ConfirmModal(
                title="⚠ Destroy Deployment",
                message="This will permanently delete the Linode instance and all its data.\nThis action CANNOT be undone.",
                details=details
            )
        )
        
        if not confirmed:
            self.notify("Destroy cancelled", timeout=2)
            return
        
        # Perform the destroy
        self.notify(f"Destroying {deployment['name']}...", timeout=3)
        
        try:
            from ...core.deployment_tracker import DeploymentTracker
            from ...core import registry
            
            tracker = DeploymentTracker(self.api_client.client)
            
            # Delete the Linode
            status, response = self.api_client.client.call_operation(
                'linodes', 'delete', [str(deployment['instance_id'])]
            )
            
            if status not in [200, 204]:
                self.notify(
                    f"Failed to delete Linode: {response}",
                    severity="error",
                    timeout=10
                )
                return
            
            # Remove from registry for backward compatibility
            registry.remove_deployment(deployment["deployment_id"])
            
            self.notify(
                f"✓ Destroyed {deployment['name']} ({deployment['deployment_id'][:8]})",
                severity="success",
                timeout=5
            )
            
            # Refresh the list
            await asyncio.sleep(1)  # Brief pause to let deletion propagate
            self.load_deployments()
            self.refresh_table()
            
        except Exception as e:
            self.notify(
                f"Error destroying deployment: {e}",
                severity="error",
                timeout=10
            )
    
    def action_help(self):
        """Show help message."""
        help_text = """
Dashboard Commands:

  ↑↓ / j/k     - Navigate deployments
  Enter        - View deployment status
  D            - Destroy deployment
  R            - Refresh list
  Q / Esc      - Quit
  ?            - Show this help

Tips:
  - Deployments are loaded from the current directory and subdirectories
  - Select a deployment and press Enter to view its live status
  - Use 'linode-cli build init <template>' to create new deployments
  - Press D to destroy a deployment (with confirmation)
"""
        self.notify(help_text, timeout=15)
    
    def action_quit(self):
        """Quit the application."""
        self.app.exit()
