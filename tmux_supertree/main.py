import argparse
import subprocess
import time

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Tree, Label, Input
from textual.containers import Container

from . import tmux
from .confirmation_modal import ConfirmationModal
from .input_modal import InputModal

initial_session_id = None
initial_window_id = None
current_tree_node = None

command_file = None
return_command = None
start_in_search_mode = False
search_term = ""
show_numbers = False
show_panes = False
show_guides = True
show_hidden_sessions = False

focus_on_session = None


JUMP_TIMEOUT = 0.5
current_jump_label = None
current_jump_updated = None

tmux_sessions = None
highlight_history = []


class TmuxTree(Tree):
    BINDINGS = [
        Binding(key="j", action="move_down", description="Move Cursor Down", show=False),
        Binding(key="k", action="move_up", description="Move Cursor Up", show=False),
        Binding(key="g", action="toggle_guides", description="Toggle guides"),
        Binding(key="n", action="toggle_numbers", description="Toggle numbers"),
        Binding(key="h", action="toggle_hidden_sessions", description="Toggle hidden sessions"),
        Binding(key="s", action="toggle_other_sessions", description="Toggle sessions"),
        Binding(key="e", action="toggle_panes", description="Toggle panes"),
        Binding(key="a", action="add_window", description="Add window"),
        Binding(key="d", action="delete_target", description="Delete target"),
        Binding(key="r", action="rename_target", description="Rename target"),
        Binding(key="enter", action="make_selection", description="Make selection", show=False),
        Binding(key="escape", action="cancel_selection", description="Exit", show=False),
    ]

    def action_move_down(self) -> None:
        self.action_cursor_down()

    def action_move_up(self) -> None:
        self.action_cursor_up()

    def action_toggle_guides(self) -> None:
        global show_guides
        show_guides = not show_guides
        self.show_guides = show_guides
        self._refresh()

    def action_toggle_numbers(self) -> None:
        global show_numbers
        show_numbers = not show_numbers
        self._refresh()

    def action_toggle_hidden_sessions(self) -> None:
        global show_hidden_sessions
        show_hidden_sessions = not show_hidden_sessions
        self._refresh()

    def action_toggle_other_sessions(self) -> None:
        # TODO: Fix the currently highlighted node.
        global focus_on_session
        if focus_on_session is None and current_tree_node is not None:
            focus_on_session = tmux.get_session_id(current_tree_node.data)
        else:
            focus_on_session = None
        self._refresh()

    def action_toggle_panes(self) -> None:
        global show_panes
        old_node = current_tree_node
        show_panes = not show_panes
        self._refresh()

        if old_node is None:
            return

        source = old_node.data
        if isinstance(source, tmux.TmuxPane) and not show_panes:
            target = _find_window(source.window_id)
        else:
            target = _find_target(source)

        if target is not None:
            self.cursor_line = target.jump_code - 1

    def action_make_selection(self) -> None:
        self.app.exit()

    def action_cancel_selection(self) -> None:
        target = None

        if tmux_sessions is not None:
            for session in tmux_sessions:
                if session.id == initial_session_id:
                    for window in session.windows:
                        if window.id == initial_window_id:
                            target = window
                            break
                    else:
                        target = session
                        break

        if target is not None:
            subprocess.run(['tmux', 'switch-client', '-t', target.id])

        self.app.exit()

    def action_add_window(self) -> None:
        modal = InputModal(
            placeholder="New window name",
            callback=self.app.handle_add_window,
        )
        self.app.push_screen(modal)

    def action_delete_target(self) -> None:
        if current_tree_node is None:
            return

        target = current_tree_node.data

        if isinstance(target, tmux.TmuxSession):
            target_type = "session"
        elif isinstance(target, tmux.TmuxWindow):
            target_type = "window"
        else:
            target_type = "pane"

        modal = ConfirmationModal(
            message=f'Delete {target_type} "{target.name}"?',
            callback=self.app.handle_delete,
        )
        self.app.push_screen(modal)

    def action_rename_target(self) -> None:
        modal = InputModal(
            placeholder="New name",
            callback=self.app.handle_rename,
        )
        self.app.push_screen(modal)

    def on_key(self, event) -> None:
        global current_jump_label, current_jump_updated

        if show_numbers and event.key in '1234567890':
            now = time.time()

            if current_jump_updated and now - current_jump_updated < JUMP_TIMEOUT:
                current_jump_label += event.key
            else:
                current_jump_label = event.key

            current_jump_updated = now
            self.cursor_line = int(current_jump_label) - 1

    def on_mount(self) -> None:
        self.guide_depth = 3
        self.ICON_NODE = ''
        self.ICON_NODE_EXPANDED = ''
        self.show_root = False
        self.show_guides = show_guides
        self.root.expand()
        self._refresh()

        target = _find_window(initial_window_id)
        if target is not None:
            self.cursor_line = target.jump_code - 1

    def _refresh(self) -> None:
        global tmux_sessions

        self.clear()
        tmux_sessions = tmux.get_sessions(log=self.log)

        if not tmux_sessions:
            self.root.add("[red]No tmux sessions found[/]")
            return

        first_marked_data = None
        has_disabled_data = False
        jump_code = 0

        def add(parent, name: str, data):
            nonlocal jump_code, first_marked_data, has_disabled_data

            jump_code += 1
            data.jump_code = jump_code

            parent_name = parent.data.name if parent.data else ""
            marked_name = _apply_fuzzy_markup(search_term, parent_name, name)
            if marked_name:
                name = marked_name
                data.is_enabled = True
            else:
                name = f"[#777777]{name}[/]"
                data.is_enabled = False
                has_disabled_data = True

            if marked_name and not first_marked_data:
                first_marked_data = data

            if show_numbers:
                label = f"[#666666]{jump_code}:[/] {name}"
            else:
                label = name

            return parent.add(label, data=data)

        for session in tmux_sessions:
            if not show_hidden_sessions and session.name.startswith('__'):
                continue

            if focus_on_session is not None and session.id != focus_on_session:
                continue

            session_node = add(self.root, session.name, session)

            for window in session.windows:
                window_name = window.name or f"Window {window.index}"
                window_node = add(session_node, window_name, window)

                if show_panes:
                    for pane in window.panes:
                        pane_name = pane.name or f"Pane {pane.index}"
                        add(window_node, pane_name, pane)

        # Expand all nodes.
        for node in self.root.children:
            node.expand()
            for child in node.children:
                child.expand()

        if has_disabled_data and first_marked_data:
            self.cursor_line = first_marked_data.jump_code - 1

    def on_tree_node_highlighted(self, event) -> None:
        global current_tree_node

        target = event.node.data
        current_tree_node = event.node
        highlight_history.append(target)

        if isinstance(target, tmux.TmuxSession):
            subprocess.run(['tmux', 'switch-client', '-t', target.id])
            return

        if isinstance(target, tmux.TmuxWindow):
            subprocess.run([
                'tmux', 'switch-client', '-t', f"{target.session_id}:{target.id}"
            ])
            return


