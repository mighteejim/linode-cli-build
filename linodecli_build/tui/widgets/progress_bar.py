"""Deployment progress widget with stage tracking."""

from textual.reactive import reactive
from textual.widgets import Static, ProgressBar
from textual.containers import Container, Vertical
from textual.app import ComposeResult
from rich.text import Text
from rich.progress import Progress, BarColumn, TextColumn

from ..utils import get_status_emoji


class DeploymentProgress(Container):
    """Widget to track and display deployment stages."""
    
    stages = reactive([])
    current_stage = reactive(0)
    
    DEFAULT_STAGES = [
        {"name": "Create Linode", "status": "pending", "time": ""},
        {"name": "Cloud-init started", "status": "pending", "time": ""},
        {"name": "Install dependencies", "status": "pending", "time": ""},
        {"name": "Start container", "status": "pending", "time": ""},
        {"name": "Health check", "status": "pending", "time": ""},
    ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.stages:
            self.stages = self.DEFAULT_STAGES.copy()
    
    def compose(self) -> ComposeResult:
        """Compose the progress display."""
        yield Static(id="progress-bar")
        yield Static(id="stage-list")
    
    def watch_stages(self, new_stages):
        """React to stage updates."""
        self.refresh_display()
    
    def watch_current_stage(self, new_current):
        """React to current stage changes."""
        self.refresh_display()
    
    def refresh_display(self):
        """Refresh the progress display."""
        # Update progress bar
        total = len(self.stages)
        completed = sum(1 for s in self.stages if s["status"] == "complete")
        percent = int((completed / total) * 100) if total > 0 else 0
        
        progress_bar = self.query_one("#progress-bar", Static)
        bar_width = 40
        filled = int((completed / total) * bar_width) if total > 0 else 0
        bar = "━" * filled + "─" * (bar_width - filled)
        progress_text = Text()
        progress_text.append(bar, style="cyan")
        progress_text.append(f" {percent}% ({completed}/{total})")
        progress_bar.update(progress_text)
        
        # Update stage list
        stage_list = self.query_one("#stage-list", Static)
        stage_text = Text()
        
        for i, stage in enumerate(self.stages):
            emoji = get_status_emoji(stage["status"])
            name = stage["name"]
            time_str = stage.get("time", "")
            
            # Style based on status
            if stage["status"] == "complete":
                style = "green"
            elif stage["status"] == "active":
                style = "yellow"
            elif stage["status"] == "failed":
                style = "red"
            else:
                style = "dim"
            
            stage_text.append(f"  {emoji} ", style=style)
            stage_text.append(name, style=style)
            
            if time_str:
                stage_text.append(f"  [{time_str}]", style="dim")
            
            stage_text.append("\n")
        
        stage_list.update(stage_text)
    
    def update_stage(self, stage_index: int, status: str, time: str = ""):
        """Update a specific stage."""
        if 0 <= stage_index < len(self.stages):
            self.stages[stage_index]["status"] = status
            if time:
                self.stages[stage_index]["time"] = time
            self.current_stage = stage_index
            # Trigger reactivity
            self.stages = self.stages.copy()
    
    def set_stage_active(self, stage_index: int):
        """Mark a stage as active."""
        self.update_stage(stage_index, "active")
    
    def set_stage_complete(self, stage_index: int, time: str = ""):
        """Mark a stage as complete."""
        self.update_stage(stage_index, "complete", time)
    
    def set_stage_failed(self, stage_index: int):
        """Mark a stage as failed."""
        self.update_stage(stage_index, "failed")
