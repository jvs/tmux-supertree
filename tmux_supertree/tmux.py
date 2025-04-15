from dataclasses import dataclass, field
import subprocess


@dataclass
class TmuxPane:
    id: str
    name: str
    index: str
    window_id: str
    session_id: str
    jump_code: int = -1
    is_enabled: bool = True


@dataclass
class TmuxWindow:
    id: str
    name: str
    index: str
    session_id: str
    jump_code: int = -1
    is_enabled: bool = True
    panes: list[TmuxPane] = field(default_factory=list)


@dataclass
class TmuxSession:
    id: str
    name: str
    jump_code: int = -1
    is_enabled: bool = True
    windows: list[TmuxWindow] = field(default_factory=list)


# def get_tree(log=None) -> list[TmuxSession]:
#     sessions = get_sessions(log=log)
#
#     jump_code = 0
#     for session in sessions:
#         jump_code += 1
#         session.jump_code = jump_code
#
#         for window in session.windows:
#             jump_code += 1
#             window.jump_code = jump_code
#
#             for pane in window.panes:
#                 jump_code += 1
#                 pane.jump_code = jump_code
#
#     return sessions


def get_sessions(log=None) -> list[TmuxSession]:
    cmd = ["tmux", "list-sessions", "-F", "#{session_id} #{session_name}"]
    try:
        # Get session information from tmux
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.returncode != 0:
            return []

        sessions = []

        for line in result.stdout.strip().split('\n'):
            if not line:
                continue

            parts = line.split(' ', 1)
            if len(parts) == 2:
                session_id, session_name = parts
                sessions.append(
                    TmuxSession(
                        id=session_id,
                        name=session_name,
                        windows=get_windows(session_id, log=log),
                    )
                )

        return sessions

    except Exception as e:
        if log:
            log(f"Error getting tmux sessions: {e}")
        return []


def get_windows(session_id: str, log=None) -> list[TmuxWindow]:
    try:
        cmd = [
            "tmux", "list-windows", "-t", session_id, "-F",
            "#{window_id} #{window_index} #{window_name}",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.returncode != 0:
            return []

        windows = []
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue

            parts = line.split(' ', 2)

            if len(parts) >= 3:
                window_id, window_index, window_name = parts
                windows.append(
                    TmuxWindow(
                        id=window_id,
                        name=window_name,
                        index=window_index,
                        session_id=session_id,
                        panes=get_panes(window_id, session_id, log=log),
                    )
                )

        return windows
    except Exception as e:
        if log:
            log(f"Error getting tmux windows: {e}")
        return []


def get_panes(window_id: str, session_id: str, log=None) -> list[TmuxPane]:
    cmd = [
        "tmux", "list-panes", "-t", window_id, "-F",
        "#{pane_id} #{pane_index} #{pane_title}"
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.returncode != 0:
            return []

        panes = []

        for line in result.stdout.strip().split('\n'):
            if not line:
                continue

            parts = line.split(' ', 2)
            pane_id = parts[0]
            pane_index = parts[1]

            # Pane title might be empty, so handle that case
            pane_title = parts[2] if len(parts) > 2 else f"Pane {pane_index}"

            panes.append(
                TmuxPane(
                    id=pane_id,
                    name=pane_title,
                    index=pane_index,
                    window_id=window_id,
                    session_id=session_id,
                )
            )

        return panes
    except Exception as e:
        if log:
            log(f"Error getting tmux panes: {e}")
        return []


def get_session_id(obj):
    if obj is None:
        return None
    elif isinstance(obj, TmuxSession):
        return obj.id
    elif isinstance(obj, (TmuxWindow, TmuxPane)):
        return obj.session_id
    else:
        raise ValueError("Invalid object type")
