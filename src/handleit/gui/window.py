from dataclasses import dataclass
from datetime import datetime, timezone
import enum
import logging
from pathlib import Path
from typing import Optional, List, Union

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Handy", "1")
from gi.repository import Gtk, Gio, Handy

from ..core import Journal, CoreTaskList, TaskRelationship
from ..io.sqlite import create_new_database
from .widgets import TaskRow, TaskDetailView, TaskList


@enum.unique
class View(enum.Enum):
    LIST = 1
    SUBTASKS = 2
    DETAIL = 3


@dataclass
class ViewState:
    view: View
    disp_id: Union[CoreTaskList, int]
    name: Optional[str] = None


@Gtk.Template(resource_path="/org/wrightsman/HandleIt/ui/window.ui")
class HandleItWindow(Handy.ApplicationWindow):
    __gtype_name__ = "HandleItWindow"

    _journal: Optional[Journal] = None
    _view_history: List[ViewState]

    leaflet_main = Gtk.Template.Child()

    sidebar = Gtk.Template.Child()

    search_bar = Gtk.Template.Child()

    headerbar_leaf_tasks = Gtk.Template.Child()
    stack_views = Gtk.Template.Child()
    view_list = Gtk.Template.Child()
    view_task = Gtk.Template.Child()

    button_sidebar_edit = Gtk.Template.Child()
    button_back = Gtk.Template.Child()
    button_sort = Gtk.Template.Child()
    button_taskedit = Gtk.Template.Child()
    button_search = Gtk.Template.Child()

    tasklist = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._view_history = []

        action_new_file = Gio.SimpleAction.new("file.new", None)
        action_new_file.connect("activate", self._on_new_file)
        self.add_action(action_new_file)

        action_open_file = Gio.SimpleAction.new("file.open", None)
        action_open_file.connect("activate", self._on_open_file)
        self.add_action(action_open_file)

        self.sidebar.connect("list_deleted", self._on_sidebar_list_deleted)
        self.sidebar.stack_mode.connect(
            "notify::visible_child_name", self._on_sidebar_mode_switch
        )
        self.sidebar.mode_view.connect("row-activated", self._on_sidebar_row_activated)
        self.sidebar.mode_view.connect("row-selected", self._on_sidebar_row_selected)

        self.leaflet_main.connect("notify::folded", self._on_leaflet_fold)

        self.tasklist.connect("row-activated", self._on_task_row_activated)
        self.tasklist.connect("subtasks_requested", self._on_subtasks_requested)
        self.tasklist.connect("new_task_created", self._on_new_task)
        self.tasklist.connect("task_modified", self._on_task_row_modified)

        self.view_task.connect("task_deleted", self._on_task_deleted)
        self.view_task.connect("task_modified", self._on_task_modified)
        self.view_task.stack_mode.connect(
            "notify::visible-child-name", self._on_view_task_mode_switch
        )

        self.search_bar.connect(
            "notify::search-mode-enabled", self._on_search_mode_toggled
        )
        self.stack_views.connect(
            "notify::visible-child-name", self._on_view_stack_mode_switch
        )

    def do_destroy(self):
        """ Close the Journal database connection, if it exists, on window destruction """
        if self._journal:
            self._journal.close()
        Handy.ApplicationWindow.do_destroy(self)

    @property
    def journal(self):
        return self._journal

    def _load_list_view(self, list_id: Union[CoreTaskList, int], list_name: str):
        # stop search
        if self.button_search.get_active():
            self.button_search.set_active(False)
        # load the tasks into the list box
        self.tasklist.load_tasks(
            self._journal.get_list_tasks(list_id),
            show_new_task_row=(
                list_id not in {CoreTaskList.COMPLETED, CoreTaskList.TRASH}
            ),
        )
        # set the active stack view
        self.stack_views.set_visible_child_name("view_list")
        # set the title
        self.headerbar_leaf_tasks.set_title(list_name)
        # reset history
        self._view_history = [ViewState(View.LIST, list_id, list_name)]
        self._set_button_visibility()

    def _load_subtasks_view(self, task_id: int, reload=False, history=True):
        # stop search
        if self.button_search.get_active():
            self.button_search.set_active(False)

        subtask_ids = self._journal.get_task(task_id).subtasks
        self.tasklist.load_tasks(self._journal.get_tasks(subtask_ids))

        if history:
            self._view_history.append(ViewState(View.SUBTASKS, task_id))

        if not reload:
            self.stack_views.set_visible_child_name("view_list")
            self.headerbar_leaf_tasks.set_title("Subtasks")
            self._set_button_visibility()

    def _load_detail_view(self, task_id: int, reload=False, history=True):
        task = self._journal.get_task(task_id)
        self.view_task.load_task(task)

        if history:
            self._view_history.append(ViewState(View.DETAIL, task_id))

        if not reload:
            self.stack_views.set_visible_child_name("view_task")
            self.headerbar_leaf_tasks.set_title("Task")
            self._set_button_visibility()

        # stop search
        if self.button_search.get_active():
            self.button_search.set_active(False)

    def _on_sidebar_row_activated(self, list_box, row):
        self.leaflet_main.set_visible_child_name("tasks")

    def _on_sidebar_row_selected(self, list_box, row):
        self._load_list_view(row.list_id, row.list_name)

    def _on_sidebar_list_deleted(self, sidebar: Gtk.Box, list_id: int):
        if list_id in [
            v.disp_id for v in filter(lambda v: v.view == View.LIST, self._view_history)
        ]:
            # we have the deleted list loaded in the view history, change to pending
            self.sidebar.mode_view.select_row(
                self.sidebar.mode_view.get_row_at_index(0)
            )
        elif self._view_history[-1].view == View.DETAIL:
            # we are in the task detail view, reload it
            self.view_task.reload()

    def _on_task_row_activated(self, list_box, row):
        self._load_detail_view(row.task.task_id)

    def _on_subtasks_requested(self, list_box, task_id: int):
        self._load_subtasks_view(task_id)

    @Gtk.Template.Callback()
    def _on_search_submitted(self, entry_search):
        if self.journal is not None:
            self.tasklist.load_tasks(self.journal.search_tasks(entry_search.get_text()))

    def _on_new_task(self, task_list, task_description: str):
        # create the task
        new_task_id = self._journal.add_task(task_description)
        current_view = self._view_history[-1]
        if current_view.view == View.LIST:
            # add task to current list too
            if not isinstance(current_view.disp_id, CoreTaskList):
                self._journal.add_task_to_list(new_task_id, current_view.disp_id)
        elif current_view.view == View.SUBTASKS:
            # add new task as subtask to currently-loaded parent
            self._journal.add_task_relationship(
                current_view.disp_id, new_task_id, TaskRelationship.PARENT
            )
        self.sidebar.update_counts()
        self._reload_view()

    def _on_task_deleted(self, task_view: TaskDetailView):
        self._journal.delete_task(task_view.task.task_id)
        trash_row = self.sidebar.mode_view.get_row_at_index(2)
        # load Trash list
        self._load_list_view(trash_row.list_id, trash_row.list_name)
        # select Trash in sidebar
        self.sidebar.mode_view.select_row(trash_row)
        # update counts
        self.sidebar.update_counts()

    def _on_task_modified(
        self, task_view: TaskDetailView, modified_attributes: Gio.ListStore
    ):
        modified_attributes = [row[0] for row in modified_attributes]
        if "completion_time" in modified_attributes:
            self.sidebar.update_counts()
        if "is_trashed" in modified_attributes:
            self.sidebar.update_counts()
        if "lists" in modified_attributes:
            self.sidebar.update_counts()

    def _on_task_row_modified(
        self, tasklist: TaskList, row: TaskRow, modified_attribute: str
    ) -> None:
        if modified_attribute == "completion_time":
            if row.task.completion_time is None:
                self._journal.update_task(
                    row.task.task_id, new_completion_time=datetime.now(timezone.utc)
                )
                if (
                    self._view_history[-1].disp_id == CoreTaskList.PENDING
                ) or isinstance(self._view_history[-1].disp_id, int):
                    # destroy the row if completed and in pending or a custom list
                    row.destroy()
            else:
                self._journal.update_task(row.task.task_id, new_completion_time=None)
                if self._view_history[-1].disp_id == CoreTaskList.COMPLETED:
                    # destroy the row if uncompleted and in completed
                    row.destroy()
            self.sidebar.update_counts()

    def _on_sidebar_mode_switch(self, stack, visible_child_name):
        self.button_sidebar_edit.set_active(stack.get_visible_child_name() == "edit")

    @Gtk.Template.Callback()
    def _on_sidebar_edit_toggled(self, button):
        if not button.get_active():
            lists = {l.list_id: l.name for l in self.journal.lists}
            # going back to view mode; check for updated entries, update lists, and reload
            changed = False
            for list_id, entry_text in self.sidebar.get_entry_texts().items():
                if lists[list_id] != entry_text:
                    changed = True
                    self.journal.update_list(list_id, new_name=entry_text)
            if changed:
                self.sidebar.load_lists(self.journal.lists)
        self.sidebar.set_edit_mode(button.get_active())

    def _set_button_visibility(self):
        if self._view_history:
            current_view = self._view_history[-1]
            if self.leaflet_main.get_folded():
                self.button_back.set_visible(True)
            else:
                if current_view.view in {View.DETAIL, View.SUBTASKS}:
                    self.button_back.set_visible(True)
                else:
                    self.button_back.set_visible(False)

            if current_view.view == View.DETAIL:
                self.button_search.set_visible(False)
                self.button_taskedit.set_visible(True)
                # self.button_sort.set_visible(False)
            else:
                if (
                    current_view.view == View.LIST
                    and current_view.disp_id == CoreTaskList.PENDING
                ):
                    # only allow searching in Pending list for now
                    self.button_search.set_visible(True)
                else:
                    self.button_search.set_visible(False)
                self.button_taskedit.set_visible(False)
                # self.button_sort.set_visible(True)

    def _on_leaflet_fold(self, obj, pspec):
        self._set_button_visibility()

    def _on_view_task_mode_switch(self, stack, visible_child_name):
        self.button_taskedit.set_active(stack.get_visible_child_name() == "edit")

    def _on_view_stack_mode_switch(self, stack, visible_child_name):
        if stack.get_visible_child_name() != "view_task":
            # make sure task view returns to view mode after leaving it
            self.view_task.stack_mode.set_visible_child_name("view")

    def _reload_view(self):
        current_view = self._view_history[-1]
        if current_view.view == View.LIST:
            self.tasklist.load_tasks(self._journal.get_list_tasks(current_view.disp_id))
        elif current_view.view == View.SUBTASKS:
            self._load_subtasks_view(current_view.disp_id, reload=True)
        elif current_view.view == View.DETAIL:
            self._load_detail_view(current_view.disp_id, reload=True)

    def _load_previous_view(self):
        current_view = self._view_history[-1]

        if current_view.view == View.LIST:
            self.leaflet_main.set_visible_child_name("sidebar")

        elif current_view.view == View.SUBTASKS:
            previous_view = self._view_history[-2]
            if previous_view.view == View.LIST:
                self._load_list_view(previous_view.disp_id, previous_view.name)
            elif previous_view.view == View.SUBTASKS:
                self._load_subtasks_view(previous_view.disp_id, history=False)
                self._view_history.pop()

        elif current_view.view == View.DETAIL:
            previous_view = self._view_history[-2]
            if previous_view.view == View.LIST:
                self._load_list_view(previous_view.disp_id, previous_view.name)
            elif previous_view.view == View.SUBTASKS:
                self._load_subtasks_view(previous_view.disp_id, history=False)
                self._view_history.pop()

        self._set_button_visibility()

    @Gtk.Template.Callback()
    def _on_back_clicked(self, button):
        self._load_previous_view()

    @Gtk.Template.Callback()
    def _on_taskedit_toggled(self, button):
        self.view_task.set_edit_mode(button.get_active())

    def _on_new_file(self, action, param):
        file_dialog = Gtk.FileChooserDialog(
            "Please choose a task database",
            self,
            Gtk.FileChooserAction.SAVE,
            (_("_Cancel"), Gtk.ResponseType.CANCEL, _("_Create"), Gtk.ResponseType.OK,),
        )

        response = file_dialog.run()
        created = False
        if response == Gtk.ResponseType.OK:
            logging.info(f"Creating new file '{file_dialog.get_filename()}'")
            db_path = Path(file_dialog.get_filename())
            db_exists = db_path.exists()
            overwrite_db = False
            if db_exists:
                overwrite_dialog = Gtk.Dialog(
                    "Confirm File Overwrite",
                    self,
                    0,
                    (_("_No"), Gtk.ResponseType.NO, _("_Yes"), Gtk.ResponseType.YES),
                )
                overwrite_dialog.get_content_area().add(
                    Gtk.Label(
                        "A file already exists at this location! Are you sure you want to overwrite it?"
                    )
                )
                overwrite_dialog.show_all()
                overwrite_db = overwrite_dialog.run() == Gtk.ResponseType.YES
                overwrite_dialog.destroy()
                if overwrite_db:
                    db_path.unlink()
                    create_new_database(db_path)
                    created = True
            else:
                create_new_database(db_path)
                created = True

        # load the newly-created database
        if created:
            self._load_journal(db_path)

        file_dialog.destroy()

    def _load_journal(self, path):
        logging.info(f"Opening file '{path}'")
        self._journal = Journal(path)

        self.sidebar.load_lists(self._journal.lists)

        if (self.sidebar.mode_view.get_selected_row() is not None) and (
            self.sidebar.mode_view.get_selected_row().list_id == CoreTaskList.PENDING
        ):
            # just reload if already on pending
            self._reload_view()
        else:
            # select the pending row
            self.sidebar.mode_view.select_row(
                self.sidebar.mode_view.get_row_at_index(0)
            )

        self.sidebar.show_all()

        self.button_sidebar_edit.set_sensitive(True)
        self.button_search.set_sensitive(True)

    def _on_open_file(self, action, param):
        dialog = Gtk.FileChooserDialog(
            "Please choose a task database",
            self,
            Gtk.FileChooserAction.OPEN,
            (_("_Cancel"), Gtk.ResponseType.CANCEL, _("_Open"), Gtk.ResponseType.OK,),
        )

        filter_sqlite3 = Gtk.FileFilter()
        filter_sqlite3.set_name("SQLite3 Databases")
        filter_sqlite3.add_mime_type("application/x-sqlite3")
        dialog.add_filter(filter_sqlite3)

        filter_any = Gtk.FileFilter()
        filter_any.set_name("Any file")
        filter_any.add_pattern("*")
        dialog.add_filter(filter_any)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            self._load_journal(Path(dialog.get_filename()))
        dialog.destroy()

    @Gtk.Template.Callback()
    def _on_search_toggled(self, button):
        self.search_bar.set_search_mode(button.props.active)

    def _on_search_mode_toggled(self, search_bar, search_mode_enabled):
        self.button_search.set_active(self.search_bar.get_search_mode())
        if not self.search_bar.get_search_mode():
            # reload the view
            self._reload_view()
