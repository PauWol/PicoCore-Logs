#!/usr/bin/env python3
"""
PicoCore Log Manager
─────────────────────
Interactive CLI for managing logs on PicoCore / ESP32 devices.
Requires: pip install rich questionary pyserial
"""

import sys

# ── dependency check ──────────────────────────────────────────────────────────
try:
    import questionary
    from questionary import Style as QStyle
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich import box
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich.rule import Rule
    from rich.padding import Padding
except ImportError:
    print("Missing dependencies. Run:\n  pip install rich questionary pyserial")
    sys.exit(1)

from board import Board, LEVEL_NAMES

# ── theme ─────────────────────────────────────────────────────────────────────

console = Console()

Q_STYLE = QStyle([
    ("qmark",         "fg:#5f87ff bold"),
    ("question",      "bold"),
    ("answer",        "fg:#5f87ff bold"),
    ("pointer",       "fg:#5f87ff bold"),
    ("highlighted",   "fg:#5f87ff bold"),
    ("selected",      "fg:#5f87ff"),
    ("separator",     "fg:#3a3a3a"),
    ("instruction",   "fg:#626262 italic"),
    ("text",          ""),
    ("disabled",      "fg:#4e4e4e italic"),
])

Q_STYLE_DANGER = QStyle([
    ("qmark",         "fg:#ff5f5f bold"),
    ("question",      "bold"),
    ("answer",        "fg:#ff5f5f bold"),
    ("pointer",       "fg:#ff5f5f bold"),
    ("highlighted",   "fg:#ff5f5f bold"),
    ("selected",      "fg:#ff5f5f"),
])

# ── ui primitives ─────────────────────────────────────────────────────────────

def header():
    console.print()
    title = Text()
    title.append("PICOCORE", style="bold white")
    title.append("  //  ", style="dim")
    title.append("Log Manager", style="bold blue")
    console.print(Panel(
        title,
        subtitle="[dim]ESP32 · MicroPython · Binary Logs[/]",
        border_style="blue",
        padding=(0, 3),
        expand=False,
    ))
    console.print()


def section(title: str):
    console.print()
    console.print(Rule(f"  {title}  ", style="dim blue", align="left"))
    console.print()


def success(msg: str):
    console.print(f"  [bold green]  OK[/]  [dim]│[/]  {msg}")

def warn(msg: str):
    console.print(f"  [bold yellow]WARN[/]  [dim]│[/]  {msg}")

def error(msg: str):
    console.print(f"  [bold red] ERR[/]  [dim]│[/]  {msg}")

def info(msg: str):
    console.print(f"  [dim]    →[/]  {msg}")

def abort():
    console.print("\n  [dim]Operation cancelled.[/]\n")
    return False

def confirm_danger(prompt: str) -> bool:
    return questionary.confirm(prompt, default=False, style=Q_STYLE_DANGER).ask()


# ── port selection ─────────────────────────────────────────────────────────────

def select_port(board: Board) -> bool:
    section("Device Selection")

    ports = list(Board.list_all_ports())

    if not ports:
        warn("No serial devices detected on any port.")
        manual = questionary.confirm(
            "Specify port path manually?", default=True, style=Q_STYLE
        ).ask()
        if not manual:
            return False
        port = questionary.text(
            "Port  (e.g. /dev/ttyACM0, COM3):",
            style=Q_STYLE,
        ).ask()
        if not port:
            return False
        board.set_port(port.strip())
        success(f"Port set to [bold]{board.port}[/]")
        return True

    choices = []
    for p in ports:
        vid_pid = f"VID:{p.vid:04X}  PID:{p.pid:04X}" if p.vid else "no VID/PID"
        label   = f"{p.device:<20}  {vid_pid:<22}  {p.description}"
        choices.append(questionary.Choice(title=label, value=p.device))
    choices.append(questionary.Choice(title="  Enter path manually …", value="__manual__"))

    answer = questionary.select(
        "Select device:",
        choices=choices,
        style=Q_STYLE,
    ).ask()

    if answer is None:
        return False

    if answer == "__manual__":
        port = questionary.text("Port path:", style=Q_STYLE).ask()
        if not port:
            return False
        answer = port.strip()

    board.set_port(answer)
    success(f"Connected to [bold]{board.port}[/]")
    return True


# ── actions ────────────────────────────────────────────────────────────────────

def action_list_fs(board: Board):
    section("Device Filesystem")

    with console.status("[blue]Reading filesystem …[/]", spinner="dots"):
        try:
            files = board.list_root_fs()
        except Exception as exc:
            error(str(exc))
            return

    if not files:
        warn("The root filesystem appears to be empty.")
        return

    t = Table(
        box=box.SIMPLE_HEAD,
        show_header=True,
        header_style="bold blue",
        row_styles=["", "dim"],
        padding=(0, 2),
    )
    t.add_column("No.",      style="dim",        width=5,  justify="right")
    t.add_column("Filename", style="bold white",  min_width=24)

    for idx, f in enumerate(files, 1):
        t.add_row(str(idx), str(f))

    console.print(Padding(t, (0, 2)))


def _level_choices():
    choices = [questionary.Choice(title="No filter  —  include all levels", value=0)]
    for num, name in LEVEL_NAMES.items():
        choices.append(questionary.Choice(
            title=f"{name:<6}  and above  (severity >= {num})",
            value=num,
        ))
    return choices


