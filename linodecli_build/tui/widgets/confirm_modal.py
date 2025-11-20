"""Confirmation modal widget for destructive actions."""

from textual.screen import ModalScreen
from textual.containers import Container, Vertical
from textual.widgets import Static, Button
from textual.binding import Binding


class ConfirmModal(ModalScreen):
    """Modal dialog for confirming destructive actions."""
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("n", "cancel", "No"),
        Binding("y", "confirm", "Yes"),
    ]
    
    CSS = """
    ConfirmModal {
        align: center middle;
    }
    
    #dialog {
        width: 60;
        height: auto;
        border: thick $error 80%;
        background: $surface;
        padding: 1 2;
    }
    
    #title {
        width: 100%;
        content-align: center middle;
        text-style: bold;
        color: $error;
        padding: 1 0;
    }
    
    #message {
        width: 100%;
        padding: 1 0;
    }
    
    #details {
        width: 100%;
        padding: 1 0;
        background: $panel;
        border: solid $primary;
    }
    
    #buttons {
        width: 100%;
        height: auto;
        layout: horizontal;
        padding: 1 0;
    }
    
    Button {
        width: 1fr;
        margin: 0 1;
    }
    
    #cancel-button {
        background: $primary;
    }
    
    #confirm-button {
        background: $error;
    }
    """
    
    def __init__(
        self,
        title: str,
        message: str,
        details: str = None,
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.title_text = title
        self.message_text = message
        self.details_text = details
    
    def compose(self):
        """Compose the modal dialog."""
        with Container(id="dialog"):
            yield Static(self.title_text, id="title")
            yield Static(self.message_text, id="message")
            
            if self.details_text:
                yield Static(self.details_text, id="details")
            
            with Container(id="buttons"):
                yield Button("Cancel [N]", variant="default", id="cancel-button")
                yield Button("Confirm [Y]", variant="error", id="confirm-button")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "confirm-button":
            self.dismiss(True)
        else:
            self.dismiss(False)
    
    def action_confirm(self) -> None:
        """Handle confirm action."""
        self.dismiss(True)
    
    def action_cancel(self) -> None:
        """Handle cancel action."""
        self.dismiss(False)
