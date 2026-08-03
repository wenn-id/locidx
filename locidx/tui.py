"""TUI for locidx.

The curses layer is separated from the model layer so the ranking and
query logic is unit-testable without a terminal.

Controls:

    /            focus search box
    j / down     move selection down
    k / up       move selection up
    g            jump to top
    G            jump to bottom
    o            open selected file with $VISUAL/$EDITOR
    q            quit
"""

import curses
import os
import subprocess
import sys

from .db import Database
from .search import search


def _open_editor(path):
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vi"
    subprocess.call([editor, path])


class App:
    """Tiny model + view split. Keeps ranking logic off the terminal."""

    def __init__(self, db, root=None):
        self.db = db
        self.root = root
        self.query = ""
        self.results = []
        self.selected = 0
        self.message = "type / to search"

    def run_query(self):
        self.results = search(self.db, self.query, root=self.root, max_results=500)
        self.selected = 0
        self.message = "%d result(s)" % len(self.results)

    def move(self, delta):
        if self.results:
            self.selected = max(0, min(len(self.results) - 1, self.selected + delta))

    def open_selected(self):
        if not self.results:
            return
        _open_editor(self.results[self.selected]["path"])


def _draw(stdscr, app):
    curses.curs_set(0)
    height, width = stdscr.getmaxyx()

    header = " locidx  |  %s" % app.message
    if height > 1:
        try:
            stdscr.addstr(0, 0, header[: width - 1])
        except curses.error:
            pass

    list_top = 1 if height > 1 else 0
    per_page = max(1, height - list_top - 1)

    first = max(0, app.selected - per_page // 2)
    last = first + per_page
    shown = app.results[first:last]

    for i, res in enumerate(shown):
        if list_top + i >= height - 1:
            break
        abs_line = first + i
        line = "%s:%d  %s" % (res["path"], res["lineno"], res["text"])
        try:
            if abs_line == app.selected:
                stdscr.addstr(list_top + i, 0, line[: width - 1], curses.A_REVERSE)
            else:
                stdscr.addstr(list_top + i, 0, line[: width - 1])
        except curses.error:
            pass

    if height > 1:
        footer = "[/] search  [j/k] move  [o] open  [g/G] top/bottom  [q] quit"
        try:
            stdscr.addstr(height - 1, 0, footer[: width - 1], curses.A_DIM)
        except curses.error:
            pass

    stdscr.refresh()


def _run(stdscr, db, root):
    app = App(db, root=root)

    def prompt():
        """Read a search query with echo; return the entered text."""
        curses.curs_set(1)
        stdscr.move(0, 0)
        stdscr.clrtoeol()
        buffer = ""
        while True:
            stdscr.addstr(0, 0, "query: %s" % buffer)
            stdscr.clrtoeol()
            stdscr.refresh()
            key = stdscr.getch()
            if key in (10, 13, ord("\n")):
                break
            elif key in (27,):
                buffer = ""
                break
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                buffer = buffer[:-1]
            elif 32 <= key < 127:
                buffer += chr(key)
        curses.curs_set(0)
        return buffer

    while True:
        _draw(stdscr, app)
        key = stdscr.getch()

        if key in (ord("q"), 27):
            break
        elif key == ord("/"):
            value = prompt()
            if value:
                app.query = value
                app.run_query()
        elif key in (ord("j"), curses.KEY_DOWN):
            app.move(1)
        elif key in (ord("k"), curses.KEY_UP):
            app.move(-1)
        elif key in (ord("g"),):
            app.selected = 0
        elif key in (ord("G"),):
            app.selected = len(app.results) - 1
        elif key in (ord("o"), curses.KEY_ENTER, 10, 13):
            app.open_selected()
        elif key == ord("r"):
            app.run_query()


def run(db=None, root=None):
    """Launch the TUI. db may be an open Database or None (default)."""
    if db is None:
        db = Database()
    try:
        curses.wrapper(_run, db, root)
    finally:
        db.close()
