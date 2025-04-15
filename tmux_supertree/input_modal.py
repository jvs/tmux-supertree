from typing import Callable

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Input


class InputModal(ModalScreen):
    CSS = """
        InputModal {
            align: center middle;
        }

        #input-modal-container {
            width: 100%;
            height: auto;
            padding: 0 1;
            margin: 0;
            background: $surface;
            align: center middle;
        }

        #input-modal-input {
            width: 100%;
            border: wide $primary;
        }
    """

    def __init__(self, placeholder: str, callback: Callable) -> None:
        super().__init__()
        self.placeholder = placeholder
        self.callback = callback

    def compose(self) -> ComposeResult:
        yield Container(
            Input(placeholder=self.placeholder, id="input-modal-input"),
            id="input-modal-container",
        )

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.app.pop_screen()
            event.stop()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        name = event.value
        self.callback(name)
        self.app.pop_screen()

    def on_mount(self) -> None:
        self.query_one(Input).focus()
