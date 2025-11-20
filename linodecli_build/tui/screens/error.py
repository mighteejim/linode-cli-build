"""Error screen for displaying error messages."""

from textual.screen import Screen
from textual.containers import Container, Vertical
from textual.widgets import Header, Footer, Static
from textual.binding import Binding
from rich.text import Text
from rich.panel import Panel


class ErrorScreen(Screen):
    """Screen for displaying error messages with user acknowledgment."""
    
    BINDINGS = [
        Binding("escape", "quit", "Quit"),
        Binding("q", "quit", "Quit"),
        Binding("enter", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Quit"),
    ]
    
    CSS = """
    ErrorScreen {
        background: $surface;
        align: center middle;
    }
    
    #error-container {
        width: 80;
        height: auto;
        padding: 2;
        background: $surface;
        border: thick $error;
    }
    
    #error-title {
        text-align: center;
        text-style: bold;
        color: $error;
        padding: 1;
    }
    
    #error-message {
        padding: 2;
        text-align: center;
    }
    
    #error-suggestion {
        padding: 2;
        color: $text-muted;
        text-align: center;
    }
    
    #error-footer {
        text-align: center;
        padding: 1;
        color: $text-muted;
    }
    """
    
    def __init__(self, title: str, message: str, suggestion: str = "", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.error_title = title
        self.error_message = message
        self.error_suggestion = suggestion
    
    def compose(self):
        """Compose the error screen."""
        yield Header()
        
        with Container(id="error-container"):
            yield Static(f"❌ {self.error_title}", id="error-title")
            yield Static(self.error_message, id="error-message")
            if self.error_suggestion:
                yield Static(self.error_suggestion, id="error-suggestion")
            yield Static("Press any key to exit", id="error-footer")
        
        yield Footer()
    
    def action_quit(self):
        """Quit the application."""
        self.app.exit(1)
