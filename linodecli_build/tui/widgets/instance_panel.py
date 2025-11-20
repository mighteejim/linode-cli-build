"""Instance information panel widget."""

from textual.reactive import reactive
from textual.widgets import Static
from textual.app import ComposeResult
from rich.text import Text
from rich.panel import Panel

from ..utils import get_status_emoji, get_status_color, format_timestamp, get_region_display_name


class InstancePanel(Static):
    """Widget to display Linode instance information."""
    
    instance_data = reactive(None)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.border_title = "Instance"
    
    def watch_instance_data(self, new_data):
        """React to instance data changes."""
        if new_data:
            self.update(self.render_instance())
    
    def render_instance(self) -> Text:
        """Render instance information as Rich Text."""
        if not self.instance_data:
            return Text("No instance data available", style="dim")
        
        instance = self.instance_data
        text = Text()
        
        # Status line
        status = instance.get("status", "unknown")
        emoji = get_status_emoji(status)
        color = get_status_color(status)
        text.append(f"Status: {emoji} ", style="bold")
        text.append(status, style=color)
        text.append("\n")
        
        # ID
        instance_id = instance.get("id", "N/A")
        text.append("ID: ", style="dim")
        text.append(f"{instance_id}\n")
        
        # Region
        region = instance.get("region", "N/A")
        region_display = get_region_display_name(region)
        text.append("Region: ", style="dim")
        text.append(f"{region} ({region_display})\n")
        
        # Type
        instance_type = instance.get("type", "N/A")
        text.append("Type: ", style="dim")
        text.append(f"{instance_type}\n")
        
        # IPv4
        ipv4 = instance.get("ipv4", [])
        if ipv4 and len(ipv4) > 0:
            text.append("IPv4: ", style="dim")
            text.append(f"{ipv4[0]}\n")
        
        # Label (only if set and different from deployment ID pattern)
        label = instance.get("label", "")
        if label and not label.startswith("build-"):
            text.append("Label: ", style="dim")
            text.append(f"{label}\n")
        
        # Created time
        created = instance.get("created")
        if created:
            text.append("Created: ", style="dim")
            text.append(format_timestamp(created))
        
        return text
    
    def render(self) -> Panel:
        """Render the widget."""
        content = self.render_instance()
        return Panel(
            content,
            title=self.border_title,
            border_style="blue",
            padding=(0, 1)
        )
