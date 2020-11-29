from typing import Any, Callable, Dict, List

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Handy", "1")

from gi.repository import GObject, Gtk, Gio, Handy

from ...core import CoreTaskList, TaskList


@Gtk.Template(resource_path="/org/wrightsman/HandleIt/ui/sidebar.ui")
class Sidebar(Gtk.Box):
    __gtype_name__ = "Sidebar"

    internal_rows = (
        CoreTaskList.PENDING,
        CoreTaskList.COMPLETED,
        CoreTaskList.TRASH,
    )

    stack_mode: Gtk.Stack = Gtk.Template.Child()
    mode_view: Gtk.ListBox = Gtk.Template.Child()
    mode_edit: Gtk.ListBox = Gtk.Template.Child()

    label_pending_count: Gtk.Label = Gtk.Template.Child()
    label_completed_count: Gtk.Label = Gtk.Template.Child()
    label_trash_count: Gtk.Label = Gtk.Template.Child()

    _count_labels: Dict[int, Gtk.Label]
    _lists: List[TaskList]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        for i, row_id in enumerate(self.internal_rows):
            row = self.mode_view.get_row_at_index(i)
            row.list_id = row_id
            row.list_name = row.get_name()
            row.internal = True
        self._count_labels: Dict[int, Gtk.Label] = {}
        self._edit_entries: Dict[int, Gtk.Entry] = {}
        self._lists = []

    def _foreach(self, f: Callable[[Gtk.ListBoxRow], Any]):
        self.mode_view.foreach(lambda row: f(row) if not row.internal else None)

    def clear(self):
        self._count_labels = {}
        self._edit_entries = {}
        self._lists = []
        self._foreach(lambda row: row.destroy())
        self.mode_edit.foreach(lambda row: row.destroy())

    def load_lists(self, tasklists: List[TaskList]):
        self.clear()

        # add lists from database
        for tasklist in tasklists:
            self._count_labels[tasklist.list_id] = self._add_row(tasklist)
            self._edit_entries[tasklist.list_id] = self._add_edit_row(tasklist)

        row = Gtk.ListBoxRow(selectable=False)
        entry = Gtk.Entry(placeholder_text="Create new list...")
        entry.connect("activate", self._on_new_list_entry_activated)
        row.add(entry)
        self.mode_edit.add(row)

        self._lists = tasklists
        self.update_counts()
        self._make_selectable()
        self.show_all()

    def update_counts(self):
        journal = self.get_toplevel().journal
        self.label_pending_count.set_label(
            str(journal.get_list_count(CoreTaskList.PENDING))
        )
        self.label_completed_count.set_label(
            str(journal.get_list_count(CoreTaskList.COMPLETED))
        )
        self.label_trash_count.set_label(
            str(journal.get_list_count(CoreTaskList.TRASH))
        )
        # update other list counts
        list_counts = journal.get_list_count([l.list_id for l in self._lists])
        for tasklist in self._lists:
            self._count_labels[tasklist.list_id].set_label(
                str(list_counts[tasklist.list_id])
            )

    def get_entry_texts(self) -> Dict[int, str]:
        return {
            list_id: entry.get_text() for list_id, entry in self._edit_entries.items()
        }

    def _add_row(self, tasklist: TaskList) -> Gtk.Label:
        row = Gtk.ListBoxRow()
        row.list_id = tasklist.list_id
        row.list_name = tasklist.name
        box = Gtk.Box(orientation="horizontal")
        icon = Gio.ThemedIcon.new_with_default_fallbacks("emblem-default-symbolic")
        box.pack_start(Gtk.Image(gicon=icon), expand=False, fill=False, padding=0)
        box.pack_start(
            Gtk.Label(label=tasklist.name), expand=False, fill=False, padding=0
        )
        label_count = Gtk.Label(label="0")
        box.pack_end(label_count, expand=False, fill=False, padding=0)
        row.add(box)
        row.internal = False
        self.mode_view.add(row)

        return label_count

    def _add_edit_row(self, tasklist: TaskList) -> Gtk.Entry:
        row = Gtk.ListBoxRow(selectable=False)
        box = Gtk.Box(orientation="horizontal")
        icon = Gio.ThemedIcon.new_with_default_fallbacks("emblem-default-symbolic")
        box.pack_start(Gtk.Image(gicon=icon), expand=False, fill=False, padding=0)
        entry = Gtk.Entry(text=tasklist.name)
        box.pack_start(entry, expand=True, fill=True, padding=0)
        button_delete = Gtk.Button(
            image=Gtk.Image(icon_name="window-close-symbolic"),
            margin_start=6,
            name="close",
        )
        button_delete.list_id = tasklist.list_id
        button_delete.connect("clicked", self._on_delete_list_button_pressed)
        row.add(box)
        self.mode_edit.add(row)
        box.pack_start(button_delete, expand=False, fill=False, padding=0)
        return entry

    def _on_new_list_entry_activated(self, entry):
        journal = self.get_toplevel().journal
        journal.add_list(entry.get_text())
        self.load_lists(journal.lists)

    def _on_delete_list_button_pressed(self, button):
        journal = self.get_toplevel().journal
        journal.delete_list(button.list_id)
        self.emit("list_deleted", button.list_id)
        self.load_lists(journal.lists)

    @GObject.Signal(arg_types=(int,))
    def list_deleted(self, list_id: int):
        pass

    def set_edit_mode(self, state: bool) -> None:
        if state:
            self.stack_mode.set_visible_child_name("edit")
        else:
            self.stack_mode.set_visible_child_name("view")

    def _make_selectable(self):
        self.mode_view.foreach(lambda row: row.set_selectable(True))
