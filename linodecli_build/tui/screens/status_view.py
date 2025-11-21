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
    
    # Animation state for blinking indicators (shared with dashboard)
    _blink_state = False
    
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("r", "refresh", "Refresh"),
        Binding("s", "ssh", "SSH"),
        Binding("d", "destroy", "Destroy"),
        Binding("?", "help", "Help"),
        Binding("ctrl+c", "quit", "Quit"),
    ]
    
    CSS = """
    StatusViewScreen {
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
    
    #main-content {
        height: 1fr;
        padding: 0;
    }
    
    #deployment-info {
        height: 3;
        padding: 0 1;
        background: $panel;
    }
    
    .info-item {
        color: $text-muted;
    }
    
    #panels-container {
        height: auto;
        max-height: 12;
        padding: 0;
    }
    
    #instance-container {
        width: 1fr;
        height: auto;
        padding: 0 1;
    }
    
    #container-container {
        width: 1fr;
        height: auto;
        padding: 0 1;
    }
    
    #logs-container {
        height: 1fr;
        min-height: 20;
        padding: 0 1;
    }
    
    #footer-info {
        height: 1;
        background: $panel;
    }
    
    #api-status {
        height: auto;
        max-height: 8;
        padding: 1;
        background: $panel;
        border: solid $accent;
        margin-bottom: 1;
    }
    
    #api-status-grid {
        height: auto;
    }
    
    .api-status-row {
        height: 1;
    }
    
    .api-endpoint {
        width: 40;
        color: $text-muted;
    }
    
    .api-status-indicator {
        width: 1fr;
    }
    """
    
    def __init__(
        self,
        api_client: LinodeAPIClient,
        instance_id: int,
        app_name: str = "app",
        environment: str = "production",
        deployment_id: str = None,
        region: str = None,
        plan: str = None,
        directory: str = None,
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.api_client = api_client
        self.instance_id = instance_id
        self.app_name = app_name
        self.environment = environment
        self.deployment_id = deployment_id
        self.deployment_region = region
        self.deployment_plan = plan
        self.deployment_directory = directory
        self.last_update = time.time()
        self.is_monitoring = True
        self.update_task = None
        self.auto_refresh = True
        self._animation_timer = None
        # Track API call status
        self.api_status = {
            'linode_api': {'status': 'pending', 'last_code': None, 'last_error': None},
            'build_monitor_status': {'status': 'pending', 'last_code': None, 'last_error': None},
            'build_monitor_logs': {'status': 'pending', 'last_code': None, 'last_error': None},
            'build_monitor_issues': {'status': 'pending', 'last_code': None, 'last_error': None},
        }
    
    def compose(self):
        """Compose the status view screen."""
        # Header with version, title, and clock (matching dashboard)
        from ... import PLUGIN_VERSION
        
        with Horizontal(id="header-info"):
            yield Static(
                f"{self.app_name} ({self.environment})",
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
        
        # Main scrollable content
        with ScrollableContainer(id="main-content"):
            # Deployment info - single line style
            yield Static(
                f"[dim]ID:[/] [cyan]{self.deployment_id[:8] if self.deployment_id else 'N/A'}[/]  "
                f"[dim]Plan:[/] {self.deployment_plan or 'N/A'}  "
                f"[dim]Region:[/] {self.deployment_region or 'N/A'}  "
                f"[dim]Status:[/] [id=info-status]⟳ Loading...[/]",
                id="deployment-info"
            )
            
            # Panels container (horizontal layout)
            with Horizontal(id="panels-container"):
                with Container(id="instance-container"):
                    yield InstancePanel()
                with Container(id="container-container"):
                    yield ContainerPanel()
            
            # Logs section - Real-time streaming
            with Container(id="logs-container"):
                yield LogViewer(title="Logs")
        
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
        
        # Start animation timer for blinking status indicators
        self._animation_timer = self.set_interval(0.5, self._animate_status)
        
        # Start clock update timer
        self._clock_timer = self.set_interval(1.0, self._update_clock)
        # Initial clock update
        self._update_clock()
        
        self.update_task = self.set_interval(3.0, self.update_status)
        # Initial update
        await self.update_status()
    
    def _update_clock(self):
        """Update the clock in the header."""
        try:
            from datetime import datetime
            header_right = self.query_one("#header-right", Static)
            current_time = datetime.now().strftime("%H:%M:%S")
            header_right.update(current_time)
        except Exception:
            pass  # Ignore if widget not found
    
    def _animate_status(self):
        """Toggle blink state for status indicators."""
        StatusViewScreen._blink_state = not StatusViewScreen._blink_state
        # Only refresh status if it's a transitional state
        # This will be handled in update_status
    
    def _get_status_indicator(self, status: str) -> str:
        """Get a styled status indicator with icon and color (matches dashboard)."""
        status_lower = status.lower()
        
        # Status mappings with icons and colors (matching dashboard)
        if status_lower == "running":
            return "[bold green]● running[/]"
        elif status_lower == "provisioning":
            # Blinking yellow for provisioning
            if StatusViewScreen._blink_state:
                return "[bold yellow]◉ provisioning[/]"
            else:
                return "[bold yellow]◯ provisioning[/]"
        elif status_lower == "booting":
            # Blinking green for booting
            if StatusViewScreen._blink_state:
                return "[bold green]◉ booting[/]"
            else:
                return "[bold green]◯ booting[/]"
        elif status_lower in ["rebooting", "migrating", "busy"]:
            # Blinking yellow for other in-progress states
            if StatusViewScreen._blink_state:
                return f"[bold yellow]◉ {status_lower}[/]"
            else:
                return f"[bold yellow]◯ {status_lower}[/]"
        elif status_lower in ["offline", "stopped"]:
            return "[dim white]○ stopped[/]"
        elif status_lower == "failed":
            return "[bold red]✕ failed[/]"
        else:
            return f"[dim]? {status}[/]"
    
    async def update_status(self):
        """Update status from API."""
        if not self.is_monitoring:
            return
        
        try:
            # Fetch instance data
            instance = await self.api_client.get_instance(self.instance_id)
            
            if instance:
                # Update API status - Linode API success
                self.api_status['linode_api'] = {'status': 'success', 'last_code': 200, 'last_error': None}
                
                # Update instance panel
                instance_panel = self.query_one(InstancePanel)
                instance_panel.instance_data = instance
                
                # Get IPv4 for BuildWatch API calls
                ipv4 = instance.get("ipv4", [])
                ipv4_addr = ipv4[0] if ipv4 and len(ipv4) > 0 else None
                
                # Update overall status with animated indicator
                status = instance.get("status", "unknown")
                status_str = self._get_status_indicator(status)
                
                # Update the deployment info line
                deployment_info = self.query_one("#deployment-info", Static)
                deployment_info.update(
                    f"[dim]ID:[/] [cyan]{self.deployment_id[:8] if self.deployment_id else 'N/A'}[/]  "
                    f"[dim]Plan:[/] {self.deployment_plan or 'N/A'}  "
                    f"[dim]Region:[/] {self.deployment_region or 'N/A'}  "
                    f"[dim]Status:[/] {status_str}"
                )
                
                # Fetch container status
                container = await self.api_client.get_container_status(instance)
                if container:
                    container_panel = self.query_one(ContainerPanel)
                    container_panel.container_data = container
                
                # Update footer with last update time
                self.last_update = time.time()
                self.update_footer()
                
                # Fetch Build Monitor logs if IPv4 available
                log_viewer = self.query_one(LogViewer)
                if ipv4_addr:
                    # Try to fetch Build Monitor status
                    bm_status = await self.api_client.fetch_buildwatch_status(ipv4_addr)
                    if bm_status:
                        self.api_status['build_monitor_status'] = {'status': 'success', 'last_code': 200, 'last_error': None}
                    else:
                        self.api_status['build_monitor_status'] = {'status': 'error', 'last_code': 'timeout', 'last_error': 'Connection timeout'}
                    
                    # Try to fetch logs from Build Monitor (increased limit for better visibility)
                    logs = await self.api_client.fetch_buildwatch_events(ipv4_addr, limit=100)
                    
                    if logs:
                        # Update API status - logs success
                        self.api_status['build_monitor_logs'] = {'status': 'success', 'last_code': 200, 'last_error': None}
                        
                        # Clear logs and repopulate with fresh data (for real-time streaming)
                        log_viewer.clear()
                        
                        # Add header
                        log_viewer.add_log_line(f"[bold cyan]📡 Streaming logs from Build Monitor[/] [dim]({len(logs)} entries)[/]")
                        log_viewer.add_log_line("")
                        
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
                            # Update API status - issues success
                            self.api_status['build_monitor_issues'] = {'status': 'success', 'last_code': 200, 'last_error': None}
                            
                            # Show unresolved issues
                            unresolved = [i for i in issues if not i.get('resolved', False)]
                            if unresolved:
                                log_viewer.add_log_line("")
                                log_viewer.add_log_line("[bold yellow]⚠ Issues Detected:[/]")
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
                                        log_viewer.add_log_line(f"    [dim]→ {recommendation}[/]")
                        else:
                            # No issues
                            self.api_status['build_monitor_issues'] = {'status': 'success', 'last_code': 200, 'last_error': None}
                    else:
                        # Build Monitor logs not available
                        self.api_status['build_monitor_logs'] = {'status': 'error', 'last_code': 'timeout', 'last_error': 'Connection timeout or service not ready'}
                        
                        # Build Monitor service might not be ready yet
                        if not log_viewer.logs:
                            log_viewer.add_log_line("[dim]Waiting for Build Monitor service to start...[/]")
                            log_viewer.add_log_line("[dim]Logs will appear here as they're generated.[/]")
                else:
                    # No IPv4 yet - instance still provisioning
                    # No need to show anything, logs will update when IPv4 is available
                    
                    # No IPv4 or instance not running
                    if not log_viewer.logs:
                        log_viewer.add_log_line("[dim]No logs available yet. Logs will appear here as they're generated.[/]")
            else:
                # Linode API failed - but update status widget to show we're retrying
                self.api_status['linode_api'] = {'status': 'error', 'last_code': 'error', 'last_error': 'Failed to fetch instance'}
                
                # Keep the status as "⟳ Connecting..." instead of showing stale data
                status_widget = self.query_one("#info-status", Static)
                status_widget.update("[yellow]⟳ Connecting to API...[/]")
        
        except Exception as e:
            # Show the actual exception in the UI
            self.api_status['linode_api'] = {'status': 'error', 'last_code': 'exception', 'last_error': str(e)}
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
    
    def action_help(self):
        """Show help and API status."""
        # Build API status summary
        api_info = []
        api_info.append("[bold cyan]🔌 API Status[/]")
        api_info.append("")
        
        # Linode API
        linode_status = self.api_status.get('linode_api', {})
        if linode_status.get('status') == 'success':
            api_info.append(f"[green]✓[/] Linode API (instance data): OK")
        else:
            error = linode_status.get('last_error', 'Unknown')
            api_info.append(f"[red]✕[/] Linode API: {error}")
        
        # Build Monitor Status
        bm_status = self.api_status.get('build_monitor_status', {})
        if bm_status.get('status') == 'success':
            api_info.append(f"[green]✓[/] Build Monitor /status: OK")
        elif bm_status.get('status') == 'error':
            api_info.append(f"[yellow]⚠[/] Build Monitor /status: Timeout")
        else:
            api_info.append(f"[dim]⟳[/] Build Monitor /status: Pending")
        
        # Build Monitor Logs
        bm_logs = self.api_status.get('build_monitor_logs', {})
        if bm_logs.get('status') == 'success':
            api_info.append(f"[green]✓[/] Build Monitor /logs: OK")
        elif bm_logs.get('status') == 'error':
            api_info.append(f"[yellow]⚠[/] Build Monitor /logs: No data")
        else:
            api_info.append(f"[dim]⟳[/] Build Monitor /logs: Pending")
        
        # Build Monitor Issues
        bm_issues = self.api_status.get('build_monitor_issues', {})
        if bm_issues.get('status') == 'success':
            api_info.append(f"[green]✓[/] Build Monitor /issues: OK")
        else:
            api_info.append(f"[dim]⟳[/] Build Monitor /issues: Pending")
        
        api_info.append("")
        api_info.append("[bold cyan]⌨️ Keyboard Shortcuts[/]")
        api_info.append("")
        api_info.append("  [cyan]Esc[/] - Back to dashboard")
        api_info.append("  [cyan]R[/] - Refresh status")
        api_info.append("  [cyan]S[/] - Show SSH command")
        api_info.append("  [cyan]D[/] - Destroy deployment")
        api_info.append("  [cyan]?[/] - Show this help")
        api_info.append("  [cyan]Ctrl+C[/] - Quit")
        
        help_text = "\n".join(api_info)
        self.notify(help_text, timeout=10)
    
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
        if self._animation_timer:
            self._animation_timer.stop()