class SearchInput(Input):
    def on_key(self, event) -> None:
        global search_term

        if event.key == "escape":
            event.stop()
            self.visible = False
            self.value = ""
            search_term = ""

    @on(Input.Changed)
    def on_input_changed(self, event: Input.Changed) -> None:
        global search_term
        search_term = event.value

        tree = self.app.query_one(TmuxTree)
        tree._refresh()


class MainApp(App):
    BINDINGS = [
        Binding(key="/", action="toggle_search", description="Search"),
    ]
    CSS = """
        Tree { padding: 1; }
        #search_input { border: wide $primary; height: 3; }
    """

    def compose(self) -> ComposeResult:
        yield TmuxTree("Tmux Sessions")
        yield SearchInput(id="search_input", placeholder="Search...")

    def on_mount(self) -> None:
        if not start_in_search_mode:
            search_input = self.query_one("#search_input")
            search_input.visible = False

    def on_key(self, event) -> None:
        global search_term

        if event.key == "escape":
            self.exit()

    def action_toggle_search(self) -> None:
        """Toggle the search box visibility."""
        search_input = self.query_one("#search_input")

        if search_input.visible:
            search_input.visible = False
        else:
            search_input.visible = True
            search_input.value = ""
            search_input.focus()

    def handle_add_window(self, name: str) -> None:
        if current_tree_node is None:
            return

        target = current_tree_node.data
        position = 'b' if isinstance(target, tmux.TmuxSession) else 'a'

        if command_file:
            with open(command_file, "w") as f:
                f.write(
                    "tmux new-window"
                    f" -{position}"
                    f" -t '{target.id}'"
                    f" -n '{name}'"
                    " -c '#{pane_current_path}'\n"
                )
                if return_command:
                    f.write(return_command)
                self.exit()

    def handle_rename(self, name: str) -> None:
        if current_tree_node is None:
            return

        target = current_tree_node.data

        if isinstance(target, tmux.TmuxSession):
            cmd = ["tmux", "rename-session", "-t", target.id, name]
        elif isinstance(target, tmux.TmuxWindow):
            cmd = ["tmux", "rename-window", "-t", target.id, name]
        else:
            raise NotImplementedError("Renaming panes is not supported yet.")

        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            self.log(f"Error renaming target: {e}")
            return

        tree = self.query_one(TmuxTree)
        tree._refresh()

        if isinstance(target, tmux.TmuxSession):
            new_session = _find_session_by_name(name)

            if new_session is not None:
                tree.cursor_line = new_session.jump_code - 1

    def handle_delete(self) -> None:
        if current_tree_node is None or not tmux_sessions:
            return

        target = current_tree_node.data

        if isinstance(target, tmux.TmuxSession):
            self.handle_delete_session(target)
        elif isinstance(target, tmux.TmuxWindow):
            self.handle_delete_window(target)

    def handle_delete_session(self, target: tmux.TmuxSession) -> None:
        assert tmux_sessions is not None

        next_target = None
        for obj in reversed(highlight_history):
            maybe_session_id = tmux.get_session_id(obj)

            if maybe_session_id is not None and maybe_session_id != target.id:
                next_target = obj
                break

        if next_target is None:
            for session in tmux_sessions:
                if session.id != target.id:
                    next_target = session
                    break

        self._handle_delete_target(target, next_target)

    def handle_delete_window(self, target: tmux.TmuxWindow) -> None:
        assert tmux_sessions is not None

        next_target = None
        for obj in reversed(highlight_history):
            if obj is not target:
                next_target = obj
                break

        if next_target is None:
            for session in tmux_sessions:
                for window in session.windows:
                    if window.id != target.id:
                        next_target = window
                        break

        self._handle_delete_target(target, next_target)

    def _handle_delete_target(self, target, next_target) -> None:
        cmds = []

        if next_target is not None:
            cmds.append(["tmux", "switch-client", "-t", next_target.id])

        command_names = {
            tmux.TmuxSession: "kill-session",
            tmux.TmuxWindow: "kill-window",
            tmux.TmuxPane: "kill-pane",
        }
        command_name = command_names[type(target)]
        cmds.append(["tmux", command_name, "-t", target.id])

        try:
            for cmd in cmds:
                subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            self.log(f"Error deleting target: {e}")
            return

        tree = self.query_one(TmuxTree)
        tree._refresh()

        if next_target is not None:
            tree.cursor_line = next_target.jump_code - 1


