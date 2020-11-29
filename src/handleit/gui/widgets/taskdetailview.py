from datetime import datetime, timezone
from typing import List, Dict

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Handy", "1")

from gi.repository import GObject, Gtk, Gio, Handy

from ...core import Task


@Gtk.Template(resource_path="/org/wrightsman/HandleIt/ui/taskdetailview.ui")
class TaskDetailView(Gtk.Box):
    __gtype_name__ = "TaskDetailView"

    _task = None

    stack_mode: Gtk.Stack = Gtk.Template.Child()
    mode_view: Gtk.Grid = Gtk.Template.Child()
    mode_edit: Gtk.Grid = Gtk.Template.Child()

    label_description: Gtk.Label = Gtk.Template.Child()
    button_complete = Gtk.Template.Child()
    button_delete = Gtk.Template.Child()

    entry_description = Gtk.Template.Child()
    textview_notes = Gtk.Template.Child()

    entry_completion_date = Gtk.Template.Child()
    entry_completion_time = Gtk.Template.Child()
    entry_start_date = Gtk.Template.Child()
    entry_start_time = Gtk.Template.Child()
    entry_due_date = Gtk.Template.Child()
    entry_due_time = Gtk.Template.Child()

    spinbutton_priority = Gtk.Template.Child()
    listbox_lists: Gtk.ListBox = Gtk.Template.Child()
    combobox_new_lists: Gtk.ComboBoxText = Gtk.Template.Child()
    _combobox_list_name_to_id: Dict[str, int]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.combobox_new_lists.connect("changed", self._on_list_combobox_changed)

    @property
    def task(self):
        return self._task

    def set_edit_mode(self, state: bool) -> None:
        if state:
            self.stack_mode.set_visible_child_name("edit")
        else:
            self.stack_mode.set_visible_child_name("view")

    def load_task(self, task: Task):
        self._task = task
        self._load_view_mode()
        self._load_edit_mode()

    def reload(self):
        self._task = self.get_toplevel().journal.get_task(self.task.task_id)
        self._load_view_mode()
        self._load_edit_mode()

    def _add_single_row_view(self, title: str, value: str, row: int) -> None:
        label_title = Gtk.Label(title, halign=Gtk.Align.END)
        label_title.get_style_context().add_class("attr-label")
        self.mode_view.attach(
            child=label_title, left=0, top=row, width=1, height=1,
        )
        self.mode_view.attach(
            child=Gtk.Label(value, halign=Gtk.Align.START),
            left=1,
            top=row,
            width=1,
            height=1,
        )

    def _add_double_row_view(self, title: str, widget: Gtk.Widget, row: int) -> None:
        label_title = Gtk.Label(title, halign=Gtk.Align.END)
        label_title.get_style_context().add_class("attr-label")
        self.mode_view.attach(child=label_title, left=0, top=row, width=1, height=1)

        self.mode_view.attach(child=widget, left=0, top=row + 1, width=2, height=1)

    def _load_view_mode(self):
        journal = self.get_toplevel().journal

        self.label_description.set_label(self.task.description)

        # set up the button labels
        if self.task.is_trashed:
            self.button_delete.set_label("Restore")
            self.button_complete.set_label("Permanently Delete")
        else:
            self.button_delete.set_label("Delete")
            if self.task.completion_time:
                self.button_complete.set_label("Uncomplete")
            else:
                self.button_complete.set_label("Complete")

        # clean up the grid, except for description and buttons
        self.mode_view.foreach(
            lambda child: None
            if (child.get_name() in {"description", "button_box"})
            else child.destroy()
        )

        # construct the grid
        last_row_num = 1

        ## set up note rows
        if self.task.notes is not None:
            self._add_double_row_view(
                "notes",
                Gtk.Label(self.task.notes, halign=Gtk.Align.START, margin_bottom=12),
                last_row_num + 1,
            )
            last_row_num += 2

        ## set up creation time row
        self._add_single_row_view(
            "created", self.task.creation_time.isoformat(), last_row_num + 1
        )
        last_row_num += 1

        ## set up completion time row
        if self.task.completion_time is not None:
            self._add_single_row_view(
                "completed", self.task.completion_time.isoformat(), last_row_num + 1
            )
            last_row_num += 1

        ## set up start time row
        if self.task.start_time is not None:
            self._add_single_row_view(
                "start", self.task.start_time.isoformat(), last_row_num + 1
            )
            last_row_num += 1

        ## set up due time row
        if self.task.due_time is not None:
            self._add_single_row_view(
                "due", self.task.due_time.isoformat(), last_row_num + 1
            )
            last_row_num += 1

        ## set up priority row
        if self.task.priority:
            self._add_single_row_view(
                "priority", str(self.task.priority), last_row_num + 1
            )
            last_row_num += 1

        ## set up lists view
        if self.task.lists:
            list_names = [
                l.name for l in self.get_toplevel().journal.get_lists(self.task.lists)
            ]
            list_listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
            for list_name in list_names:
                row = Gtk.ListBoxRow()
                row.add(Gtk.Label(list_name))
                list_listbox.add(row)
            self._add_double_row_view("lists", list_listbox, last_row_num + 1)
            last_row_num += 2

        ## set up tags view
        if self.task.tags:
            tag_listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
            for tag_name in self.task.tags:
                row = Gtk.ListBoxRow()
                row.add(Gtk.Label(tag_name))
                tag_listbox.add(row)
            self._add_double_row_view("tags", tag_listbox, last_row_num + 1)
            last_row_num += 2

        ## set up subtasks view
        if self.task.subtasks:
            subtask_listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
            subtask_descs = [
                task.description
                for task in self.get_toplevel().journal.get_tasks(self.task.subtasks)
            ]
            for subtask_desc in subtask_descs:
                row = Gtk.ListBoxRow()
                row.add(Gtk.Label(subtask_desc, halign=Gtk.Align.START))
                subtask_listbox.add(row)
            self._add_double_row_view("subtasks", subtask_listbox, last_row_num + 1)
            last_row_num += 2

        ## set up parent item
        if self.task.parent is not None:
            self._add_single_row_view(
                "parent",
                journal.get_task(self.task.parent).description,
                last_row_num + 1,
            )
            last_row_num += 1

        ## set up dependencies view
        if self.task.dependencies:
            dependency_listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
            dependency_descs = [
                task.description
                for task in self.get_toplevel().journal.get_tasks(
                    self.task.dependencies
                )
            ]
            for dependency_desc in dependency_descs:
                row = Gtk.ListBoxRow()
                row.add(Gtk.Label(dependency_desc, halign=Gtk.Align.START))
                dependency_listbox.add(row)
            self._add_double_row_view(
                "dependencies", dependency_listbox, last_row_num + 1
            )
            last_row_num += 2

        ## set up dependents view
        if self.task.dependents:
            dependent_listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
            dependents_descs = [
                task.description
                for task in self.get_toplevel().journal.get_tasks(self.task.dependents)
            ]
            for dependent_desc in dependents_descs:
                row = Gtk.ListBoxRow()
                row.add(Gtk.Label(dependent_desc, halign=Gtk.Align.START))
                dependent_listbox.add(row)
            self._add_double_row_view("dependents", dependent_listbox, last_row_num + 1)
            last_row_num += 2

        self.mode_view.show_all()

    def _load_edit_mode(self):
        journal = self.get_toplevel().journal

        self.entry_description.set_text(self.task.description)
        if self.task.notes is not None:
            self.textview_notes.get_buffer().set_text(self.task.notes)

        if self.task.completion_time is not None:
            local_cmp_time = self.task.completion_time.astimezone()
            self.entry_completion_date.set_text(
                "{0:%Y}-{0:%m}-{0:%d}".format(local_cmp_time)
            )
            self.entry_completion_time.set_text(
                "{0:%H}:{0:%M}:{0:%S}".format(local_cmp_time)
            )
        else:
            self.entry_completion_date.set_text("")
            self.entry_completion_time.set_text("")

        if self.task.start_time is not None:
            local_start_time = self.task.start_time.astimezone()
            self.entry_start_date.set_text(
                "{0:%Y}-{0:%m}-{0:%d}".format(local_start_time)
            )
            self.entry_start_time.set_text(
                "{0:%H}:{0:%M}:{0:%S}".format(local_start_time)
            )
        else:
            self.entry_start_date.set_text("")
            self.entry_start_time.set_text("")

        if self.task.due_time is not None:
            local_due_time = self.task.due_time.astimezone()
            self.entry_due_date.set_text("{0:%Y}-{0:%m}-{0:%d}".format(local_due_time))
            self.entry_due_time.set_text("{0:%H}:{0:%M}:{0:%S}".format(local_due_time))
        else:
            self.entry_due_date.set_text("")
            self.entry_due_time.set_text("")

        self.spinbutton_priority.set_value(self.task.priority)

        # reset and add the lists
        self.listbox_lists.foreach(
            lambda row: row.destroy() if row.get_name() != "combobox" else None
        )
        tasklists = set()
        for tasklist in journal.get_lists(self.task.lists):
            self._add_list_listbox_edit(tasklist.name, tasklist.list_id)
            tasklists.add(tasklist.name)

        # add the new list dropdown
        self.combobox_new_lists.remove_all()
        self.combobox_new_lists.append_text("Add to list...")
        self.combobox_new_lists.set_active(0)
        self._combobox_list_name_to_id = {}
        for tasklist in journal.lists:
            if tasklist.name not in tasklists:
                self._combobox_list_name_to_id[tasklist.name] = tasklist.list_id
                self.combobox_new_lists.append_text(tasklist.name)

        self.mode_edit.show_all()

    def _add_list_listbox_edit(self, tasklist_name: str, tasklist_id: int):
        label_name = Gtk.Label(label=tasklist_name)
        button_close = Gtk.Button(image=Gtk.Image(icon_name="window-close-symbolic"))
        row = Gtk.ListBoxRow()
        button_close.row = row
        button_close.connect("clicked", self._on_list_delete_button_clicked)
        box = Gtk.Box(orientation="horizontal")
        box.pack_start(label_name, True, True, 0)
        box.pack_end(button_close, False, False, 0)
        row.list_id = tasklist_id
        row.list_name = tasklist_name
        row.add(box)
        n_children = len(self.listbox_lists.get_children())
        self.listbox_lists.insert(row, n_children - 1)
        row.show_all()

    def _on_list_combobox_changed(self, combobox):
        selected_id = combobox.get_active()
        selected_list = combobox.get_active_text()
        if selected_list not in {None, "Add to list..."}:
            combobox.remove(selected_id)
            self._add_list_listbox_edit(
                selected_list, self._combobox_list_name_to_id[selected_list]
            )
            del self._combobox_list_name_to_id[selected_list]

    def _on_list_delete_button_clicked(self, button):
        self.combobox_new_lists.append_text(button.row.list_name)
        self._combobox_list_name_to_id[button.row.list_name] = button.row.list_id
        button.row.destroy()

    @Gtk.Template.Callback()
    def _on_complete_button_clicked(self, button_complete):
        if self._task.is_trashed:
            # permanently delete and go back in view history
            self.emit("task_deleted")
        else:
            modified_attributes = Gtk.ListStore(str)
            modified_attributes.append(["completion_time"])
            journal = self.get_toplevel().journal
            if self._task.completion_time:
                self._task.completion_time = None
                self.button_complete.set_label("Complete")
            else:
                self._task.completion_time = datetime.now(timezone.utc)
                self.button_complete.set_label("Uncomplete")
            journal.update_task(
                self._task.task_id, new_completion_time=self._task.completion_time
            )
            self.emit("task_modified", modified_attributes)
            self._load_view_mode()
            self._load_edit_mode()

    @Gtk.Template.Callback()
    def _on_delete_button_clicked(self, button_delete):
        modified_attributes = Gtk.ListStore(str)
        modified_attributes.append(["is_trashed"])
        journal = self.get_toplevel().journal
        if self._task.is_trashed:
            self.button_delete.set_label("Delete")
            if self._task.completion_time:
                self.button_complete.set_label("Uncomplete")
            else:
                self.button_complete.set_label("Complete")
        else:
            self.button_delete.set_label("Restore")
            self.button_complete.set_label("Permanently Delete")
        self._task.is_trashed = not self._task.is_trashed
        journal.update_task(self._task.task_id, is_trashed=self._task.is_trashed)
        self.emit("task_modified", modified_attributes)
        self._load_view_mode()
        self._load_edit_mode()

    @Gtk.Template.Callback()
    def _on_edit_cancel_button_clicked(self, button_cancel):
        """
        When the cancel button on the task detail edit mode is clicked, switch
        back to view mode and reset edit mode state
        """
        self.stack_mode.set_visible_child_name("view")
        self._load_edit_mode()

    @Gtk.Template.Callback()
    def _on_edit_confirm_button_clicked(self, button_confirm):
        """
        When the confirm button on the task detail edit mode is clicked, save
        the changes to the task in the journal and switch back to view mode.
        """
        journal = self.get_toplevel().journal

        # check what has changed
        kwargs = {}
        changes: List[str] = []

        if self.entry_description.get_text() != self.task.description:
            kwargs["new_description"] = self.entry_description.get_text()
            changes.append("description")

        if self.textview_notes.get_buffer().props.text != self.task.notes:
            kwargs["new_notes"] = self.textview_notes.get_buffer().props.text
            changes.append("notes")

        if self._time_is_new_or_changed("completion"):
            new_date = self.entry_completion_date.get_text()
            new_time = self.entry_completion_time.get_text()
            if (new_date == "") and (new_time == ""):
                new_completion_time = None
                kwargs["new_completion_time"] = new_completion_time
                changes.append("completion_time")
            else:
                try:
                    # times in the past are always UTC
                    new_completion_time = datetime.fromisoformat(
                        f"{new_date}T{new_time}"
                    ).astimezone(timezone.utc)
                    if new_completion_time < datetime.now(timezone.utc):
                        kwargs["new_completion_time"] = new_completion_time
                        changes.append("completion_time")
                except ValueError:
                    pass

        if self._time_is_new_or_changed("start"):
            new_date = self.entry_start_date.get_text()
            new_time = self.entry_start_time.get_text()
            if (new_date == "") and (new_time == ""):
                new_start_time = None
                kwargs["new_start_time"] = new_start_time
                changes.append("start_time")
            else:
                try:
                    # potentially future times are in local time zones
                    new_start_time = datetime.fromisoformat(
                        f"{new_date}T{new_time}"
                    ).astimezone()
                    kwargs["new_start_time"] = new_start_time
                    changes.append("start_time")
                except ValueError:
                    pass

        if self._time_is_new_or_changed("due"):
            new_date = self.entry_due_date.get_text()
            new_time = self.entry_due_time.get_text()
            if (new_date == "") and (new_time == ""):
                new_due_time = None
                kwargs["new_due_time"] = new_due_time
                changes.append("due_time")
            else:
                try:
                    # potentially future times are in local time zones
                    new_due_time = datetime.fromisoformat(
                        f"{new_date}T{new_time}"
                    ).astimezone()
                    kwargs["new_due_time"] = new_due_time
                    changes.append("due_time")
                except ValueError:
                    pass

        if self.spinbutton_priority.get_value_as_int() != self.task.priority:
            kwargs["new_priority"] = self.spinbutton_priority.get_value_as_int()
            changes.append("priority")

        listbox_list_ids = {
            row.list_id
            for row in self.listbox_lists.get_children()
            if hasattr(row, "list_id")
        }
        task_list_ids = set(self.task.lists)
        if listbox_list_ids != task_list_ids:
            added = listbox_list_ids - task_list_ids
            removed = task_list_ids - listbox_list_ids
            for list_id in added:
                journal.add_task_to_list(self.task.task_id, list_id)
            for list_id in removed:
                journal.delete_task_from_list(self.task.task_id, list_id)
            changes.append("lists")

        journal.update_task(self.task.task_id, **kwargs)
        # reload the task
        self._task = journal.get_task(self.task.task_id)

        self._load_view_mode()
        self.stack_mode.set_visible_child_name("view")
        self._load_edit_mode()

        if changes:
            modified_attributes = Gtk.ListStore(str)
            for change in changes:
                modified_attributes.append([change])
            self.emit("task_modified", modified_attributes)

    def _time_is_new_or_changed(self, time_name: str):
        time = getattr(self.task, f"{time_name}_time")
        entry_date = getattr(self, f"entry_{time_name}_date")
        entry_time = getattr(self, f"entry_{time_name}_time")
        if time is None:
            is_new = (entry_date.get_text() != "") or (entry_time.get_text() != "")
            is_changed = False
        else:
            is_new = False
            local_time = time.astimezone()
            date_changed = entry_date.get_text() != "{0:%Y}-{0:%m}-{0:%d}".format(
                local_time
            )
            time_changed = entry_time.get_text() != "{0:%H}:{0:%M}:{0:%S}".format(
                local_time
            )
            is_changed = date_changed or time_changed
        return is_new or is_changed

    @GObject.Signal()
    def task_deleted(self):
        pass

    @GObject.Signal(arg_types=(Gtk.ListStore,))
    def task_modified(self, modified_attributes):
        self.reload()
