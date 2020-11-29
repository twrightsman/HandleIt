import builtins
from collections import defaultdict
from datetime import datetime, timezone
import enum
from pathlib import Path
import sqlite3
from typing import Optional, List, Union, Dict, Any, Set, overload


TaskAttribute = Union[str, int, float, bool]


@enum.unique
class CoreTaskList(enum.Enum):
    PENDING = -1
    COMPLETED = -2
    TRASH = -3


@enum.unique
class TaskRelationship(enum.Enum):
    PARENT = "parent_of"
    DEPENDENCY = "blocked_by"


class Task:
    def __init__(
        self,
        task_id: int,
        position: int,
        description: str = "",
        notes: Optional[str] = None,
        priority: int = 0,
        creation_time: Optional[datetime] = None,
        completion_time: Optional[datetime] = None,
        due_time: Optional[datetime] = None,
        start_time: Optional[datetime] = None,
        is_trashed: bool = False,
        lists: Optional[List[int]] = None,
        tags: Optional[Set[str]] = None,
        attributes: Optional[Dict[str, TaskAttribute]] = None,
        subtasks: Optional[List[int]] = None,
        parent: Optional[int] = None,
        dependencies: Optional[List[int]] = None,
        dependents: Optional[List[int]] = None,
    ) -> None:
        self.task_id = task_id
        self.position = position
        self.description = description
        self.notes = notes
        self.priority = priority
        self.creation_time = (
            creation_time if creation_time is not None else datetime.now(timezone.utc)
        )
        self.completion_time = completion_time
        self.due_time = due_time
        self.start_time = start_time
        self.is_trashed = is_trashed
        self._lists = lists if lists is not None else []
        self._tags = tags if tags is not None else []
        self._attributes = attributes if attributes is not None else {}
        self._subtasks = subtasks if subtasks is not None else []
        self._parent = parent
        self._dependencies = dependencies if dependencies is not None else []
        self._dependents = dependents if dependents is not None else []

    @property
    def lists(self):
        return self._lists

    @property
    def tags(self):
        return self._tags

    @property
    def attributes(self):
        return self._attributes

    @property
    def subtasks(self):
        return self._subtasks

    @property
    def parent(self):
        return self._parent

    @property
    def dependencies(self):
        return self._dependencies

    @property
    def dependents(self):
        return self._dependents

    @staticmethod
    def from_sqlite_row(row: sqlite3.Row) -> "Task":
        return Task(
            row["task_id"],
            row["position"],
            row["description"],
            row["notes"],
            int(row["priority"]),
            datetime.fromisoformat(row["creation_dtm"]),
            datetime.fromisoformat(row["completion_dtm"])
            if row["completion_dtm"]
            else None,
            datetime.fromisoformat(row["due_dtm"]) if row["due_dtm"] else None,
            datetime.fromisoformat(row["start_dtm"]) if row["start_dtm"] else None,
            bool(row["is_trashed"]),
        )


class TaskTag:
    def __init__(self, tag_id: int, name: str, color: str):
        self.tag_id = tag_id
        self.name = name
        self.color = color

    @staticmethod
    def from_sqlite_row(row: sqlite3.Row) -> "TaskTag":
        return TaskTag(row["tag_id"], row["name"], row["color"])


class TaskList:
    def __init__(self, list_id: int, name: str, icon: str, position: int):
        self.list_id = list_id
        self.name = name
        self.icon = icon
        self.position = position

    @staticmethod
    def from_sqlite_row(row: sqlite3.Row) -> "TaskList":
        return TaskList(row["list_id"], row["name"], row["icon"], row["position"])