def _find_session_by_name(name):
    if not tmux_sessions:
        return None

    for session in tmux_sessions:
        if session.name == name:
            return session



def _find_target(tmux_object):
    if not tmux_sessions:
        return None

    for session in tmux_sessions:
        if isinstance(tmux_object, tmux.TmuxSession):
            if session.id == tmux_object.id:
                return session
            else:
                continue

        for window in session.windows:
            if isinstance(tmux_object, tmux.TmuxWindow):
                if window.id == tmux_object.id:
                    return window
                else:
                    continue

            for pane in window.panes:
                if pane.id == tmux_object.id:
                    return pane


def _find_window(window_id):
    if not tmux_sessions:
        return None

    for session in tmux_sessions:
        for window in session.windows:
            if window.id == window_id:
                return window

    return None


def _is_fuzzy_match(search_term, name):
    if not search_term:
        return True

    search_term = search_term.lower()
    name = name.lower()
    if not search_term:
        return True

    i = 0

    for char in name:
        # If current character matches the current character in search_term
        if char == search_term[i]:
            # Move to next character in search_term.
            i += 1

            # Have we matched all characters in search_term?
            if i == len(search_term):
                return True

    # If we've gone through all of name without matching all of search_term.
    return False


def _apply_fuzzy_markup(search_term, parent_name, name):
    if not search_term:
        return name

    if "/" in search_term:
        parent_search_term, search_term = search_term.split("/", 1)
    else:
        parent_search_term = None

    if parent_name and parent_search_term:
        if not _is_fuzzy_match(parent_search_term, parent_name):
            return None

    i = 0
    search_term = search_term.lower().replace(" ", "")

    result = []
    num_matches = 0

    for char in name:
        is_match = len(search_term) > i and char.lower() == search_term[i]

        if is_match:
            char = f"[underline bold]{char}[/]"
            num_matches += 1
            i += 1

        result.append(char)

    if num_matches == len(search_term):
        return "".join(result)
    else:
        return None


def _set_initial_session_and_window():
    global initial_session_id, initial_window_id

    output = subprocess.check_output(
        ['tmux', 'display-message', '-p', '#{session_id} #{window_id}'],
        stderr=subprocess.DEVNULL,
        text=True
    ).strip()

    initial_session_id, initial_window_id = output.split()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--command-file')
    parser.add_argument('--return-command')
    parser.add_argument('--search-mode', action='store_true')
    args = parser.parse_args()

    start_in_search_mode = args.search_mode
    command_file = args.command_file
    return_command = args.return_command

    _set_initial_session_and_window()
    app = MainApp()
    app.run()
