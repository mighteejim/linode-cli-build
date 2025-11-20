"""Container information panel widget."""

from textual.reactive import reactive
from textual.widgets import Static
from textual.app import ComposeResult
from rich.text import Text
from rich.panel import Panel

from ..utils import get_status_emoji, get_status_color, format_uptime


class ContainerPanel(Static):
    """Widget to display Docker container information."""
    
    container_data = reactive(None)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.border_title = "Container"
    
    def watch_container_data(self, new_data):
        """React to container data changes."""
        if new_data:
            self.update(self.render_container())
    
    def render_container(self) -> Text:
        """Render container information as Rich Text."""
        if not self.container_data:
            return Text("No container data available", style="dim")
        
        container = self.container_data
        text = Text()
        
        # Name
        name = container.get("name", "N/A")
        text.append("Name: ", style="bold")
        text.append(f"{name}\n")
        
        # Image
        image = container.get("image", "N/A")
        text.append("Image: ", style="bold")
        text.append(f"{image}\n")
        
        # Status
        status = container.get("status", "unknown")
        emoji = get_status_emoji(status)
        color = get_status_color(status)
        text.append(f"Status: {emoji} ", style="bold")
        text.append(status, style=color)
        text.append("\n")
        
        # Uptime
        uptime = container.get("uptime", "N/A")
        if uptime != "N/A":
            text.append("Uptime: ", style="bold")
            text.append(f"{uptime}\n")
        
        # Health check
        health = container.get("health", "")
        if health:
            text.append("Health: ", style="bold")
            health_color = "green" if "200" in health or "OK" in health else "yellow"
            text.append(f"{health}\n", style=health_color)
        
        # Ports (if available)
        ports = container.get("ports", [])
        if ports:
            text.append("Ports: ", style="bold")
            text.append(f"{', '.join(ports)}\n")
        
        return text
    
    def render(self) -> Panel:
        """Render the widget."""
        content = self.render_container()
        return Panel(
            content,
            title=self.border_title,
            border_style="cyan",
            padding=(0, 1)
        )