class Journal:

    _valid_attribute_types = {"str", "int", "float", "bool"}

    def __init__(self, db_path: Union[Path, sqlite3.Connection]):
        if isinstance(db_path, sqlite3.Connection):
            self._conn = db_path
        else:
            self._conn = sqlite3.connect(db_path)

        self._conn.row_factory = sqlite3.Row
        self._closed = False

    def close(self):
        self._conn.close()
        self._closed = True

    def _get_task_lists(self, task_ids: Union[int, List[int]]) -> Dict[int, List[int]]:
        if isinstance(task_ids, int):
            task_ids = [task_ids]

        # generate a parameterized query with a number of placeholders equal to the number of tasks for which lists are being searched for
        query = f"SELECT task_id, list_id FROM task_lists WHERE task_id IN ( {','.join(['?'] * len(task_ids))} )"
        task_lists = defaultdict(list)
        for row in self._conn.execute(query, task_ids):
            task_lists[row["task_id"]].append(row["list_id"])
        return task_lists

    def _postprocess_list_tasks(self, tasks: List[Task]) -> List[Task]:
        """ Assign subtasks, dependencies, tags, and attributes to Tasks """
        task_ids = [task.task_id for task in tasks]
        lists = self._get_task_lists(task_ids)
        tags = self._get_task_tags(task_ids)
        attrs = self._get_task_attributes(task_ids)
        subtasks = self._get_subtasks(task_ids)
        parents = self._get_parent(task_ids)
        dependencies = self._get_dependencies(task_ids)
        dependents = self._get_dependents(task_ids)
        for task in tasks:
            task._lists = lists[task.task_id]
            task._tags = tags[task.task_id]
            task._attributes = attrs[task.task_id]
            task._subtasks = subtasks[task.task_id]
            task._parent = parents[task.task_id]
            task._dependencies = dependencies[task.task_id]
            task._dependents = dependents[task.task_id]
        return tasks

    def _get_pending_tasks(self) -> List[Task]:
        return self._postprocess_list_tasks(
            [
                Task.from_sqlite_row(row)
                for row in self._conn.execute(
                    'SELECT tasks.* FROM tasks LEFT JOIN task_relations ON tasks.task_id = task_relations.task_to_id WHERE (task_relations.relationship IS NULL OR task_relations.relationship != "parent_of") AND completion_dtm IS NULL AND NOT is_trashed'
                )
            ]
        )

    def _get_completed_tasks(self) -> List[Task]:
        return self._postprocess_list_tasks(
            [
                Task.from_sqlite_row(row)
                for row in self._conn.execute(
                    "SELECT * FROM tasks WHERE completion_dtm IS NOT NULL AND NOT is_trashed"
                )
            ]
        )

    def _get_trashed_tasks(self) -> List[Task]:
        return self._postprocess_list_tasks(
            [
                Task.from_sqlite_row(row)
                for row in self._conn.execute("SELECT * FROM tasks WHERE is_trashed")
            ]
        )

    def get_list_tasks(self, list_id: Union[CoreTaskList, int]) -> List[Task]:
        """ Look up top-level tasks (no parents) of a given list """
        if isinstance(list_id, CoreTaskList):
            if list_id == CoreTaskList.PENDING:
                return self._get_pending_tasks()
            elif list_id == CoreTaskList.COMPLETED:
                return self._get_completed_tasks()
            elif list_id == CoreTaskList.TRASH:
                return self._get_trashed_tasks()
            else:
                raise ValueError(f"Invalid CoreTaskList: '{list_id}'")
        elif isinstance(list_id, int):
            return self._postprocess_list_tasks(
                [
                    Task.from_sqlite_row(row)
                    for row in self._conn.execute(
                        'SELECT tasks.* FROM tasks LEFT JOIN task_relations ON tasks.task_id = task_relations.task_to_id LEFT JOIN task_lists ON tasks.task_id = task_lists.task_id WHERE (task_relations.relationship IS NULL OR task_relations.relationship != "parent_of") AND task_lists.list_id = ? AND completion_dtm IS NULL AND NOT is_trashed',
                        (list_id,),
                    )
                ]
            )
        else:
            raise TypeError(
                "List IDs must be either integers or a built-in CoreTaskList"
            )

    def _get_pending_count(self) -> int:
        return int(
            self._conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE completion_dtm IS NULL AND NOT is_trashed"
            ).fetchone()[0]
        )

    def _get_completed_count(self) -> int:
        return int(
            self._conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE completion_dtm IS NOT NULL AND NOT is_trashed"
            ).fetchone()[0]
        )

    def _get_trashed_count(self) -> int:
        return int(
            self._conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE is_trashed"
            ).fetchone()[0]
        )

    @overload
    def get_list_count(self, list_id: List[int]) -> Dict[int, int]:
        pass

    @overload
    def get_list_count(self, list_id: Union[CoreTaskList, int]) -> int:
        pass

    def get_list_count(self, list_id):
        if isinstance(list_id, CoreTaskList):
            if list_id == CoreTaskList.PENDING:
                count = self._get_pending_count()
            elif list_id == CoreTaskList.COMPLETED:
                count = self._get_completed_count()
            elif list_id == CoreTaskList.TRASH:
                count = self._get_trashed_count()
        elif isinstance(list_id, int):
            count = int(
                self._conn.execute(
                    "SELECT COUNT(*) FROM task_lists LEFT JOIN tasks ON task_lists.task_id = tasks.task_id WHERE task_lists.list_id = ? AND NOT tasks.is_trashed AND tasks.completion_dtm IS NULL",
                    (list_id,),
                ).fetchone()[0]
            )
        elif isinstance(list_id, list):
            if all([isinstance(e, int) for e in list_id]):
                count = {l: 0 for l in list_id}
                query = f"SELECT task_lists.list_id, COUNT(*) FROM task_lists LEFT JOIN tasks ON task_lists.task_id = tasks.task_id WHERE task_lists.list_id IN ( {', '.join((['?'] * len(list_id)))} ) AND NOT tasks.is_trashed AND tasks.completion_dtm IS NULL GROUP BY task_lists.list_id"
                for row in self._conn.execute(query, list_id):
                    count[row["list_id"]] = row[1]
            else:
                raise TypeError("Can only search for lists of integer list IDs")
        else:
            raise TypeError(
                "List IDs must be either integers or a built-in CoreTaskList"
            )

        return count

    @property
    def lists(self) -> List[TaskList]:
        return [
            TaskList.from_sqlite_row(row)
            for row in self._conn.execute("SELECT * FROM lists ORDER BY position")
        ]

    def get_list(self, list_id: int) -> Optional[TaskList]:
        l = self._conn.execute(
            "SELECT * FROM lists WHERE list_id = ?", (list_id,)
        ).fetchone()
        if l is not None:
            return TaskList.from_sqlite_row(l)
        return None

    def get_lists(self, list_ids: List[int]) -> List[TaskList]:
        query = f"SELECT * FROM lists WHERE list_id IN ( {', '.join((['?'] * len(list_ids)))} )"
        return [
            TaskList.from_sqlite_row(row) for row in self._conn.execute(query, list_ids)
        ]

    def add_list(self, name: str, icon: Optional[str] = None) -> int:
        """ Add a list to the end of user lists """
        # get current highest position of lists
        max_list_id = self._conn.execute("SELECT MAX(list_id) FROM lists").fetchone()[0]
        if max_list_id is None:
            max_list_id = 0

        with self._conn:
            self._conn.execute(
                "INSERT INTO lists (list_id, name, icon, position) VALUES (?, ?, ?, ?)",
                (max_list_id + 1, name, icon, max_list_id + 1),
            )

        return max_list_id + 1

    def update_list(
        self,
        list_id: int,
        new_name: Optional[str] = None,
        new_icon: Optional[str] = None,
    ) -> None:
        """ Update the name or icon of a list """
        changes = []

        # only update provided values
        if new_name is not None:
            changes.append(("name", new_name))
        if new_icon is not None:
            changes.append(("icon", new_icon))

        if changes:
            query = "UPDATE lists SET {set_string} WHERE list_id = ?"
            with self._conn:
                query = query.format(
                    set_string=(
                        ", ".join(" = ".join([change[0], "?"]) for change in changes)
                    )
                )
                self._conn.execute(
                    query, tuple([change[1] for change in changes] + [list_id])
                )

    def swap_list_positions(self, list1_id: int, list2_id: int) -> None:
        list1 = self.get_list(list1_id)
        list2 = self.get_list(list2_id)
        max_position = self._conn.execute("SELECT MAX(position) FROM lists").fetchone()[
            0
        ]

        if (list1 is not None) and (list2 is not None):
            with self._conn:
                query = "UPDATE lists SET position = ? WHERE list_id = ?"
                # set list1 position to end
                self._conn.execute(query, (max_position + 1, list1_id))
                # set list2 position to list1
                self._conn.execute(query, (list1.position, list2_id))
                # set list1 position to list2
                self._conn.execute(query, (list2.position, list1_id))

    def delete_list(self, list_id: int) -> None:
        with self._conn:
            # delete task-list relationships part of the to-be-deleted list
            self._conn.execute("DELETE FROM task_lists WHERE list_id = ?", (list_id,))
            # delete the list
            self._conn.execute("DELETE FROM lists WHERE list_id = ?", (list_id,))

    def get_task(self, task_id: int) -> Optional[Task]:
        row = self._conn.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
        if row is not None:
            task = Task.from_sqlite_row(row)
            return self._postprocess_list_tasks([task])[0]
        return None

    def get_tasks(self, task_ids: List[int]) -> List[Task]:
        query = f"SELECT * FROM tasks WHERE task_id IN ( {', '.join((['?'] * len(task_ids)))} )"
        tasks = [
            Task.from_sqlite_row(row) for row in self._conn.execute(query, task_ids)
        ]
        return self._postprocess_list_tasks(tasks)

    def add_task(
        self,
        description: str = "",
        notes: Optional[str] = None,
        priority: int = 0,
        completion_time: Optional[datetime] = None,
        due_time: Optional[datetime] = None,
        start_time: Optional[datetime] = None,
        is_trashed: bool = False,
        tags: Optional[List[str]] = None,
        attributes: Optional[Dict[str, Any]] = None,
        lists: Optional[List[int]] = None,
    ) -> int:
        """ Add a task to the database and return its new ID """

        if tags:
            raise NotImplementedError
        if attributes:
            raise NotImplementedError
        if lists:
            raise NotImplementedError

        # get current max task_id
        max_task_id = self._conn.execute("SELECT MAX(task_id) FROM tasks").fetchone()[0]
        if max_task_id is None:
            max_task_id = 0

        # add the new task
        task_dict = {
            "task_id": max_task_id + 1,
            "position": max_task_id + 1,
            "creation_dtm": datetime.now(timezone.utc).isoformat(),
            "description": description,
            "notes": notes,
            "priority": priority,
            "completion_dtm": completion_time,
            "due_dtm": due_time,
            "start_dtm": start_time,
            "is_trashed": is_trashed,
        }
        with self._conn:
            self._conn.execute(
                "INSERT INTO tasks (task_id, position, creation_dtm, description, notes, priority, completion_dtm, due_dtm, start_dtm, is_trashed) VALUES (:task_id, :position, :creation_dtm, :description, :notes, :priority, :completion_dtm, :due_dtm, :start_dtm, :is_trashed)",
                task_dict,
            )

        return max_task_id + 1

    def update_task(
        self,
        task_id: int,
        new_description: Optional[str] = None,
        new_priority: Optional[int] = None,
        new_creation_time: Optional[datetime] = None,
        is_trashed: Optional[bool] = None,
        **kwargs,
    ) -> None:
        """
        Update the attributes of a task

        The following nullable parameters are optionally set using the kwargs:

        - new_notes (str)
        - new_completion_time (datetime)
        - new_due_time (datetime)
        - new_start_time (datetime)
        """
        changes = []
        if new_description is not None:
            changes.append(("description", new_description))
        if new_priority is not None:
            changes.append(("priority", new_priority))
        if new_creation_time is not None:
            changes.append(("creation_dtm", new_creation_time.isoformat()))
        if is_trashed is not None:
            changes.append(("is_trashed", int(is_trashed)))

        if "new_notes" in kwargs:
            changes.append(("notes", kwargs["new_notes"]))
        if "new_completion_time" in kwargs:
            if kwargs["new_completion_time"] is None:
                new_completion_time = None
            else:
                new_completion_time = kwargs["new_completion_time"].isoformat()
            changes.append(("completion_dtm", new_completion_time))
        if "new_due_time" in kwargs:
            if kwargs["new_due_time"] is None:
                new_due_time = None
            else:
                new_due_time = kwargs["new_due_time"].isoformat()
            changes.append(("due_dtm", new_due_time))
        if "new_start_time" in kwargs:
            if kwargs["new_start_time"] is None:
                new_start_time = None
            else:
                new_start_time = kwargs["new_start_time"].isoformat()
            changes.append(("start_dtm", new_start_time))

        if changes:
            query = "UPDATE tasks SET {set_string} WHERE task_id = ?"
            with self._conn:
                query = query.format(
                    set_string=(
                        ", ".join(" = ".join([change[0], "?"]) for change in changes)
                    )
                )
                self._conn.execute(
                    query, tuple([change[1] for change in changes] + [task_id])
                )

    def add_task_to_list(self, task_id: int, list_id: int) -> None:
        # TODO verify both task and list exist
        with self._conn:
            self._conn.execute(
                "INSERT INTO task_lists (list_id, task_id) VALUES (?, ?)",
                (list_id, task_id),
            )

    def delete_task_from_list(self, task_id: int, list_id: int) -> None:
        with self._conn:
            self._conn.execute(
                "DELETE FROM task_lists WHERE list_id = ? AND task_id = ?",
                (list_id, task_id),
            )

    def _get_task_tags(self, task_ids: Union[int, List[int]]) -> Dict[int, Set[str]]:
        if isinstance(task_ids, int):
            task_ids = [task_ids]
        # generate a parameterized query with a number of placeholders equal to the number of tasks for which tags are being searched for
        query = f"SELECT task_tags.task_id, tags.name FROM tags JOIN task_tags ON tags.tag_id = task_tags.tag_id WHERE task_tags.task_id IN ( {','.join(['?'] * len(task_ids))} )"
        task_tags = defaultdict(set)
        for row in self._conn.execute(query, task_ids):
            task_tags[row["task_id"]].add(row["name"])
        return task_tags

    def delete_task(self, task_id: int) -> None:
        with self._conn:
            # delete list task relationship
            self._conn.execute("DELETE FROM task_lists WHERE task_id = ?", (task_id,))
            # delete tag task relationship
            self._conn.execute("DELETE FROM task_tags WHERE task_id = ?", (task_id,))
            # delete relationships between any other tasks
            self._conn.execute(
                "DELETE FROM task_relations WHERE task_from_id = ? OR task_to_id = ?",
                (task_id, task_id),
            )
            # delete attribute task relationship
            self._conn.execute(
                "DELETE FROM task_attributes WHERE task_id = ?", (task_id,)
            )
            # delete the task
            self._conn.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))

    def add_task_tag(self, task_id: int, tag: str) -> None:
        """ Adds the tag to the task, creating a new tag if it doesn't exist """
        tag_id = self.get_tag(tag)
        if tag_id is None:
            tag_id = self.add_tag(tag)

        # add the tag to the task
        with self._conn:
            self._conn.execute(
                "INSERT INTO task_tags (task_id, tag_id) VALUES (?, ?)",
                (task_id, tag_id),
            )

    def delete_task_tag(self, task_id: int, tag: str) -> None:
        tag_id = self.get_tag(tag).tag_id
        if tag_id is not None:
            with self._conn:
                self._conn.execute(
                    "DELETE FROM task_tags WHERE task_id = ? AND tag_id = ?",
                    (task_id, tag_id),
                )

    def get_tag(self, tag: Union[int, str]) -> Optional[TaskTag]:
        if isinstance(tag, int):
            t = self._conn.execute(
                "SELECT * FROM tags WHERE tag_id = ?", (tag,)
            ).fetchone()
        elif isinstance(tag, str):
            t = self._conn.execute(
                "SELECT * FROM tags WHERE name = ?", (tag,)
            ).fetchone()
        else:
            raise TypeError(
                f"Must get tags by integer tag id or string tag name, not '{type(tag)}'"
            )
        if t is not None:
            return TaskTag.from_sqlite_row(t)
        return None

    def add_tag(self, name: str, color: Optional[str] = None) -> int:
        max_tag_id = self._conn.execute("SELECT MAX(tag_id) FROM tags").fetchone()[0]
        if max_tag_id is None:
            max_tag_id = 0

        with self._conn:
            self._conn.execute(
                "INSERT INTO tags (tag_id, name, color) VALUES (?, ?, ?)",
                (max_tag_id + 1, name, color),
            )

        return max_tag_id + 1

    def update_tag(self, tag_id: int, new_tag_name: Optional[str], **kwargs) -> None:
        changes = []

        if new_tag_name is not None:
            changes.append(("name", new_tag_name))

        if "new_tag_color" in kwargs:
            changes.append(("color", kwargs["new_tag_color"]))

        if changes:
            query = "UPDATE tags SET {set_string} WHERE tag_id = ?"
            with self._conn:
                query = query.format(
                    set_string=(
                        ", ".join(" = ".join([change[0], "?"]) for change in changes)
                    )
                )
                self._conn.execute(
                    query, tuple([change[1] for change in changes] + [tag_id])
                )

    def delete_tag(self, tag: Union[str, int]) -> None:
        tag = self.get_tag(tag)
        if tag is not None:
            with self._conn:
                self._conn.execute(
                    "DELETE FROM task_tags WHERE tag_id = ?", (tag.tag_id,)
                )
                self._conn.execute("DELETE FROM tags WHERE tag_id = ?", (tag.tag_id,))

    def _get_task_attributes(
        self, task_ids: Union[int, List[int]]
    ) -> Dict[int, Dict[str, TaskAttribute]]:
        if isinstance(task_ids, int):
            task_ids = [task_ids]

        task_attrs = defaultdict(dict)
        query = f"SELECT * FROM task_attributes WHERE task_id IN ( {','.join(['?'] * len(task_ids))} )"
        for row in self._conn.execute(query, task_ids):
            if row["attr_type"] not in self._valid_attribute_types:
                raise TypeError(
                    f"Task {row['task_id']} has invalid type '{row['attr_type']}'. (Valid types are str, int, float, and bool)"
                )
            task_attrs[row["task_id"]][row["attr_key"]] = getattr(
                builtins, row["attr_type"]
            )(row["attr_value"])
        return task_attrs

    def add_task_attribute(self, task_id: int, key: str, value: TaskAttribute) -> None:
        value_type = type(value).__name__
        if value_type not in self._valid_attribute_types:
            raise TypeError(
                f"Task attribute values can only be str, int, float, or bool, not '{value_type}'"
            )
        with self._conn:
            self._conn.execute(
                "INSERT into task_attributes (task_id, attr_key, attr_type, attr_value) VALUES (?, ?, ?, ?)",
                (task_id, key, value_type, value),
            )

    def delete_task_attribute(self, task_id: int, key: str) -> None:
        with self._conn:
            self._conn.execute(
                "DELETE FROM task_attributes WHERE task_id = ? AND attr_key = ?",
                (task_id, key),
            )

    def update_task_attribute(
        self, task_id: int, key: str, new_value: TaskAttribute
    ) -> None:
        new_value_type = type(new_value).__name__
        if new_value_type not in self._valid_attribute_types:
            raise TypeError(
                f"Task attribute values can only be str, int, float, or bool, not '{new_value_type}'"
            )
        with self._conn:
            self._conn.execute(
                "UPDATE task_attributes SET attr_value = ?, attr_type = ? WHERE task_id = ? AND attr_key = ?",
                (new_value, new_value_type, task_id, key),
            )

    def swap_task_positions(self, task1_id: int, task2_id: int):
        task1 = self.get_task(task1_id)
        task2 = self.get_list(task2_id)
        max_position = self._conn.execute("SELECT MAX(position) FROM tasks").fetchone()[
            0
        ]

        if (task1 is not None) and (task2 is not None):
            with self._conn:
                query = "UPDATE tasks SET position = ? WHERE task_id = ?"
                # set task1 position to end
                self._conn.execute(query, (max_position + 1, task1_id))
                # set task2 position to task1
                self._conn.execute(query, (task1.position, task2_id))
                # set task1 position to task2
                self._conn.execute(query, (task2.position, task1_id))

    def get_task_relationships(self, task_from_id, task_to_id) -> Set[TaskRelationship]:
        return set(
            [
                TaskRelationship(row["relationship"])
                for row in self._conn.execute(
                    "SELECT relationship FROM task_relations WHERE task_from_id = ? AND task_to_id = ?",
                    (task_from_id, task_to_id),
                )
            ]
        )

    def add_task_relationship(
        self, task_from_id: int, task_to_id: int, relationship: TaskRelationship
    ) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO task_relations (task_from_id, task_to_id, relationship) VALUES (?, ?, ?)",
                (task_from_id, task_to_id, relationship.value),
            )

    def delete_task_relationship(
        self, task_from_id: int, task_to_id: int, relationship: TaskRelationship
    ) -> None:
        with self._conn:
            self._conn.execute(
                "DELETE FROM task_relations WHERE task_from_id = ? AND task_to_id = ? AND relationship = ?",
                (task_from_id, task_to_id, relationship.value),
            )

    def update_task_relationship(
        self, task_from_id: int, task_to_id: int, new_relationship: TaskRelationship
    ) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE task_relations SET relationship = ? WHERE task_from_id = ? AND task_to_id = ?",
                (new_relationship.value, task_from_id, task_to_id),
            )

    def _get_subtasks(self, task_id: Union[int, List[int]]) -> Dict[int, List[int]]:
        if isinstance(task_id, int):
            task_id = [task_id]

        subtasks = defaultdict(list)
        query = f"SELECT task_to_id, task_from_id FROM task_relations WHERE relationship = 'parent_of' AND task_from_id IN ( {','.join(['?'] * len(task_id))} )"
        for row in self._conn.execute(query, task_id):
            subtasks[row["task_from_id"]].append(row["task_to_id"])
        return subtasks

    def _get_parent(self, task_id: Union[int, List[int]]) -> Dict[int, Optional[int]]:
        if isinstance(task_id, int):
            task_id = [task_id]

        parents = {t: None for t in task_id}
        query = f"SELECT task_from_id, task_to_id FROM task_relations WHERE relationship = 'parent_of' AND task_to_id IN ( {','.join(['?'] * len(task_id))} )"
        for row in self._conn.execute(query, task_id):
            parents[row["task_to_id"]] = row["task_from_id"]
        return parents

    def _get_dependencies(self, task_id: Union[int, List[int]]) -> Dict[int, List[int]]:
        if isinstance(task_id, int):
            task_id = [task_id]

        dependencies = defaultdict(list)
        query = f"SELECT task_to_id, task_from_id FROM task_relations WHERE relationship = 'blocked_by' AND task_from_id IN ( {','.join(['?'] * len(task_id))} )"
        for row in self._conn.execute(query, task_id):
            dependencies[row["task_from_id"]].append(row["task_to_id"])
        return dependencies

    def _get_dependents(self, task_id: Union[int, List[int]]) -> Dict[int, List[int]]:
        """ Get tasks depending on this/these task(s) """
        if isinstance(task_id, int):
            task_id = [task_id]

        dependents = defaultdict(list)
        query = f"SELECT task_from_id, task_to_id FROM task_relations WHERE relationship = 'blocked_by' AND task_to_id IN ( {','.join(['?'] * len(task_id))} )"
        for row in self._conn.execute(query, task_id):
            dependents[row["task_to_id"]].append(row["task_from_id"])
        return dependents

    def search_tasks(self, query: str) -> List[Task]:
        return [
            Task.from_sqlite_row(row)
            for row in self._conn.execute(
                "SELECT * FROM tasks WHERE description LIKE ? OR notes LIKE ?",
                ("%" + query + "%", "%" + query + "%"),
            )
        ]
