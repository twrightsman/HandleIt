from typing import List

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Handy", "1")

from gi.repository import GObject, Gtk, Gio, Handy

from ...core import Task


@Gtk.Template(resource_path="/org/wrightsman/HandleIt/ui/taskrow.ui")
class TaskRow(Gtk.ListBoxRow):
    __gtype_name__ = "TaskRow"

    button_checkbox = Gtk.Template.Child()
    label_description = Gtk.Template.Child()

    def __init__(self, task: Task, **kwargs):
        super().__init__(**kwargs)

        self._task = task
        self.button_checkbox.set_active(task.completion_time is not None)
        self.label_description.set_label(task.description)

        self.button_checkbox.connect("toggled", self._on_checkbox_toggled)

    @property
    def task(self):
        return self._task

    def _on_checkbox_toggled(self, button):
        self.emit("checkbox_toggled")

    @GObject.Signal()
    def checkbox_toggled(self):
        pass

    @GObject.Signal()
    def subtasks_requested(self):
        pass


class TaskList(Gtk.ListBox):
    __gtype_name__ = "TaskList"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def load_tasks(self, tasks: List[Task], show_new_task_row: bool = True):
        # remove all current tasks from list
        self.foreach(lambda row: row.destroy())

        for task in tasks:
            taskrow = TaskRow(task)
            taskrow.connect("subtasks_requested", self._on_subtasks_requested)
            taskrow.connect("checkbox_toggled", self._on_row_checkbox_toggled)
            self.add(taskrow)

        if show_new_task_row:
            # add new task creation row
            new_task_row = Gtk.ListBoxRow(activatable=False)
            new_task_entry = Gtk.Entry(placeholder_text="Create a new task...")
            new_task_row.add(new_task_entry)
            new_task_entry.connect("activate", self._on_create_task)
            self.add(new_task_row)

        self.show_all()

    def _on_create_task(self, new_task_entry: Gtk.Entry):
        description = new_task_entry.get_text()
        if description != "":
            self.emit("new_task_created", description)

    def _on_row_checkbox_toggled(self, row: TaskRow):
        self.emit("task_modified", row, "completion_time")

    @GObject.Signal(arg_types=(TaskRow, str))
    def task_modified(self, row, modified_attribute):
        pass

    @GObject.Signal(arg_types=(str,))
    def new_task_created(self, task_description):
        pass

    @GObject.Signal(arg_types=(int,))
    def subtasks_requested(self, task_id):
        pass

    def _on_subtasks_requested(self, taskrow: "TaskRow"):
        self.emit("subtasks_requested", taskrow.task.task_id)
