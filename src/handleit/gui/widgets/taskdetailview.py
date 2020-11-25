from datetime import datetime, timezone

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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

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
        self.entry_description.set_text(self.task.description)
        if self.task.notes is not None:
            self.textview_notes.get_buffer().set_text(self.task.notes)

        self.mode_edit.show_all()

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
        # check what has changed
        kwargs = {}
        modified_attributes = Gtk.ListStore(str)
        if self.entry_description.get_text() != self.task.description:
            kwargs["new_description"] = self.entry_description.get_text()
            modified_attributes.append(["description"])

        if self.textview_notes.get_buffer().props.text != self.task.notes:
            kwargs["new_notes"] = self.textview_notes.get_buffer().props.text
            modified_attributes.append(["notes"])

        journal = self.get_toplevel().journal
        journal.update_task(self.task.task_id, **kwargs)
        self._task = journal.get_task(self.task.task_id)

        self._load_view_mode()
        self.stack_mode.set_visible_child_name("view")
        self.emit("task_modified", modified_attributes)

    @GObject.Signal()
    def task_deleted(self):
        pass

    @GObject.Signal(arg_types=(Gtk.ListStore,))
    def task_modified(self, modified_attributes):
        pass
