from typing import Callable

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class ConfirmationModal(ModalScreen):
    CSS = """
        ConfirmationModal {
            align: center middle;
        }

        #confirmation-modal-container {
            width: 80%;
            height: auto;
            padding: 0 1;
            margin: 0;
            background: $surface;
            align: center middle;
            border: solid $primary;
        }

        #confirmation-modal-message {
            width: 100%;
            height: auto;
            padding: 1;
            background: $surface;
        }

        #confirmation-modal-button-container {
            height: auto;
            width: 100%;
            align-horizontal: right;
            padding-right: 1;
        }

        #confirmation-modal-ok {
            min-width: 4;
            border: none;
        }
    """

    def __init__(self, message: str, callback: Callable) -> None:
        super().__init__()
        self.message = message
        self.callback = callback

    def compose(self) -> ComposeResult:
        yield Container(
            Label(self.message, id="confirmation-modal-message"),
            Container(
                Button("OK", variant="primary", id="confirmation-modal-ok"),
                id="confirmation-modal-button-container",
            ),
            id="confirmation-modal-container",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self._accept()

    def on_key(self, event) -> None:
        if event.key == "escape":
            event.stop()
            self.app.pop_screen()
        elif event.key == "y":
            event.stop()
            self._accept()

    def _accept(self):
        self.callback()
        self.app.pop_screen()