def action_download_logs(board: Board):
    section("Download Logs")

    fmt = questionary.select(
        "Output format:",
        choices=[
            questionary.Choice("CSV    —  spreadsheet-compatible",       "csv"),
            questionary.Choice("JSON   —  structured, machine-readable", "json"),
            questionary.Choice("Text   —  plain human-readable",         "text"),
            questionary.Choice("Table  —  aligned terminal output",      "table"),
        ],
        style=Q_STYLE,
    ).ask()
    if fmt is None:
        return abort()

    min_level = questionary.select(
        "Minimum log level:",
        choices=_level_choices(),
        style=Q_STYLE,
    ).ask()
    if min_level is None:
        return abort()

    auto_convert = questionary.confirm(
        "Convert to selected format automatically?  "
        "(No = save raw .bin to Downloads)",
        default=True,
        style=Q_STYLE,
    ).ask()
    if auto_convert is None:
        return abort()

    console.print()

    progress = Progress(
        SpinnerColumn(spinner_name="dots", style="blue"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=28, style="blue", complete_style="bold blue"),
        TaskProgressColumn(),
        console=console,
        transient=False,
    )

    task_id    = None
    file_count = 0

    def callback(event: str, data: dict):
        nonlocal task_id, file_count

        if event == "files_found":
            file_count = data["count"]
            if file_count == 0:
                return
            steps = file_count * (2 if auto_convert else 1)
            task_id = progress.add_task(
                f"Processing  [bold]{file_count}[/] file(s) …",
                total=steps,
            )

        elif event == "download_done":
            if task_id is not None:
                progress.advance(task_id)
            info(f"Downloaded   [bold]{data['file']}[/]")

        elif event == "convert_done":
            if task_id is not None:
                progress.advance(task_id)
            info(f"Converted    [bold]{data['file']}[/]  ->  [dim]{data['output']}[/]")

        elif event == "done":
            if task_id is not None:
                progress.update(task_id, description="[green]Complete[/]")

    try:
        with progress:
            output_dir, _ = board.download_logs(
                auto_convert=auto_convert,
                format=fmt,
                min_level=min_level,
                callback=callback,
            )
    except Exception as exc:
        error(str(exc))
        return

    if file_count == 0:
        warn("No log files found on the device.")
        return

    console.print()
    success(f"Output directory  [bold]{output_dir}[/]")


def action_delete_logs(board: Board):
    section("Delete Logs")

    with console.status("[blue]Scanning for log files …[/]", spinner="dots"):
        try:
            log_files = list(board._get_log_files())
        except Exception as exc:
            error(str(exc))
            return

    if not log_files:
        warn("No log files found on the device.")
        return

    t = Table(
        box=box.SIMPLE_HEAD,
        show_header=True,
        header_style="bold red",
        padding=(0, 2),
    )
    t.add_column("No.", style="dim", width=5, justify="right")
    t.add_column("File", style="bold white")

    for idx, f in enumerate(log_files, 1):
        t.add_row(str(idx), str(f))

    console.print(Padding(t, (0, 2)))
    console.print(
        f"  [dim]This will permanently remove "
        f"[bold red]{len(log_files)}[/] file(s) from the device.[/]\n"
    )

    if not confirm_danger(f"Confirm deletion of {len(log_files)} file(s)?"):
        return abort()

    with console.status("[red]Deleting …[/]", spinner="dots"):
        try:
            deleted = board.delete_logs()
        except Exception as exc:
            error(str(exc))
            return

    for f in deleted:
        info(f"Removed  [dim]{f}[/]")

    console.print()
    success(f"[bold]{len(deleted)}[/] file(s) deleted from device.")


def action_interrupt(board: Board):
    section("Interrupt Board")

    console.print(
        "  [dim]Sends a CTRL-C sequence over serial to halt the running\n"
        "  MicroPython script and return the device to the REPL prompt.[/]\n"
    )

    if not questionary.confirm(
        "Proceed with interrupt?", default=True, style=Q_STYLE
    ).ask():
        return abort()

    with console.status("[yellow]Interrupting …[/]", spinner="dots"):
        try:
            board.interrupt_board()
        except Exception as exc:
            error(str(exc))
            return

    success("Board interrupted — REPL is now active.")


def action_change_port(board: Board):
    select_port(board)


# ── main menu ─────────────────────────────────────────────────────────────────

MENU = [
    ("download",  " DL ", "Download logs",             action_download_logs),
    ("delete",    " RM ", "Delete logs from device",   action_delete_logs),
    ("fs",        " LS ", "List device filesystem",    action_list_fs),
    ("interrupt", "INT ", "Interrupt board  (CTRL-C)", action_interrupt),
    ("port",      "PORT", "Change device port",        action_change_port),
    ("exit",      "    ", "Exit",                      None),
]


def main_menu(board: Board):
    while True:
        section("Main Menu")

        port_text = (
            f"[bold blue]{board.port}[/]"
            if board.port else "[dim]not configured[/]"
        )
        console.print(f"  Device  [dim]│[/]  {port_text}\n")

        choices = [
            questionary.Choice(
                title=f"[{prefix}]  {label}",
                value=key,
            )
            for key, prefix, label, _ in MENU
        ]

        key = questionary.select(
            "Select action:",
            choices=choices,
            style=Q_STYLE,
        ).ask()

        if key is None or key == "exit":
            console.print("\n  [dim]Session ended.[/]\n")
            break

        fn = next(fn for k, _, __, fn in MENU if k == key)
        if fn:
            fn(board)


# ── entry point ────────────────────────────────────────────────────────────────

def main():
    header()
    board = Board()

    if not select_port(board):
        console.print("\n  [dim]No device selected. Exiting.[/]\n")
        sys.exit(0)

    main_menu(board)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n\n  [dim]Interrupted.[/]\n")
        sys.exit(0)