"""Log viewer widget with auto-scroll."""

from textual.reactive import reactive
from textual.widgets import RichLog
from textual.containers import Container


class LogViewer(Container):
    """Scrollable log viewer with auto-scroll capability."""
    
    logs = reactive([])
    auto_scroll = reactive(True)
    
    def __init__(self, *args, title="Logs", **kwargs):
        super().__init__(*args, **kwargs)
        self.title = title
        self.log_widget = None
    
    def compose(self):
        """Compose the log viewer."""
        self.log_widget = RichLog(
            highlight=True,
            markup=True,
            wrap=True,
            auto_scroll=True
        )
        self.log_widget.border_title = self.title
        yield self.log_widget
    
    def watch_logs(self, new_logs):
        """React to log updates."""
        if self.log_widget and new_logs:
            # Clear and repopulate
            self.log_widget.clear()
            for line in new_logs:
                self.log_widget.write(line)
    
    def add_log_line(self, line: str):
        """Add a single log line."""
        if self.log_widget:
            self.log_widget.write(line)
    
    def clear(self):
        """Clear all logs (alias for clear_logs)."""
        self.clear_logs()
    
    def clear_logs(self):
        """Clear all logs."""
        if self.log_widget:
            self.log_widget.clear()
        self.logs = []
