from typing import Any, Callable

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Handy", "1")

from gi.repository import GObject, Gtk, Gio, Handy

from ...core import CoreTaskList


class Sidebar(Gtk.ListBox):
    __gtype_name__ = "Sidebar"

    internal_rows = (
        (CoreTaskList.PENDING, "Pending", "checkbox-symbolic"),
        (CoreTaskList.COMPLETED, "Completed", "checkbox-checked-symbolic"),
        (CoreTaskList.TRASH, "Trash", "user-trash-symbolic"),
    )
    label_count = {"Pending": None, "Completed": None, "Trash": None}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        for row_id, row_name, icon_name in self.internal_rows:
            self._add_internal_row(row_id, row_name, icon_name)

    def foreach(self, f: Callable[[Gtk.ListBoxRow], Any]):
        super().foreach(lambda row: f(row) if not row.internal else None)

    def update_counts(self):
        journal = self.get_toplevel().journal
        self.label_count["Pending"].set_label(
            str(journal.get_list_count(CoreTaskList.PENDING))
        )
        self.label_count["Completed"].set_label(
            str(journal.get_list_count(CoreTaskList.COMPLETED))
        )
        self.label_count["Trash"].set_label(
            str(journal.get_list_count(CoreTaskList.TRASH))
        )

    def _add_internal_row(self, row_id: CoreTaskList, row_name: str, icon_name: str):
        row = Gtk.ListBoxRow()
        row.set_name(row_name)
        row.list_id = row_id
        row.list_name = row_name
        box = Gtk.Box(orientation="horizontal")
        box.pack_start(
            Gtk.Image(icon_name=icon_name), expand=False, fill=False, padding=0
        )
        box.pack_start(Gtk.Label(label=row_name), expand=False, fill=False, padding=0)
        self.label_count[row_name] = Gtk.Label()
        box.pack_end(self.label_count[row_name], expand=False, fill=False, padding=0)
        row.add(box)
        row.internal = True
        row.set_selectable(False)
        self.add(row)

    def add_row(self, list_id: int, name: str, icon: str, initial_count: int):
        row = Gtk.ListBoxRow()
        row.list_id = list_id
        row.list_name = name
        box = Gtk.Box(orientation="horizontal")
        icon = Gio.ThemedIcon.new_with_default_fallbacks(icon)
        box.pack_start(Gtk.Image(gicon=icon), expand=False, fill=False, padding=0)
        box.pack_start(Gtk.Label(label=name), expand=False, fill=False, padding=0)
        box.pack_end(
            Gtk.Label(label=str(initial_count)), expand=False, fill=False, padding=0
        )
        row.add(box)
        row.internal = False
        self.add(row)

    def _make_selectable(self):
        # need to use super here to avoid recursion errors
        super().foreach(lambda row: row.set_selectable(True))
