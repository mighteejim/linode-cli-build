"""Status view screen for monitoring deployed applications."""

import time
import asyncio
from textual.screen import Screen
from textual.containers import Container, Vertical, Horizontal, ScrollableContainer
from textual.widgets import Header, Footer, Static
from textual.binding import Binding
from rich.text import Text

from ..widgets import InstancePanel, ContainerPanel, LogViewer
from ..api import LinodeAPIClient
from ..utils import format_elapsed_time, format_uptime


class StatusViewScreen(Screen):
    """Screen for viewing live status of deployed applications."""
    
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("r", "refresh", "Refresh"),
        Binding("s", "ssh", "SSH"),
        Binding("d", "destroy", "Destroy"),
        Binding("ctrl+c", "quit", "Quit"),
    ]
    
    CSS = """
    StatusViewScreen {
        background: $surface;
    }
    
    #header-info {
        height: 3;
        background: $primary;
        padding: 1;
    }
    
    #main-content {
        height: 1fr;
        padding: 1;
    }
    
    #overall-status {
        height: 2;
        padding: 0 1;
    }
    
    #panels-container {
        height: auto;
    }
    
    #instance-container {
        width: 1fr;
        padding: 0 1;
    }
    
    #container-container {
        width: 1fr;
        padding: 0 1;
    }
    
    #logs-container {
        height: 4;
        padding: 0 1;
    }
    
    #actions-container {
        height: 2;
        padding: 0 1;
    }
    
    #footer-info {
        height: 1;
        background: $panel;
    }
    """
    
    def __init__(
        self,
        api_client: LinodeAPIClient,
        instance_id: int,
        app_name: str = "app",
        environment: str = "production",
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.api_client = api_client
        self.instance_id = instance_id
        self.app_name = app_name
        self.environment = environment
        self.last_update = time.time()
        self.is_monitoring = True
        self.update_task = None
        self.auto_refresh = True
    
    def compose(self):
        """Compose the status view screen."""
        yield Header(show_clock=True)
        
        # Header info
        yield Static(
            f"Status: {self.app_name} ({self.environment})",
            id="header-info"
        )
        
        # Main scrollable content
        with ScrollableContainer(id="main-content"):
            # Overall status
            yield Static(
                "Overall: ✓ Healthy",
                id="overall-status"
            )
            
            # Panels container (horizontal layout)
            with Horizontal(id="panels-container"):
                with Container(id="instance-container"):
                    yield InstancePanel()
                with Container(id="container-container"):
                    yield ContainerPanel()
            
            # Logs section
            with Container(id="logs-container"):
                yield LogViewer(title="Recent Activity")
            
            # Actions
            yield Static(
                "Quick Actions: [S] SSH  [D] Destroy  [R] Refresh",
                id="actions-container"
            )
        
        # Footer
        yield Static(
            "Auto-refresh: ON (3s) | Last update: 0 seconds ago",
            id="footer-info"
        )
        
        yield Footer()
    
    async def on_mount(self):
        """Start monitoring when screen is mounted."""
        # Reset scroll position to top
        self.scroll_home(animate=False)
        
        self.update_task = self.set_interval(3.0, self.update_status)
        # Initial update
        await self.update_status()
    
    async def update_status(self):
        """Update status from API."""
        if not self.is_monitoring:
            return
        
        try:
            # Fetch instance data
            instance = await self.api_client.get_instance(self.instance_id)
            
            if instance:
                # Update instance panel
                instance_panel = self.query_one(InstancePanel)
                instance_panel.instance_data = instance
                
                # Get IPv4 for BuildWatch API calls
                ipv4 = instance.get("ipv4", [])
                ipv4_addr = ipv4[0] if ipv4 and len(ipv4) > 0 else None
                
                # Update overall status
                status = instance.get("status", "unknown")
                overall_status = self.query_one("#overall-status", Static)
                
                if status == "running":
                    overall_status.update(
                        Text("Overall: ✓ Healthy", style="green bold")
                    )
                elif status == "booting":
                    overall_status.update(
                        Text("Overall: ⟳ Booting", style="cyan bold")
                    )
                elif status == "provisioning":
                    overall_status.update(
                        Text("Overall: ⟳ Provisioning", style="yellow bold")
                    )
                else:
                    overall_status.update(
                        Text(f"Overall: {status}", style="yellow bold")
                    )
                
                # Fetch container status
                container = await self.api_client.get_container_status(instance)
                if container:
                    container_panel = self.query_one(ContainerPanel)
                    container_panel.container_data = container
                
                # Update header with uptime
                created = instance.get("created")
                if created:
                    # Calculate uptime (simplified)
                    header_info = self.query_one("#header-info", Static)
                    header_info.update(
                        f"Status: {self.app_name} ({self.environment})    Uptime: Running"
                    )
                
                # Update footer with last update time
                self.last_update = time.time()
                self.update_footer()
                
                # Fetch Build Monitor logs if IPv4 available
                log_viewer = self.query_one(LogViewer)
                if ipv4_addr:
                    # Try to fetch logs from Build Monitor
                    logs = await self.api_client.fetch_buildwatch_events(ipv4_addr, limit=50)
                    
                    if logs:
                        # Clear old placeholder messages
                        if log_viewer.logs and "[dim]No logs available" in str(log_viewer.logs[0]):
                            log_viewer.clear()
                        
                        # Update log viewer with Build Monitor logs
                        # Each log has: timestamp, message, category, formatted
                        for log_entry in logs:
                            formatted = log_entry.get('formatted', '')
                            message = log_entry.get('message', '')
                            category = log_entry.get('category', '')
                            
                            # The formatted field already has icons and colors
                            if formatted:
                                # Extract just the message part (after timestamp)
                                # Format: [HH:MM:SS] message
                                if '] ' in formatted:
                                    display_msg = formatted.split('] ', 1)[1]
                                else:
                                    display_msg = formatted
                                
                                log_viewer.add_log_line(display_msg)
                        
                        # Fetch and display issues
                        issues = await self.api_client.fetch_buildwatch_issues(ipv4_addr)
                        if issues:
                            # Show unresolved issues
                            unresolved = [i for i in issues if not i.get('resolved', False)]
                            if unresolved:
                                log_viewer.add_log_line("")
                                log_viewer.add_log_line("[bold]⚠ Issues Detected:[/]")
                                for issue in unresolved[:5]:  # Show up to 5 issues
                                    severity = issue.get('severity', 'info')
                                    message = issue.get('message', '')
                                    recommendation = issue.get('recommendation', '')
                                    
                                    if severity == 'critical':
                                        log_viewer.add_log_line(f"  [red]🚨 CRITICAL:[/] {message}")
                                    elif severity == 'warning':
                                        log_viewer.add_log_line(f"  [yellow]⚠ WARNING:[/] {message}")
                                    elif severity == 'error':
                                        log_viewer.add_log_line(f"  [red]❌ ERROR:[/] {message}")
                                    else:
                                        log_viewer.add_log_line(f"  [blue]ℹ INFO:[/] {message}")
                                    
                                    if recommendation:
                                        log_viewer.add_log_line(f"    → {recommendation}")
                    else:
                        # Build Monitor service might not be ready yet
                        if not log_viewer.logs:
                            log_viewer.add_log_line("[dim]Waiting for Build Monitor service to start...[/]")
                            log_viewer.add_log_line("[dim]Logs will appear here as they're generated.[/]")
                else:
                    # No IPv4 or instance not running
                    if not log_viewer.logs:
                        log_viewer.add_log_line("[dim]No logs available yet. Logs will appear here as they're generated.[/]")
        
        except Exception as e:
            self.notify(f"Error updating status: {e}", severity="error")
    
    def update_footer(self):
        """Update footer with refresh status."""
        footer = self.query_one("#footer-info", Static)
        seconds_ago = int(time.time() - self.last_update)
        refresh_status = "ON (3s)" if self.auto_refresh else "OFF"
        footer.update(
            f"Auto-refresh: {refresh_status} | Last update: {seconds_ago} seconds ago"
        )
    
    def action_refresh(self):
        """Manually refresh status."""
        self.notify("Refreshing...", timeout=1)
        asyncio.create_task(self.update_status())
    
    def action_ssh(self):
        """Show SSH command."""
        instance_panel = self.query_one(InstancePanel)
        if instance_panel.instance_data:
            ipv4 = instance_panel.instance_data.get("ipv4", [])
            if ipv4 and len(ipv4) > 0:
                ssh_command = f"ssh root@{ipv4[0]}"
                self.notify(f"SSH: {ssh_command}", timeout=10)
            else:
                self.notify("No IPv4 address available", severity="warning")
        else:
            self.notify("Instance data not loaded", severity="warning")
    
    def action_destroy(self):
        """Confirm and destroy deployment."""
        # Run the async destroy in a worker
        self.run_worker(self._destroy_deployment(), exclusive=True)
    
    async def _destroy_deployment(self):
        """Actually destroy the deployment (async worker)."""
        # Get deployment ID from instance
        from ...core.deployment_tracker import DeploymentTracker
        
        tracker = DeploymentTracker(self.api_client.client)
        
        # Find deployment by instance_id
        all_deployments = tracker.list_deployments()
        deployment = None
        for dep in all_deployments:
            if dep.get('linode_id') == self.instance_id:
                deployment = dep
                break
        
        if not deployment:
            self.notify("Deployment not found", severity="error")
            return
        
        # Show confirmation modal
        from ..widgets import ConfirmModal
        
        details = f"""  Deployment ID: {deployment['deployment_id']}
  Application: {self.app_name}
  Environment: {self.environment}
  Instance: {self.instance_id}
  Region: {deployment.get('region', 'unknown')}"""
        
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
        
        # Stop monitoring
        self.is_monitoring = False
        if self.update_task:
            self.update_task.stop()
        
        # Perform the destroy
        self.notify(f"Destroying {self.app_name}...", timeout=3)
        
        try:
            from ...core import registry
            
            # Delete the Linode
            status, response = self.api_client.client.call_operation(
                'linodes', 'delete', [str(self.instance_id)]
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
                f"✓ Destroyed {self.app_name} ({deployment['deployment_id'][:8]})",
                severity="success",
                timeout=5
            )
            
            # Return to dashboard
            await asyncio.sleep(1)
            self.app.pop_screen()
            
        except Exception as e:
            self.notify(
                f"Error destroying deployment: {e}",
                severity="error",
                timeout=10
            )
    
    def action_back(self):
        """Go back to dashboard."""
        self.is_monitoring = False
        if self.update_task:
            self.update_task.stop()
        self.app.pop_screen()
    
    def action_quit(self):
        """Quit the application."""
        self.is_monitoring = False
        if self.update_task:
            self.update_task.stop()
        self.app.exit()
    
    async def on_unmount(self):
        """Clean up when screen is unmounted."""
        self.is_monitoring = False
        if self.update_task:
            self.update_task.stop()
