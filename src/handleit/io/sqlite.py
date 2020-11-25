import sqlite3
from typing import Union

from ..core import Journal


def create_new_database(path: Union[str, sqlite3.Connection]) -> None:
    if isinstance(path, sqlite3.Connection):
        conn = path
    else:
        conn = sqlite3.connect(path)

    with conn as c:
        c.executescript(
            """
            PRAGMA foreign_keys = ON;
            PRAGMA user_version = 1;

            CREATE TABLE metadata (
                property TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE tasks (
                task_id INTEGER PRIMARY KEY,
                position INTEGER NOT NULL UNIQUE,
                description TEXT NOT NULL,
                notes TEXT,
                priority INTEGER NOT NULL DEFAULT 0,
                creation_dtm TEXT NOT NULL,
                completion_dtm TEXT,
                due_dtm TEXT,
                start_dtm TEXT,
                is_trashed INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE lists (
                list_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                icon TEXT,
                position INTEGER NOT NULL UNIQUE
            );

            CREATE TABLE task_lists (
                list_id INTEGER NOT NULL,
                task_id INTEGER NOT NULL,
                FOREIGN KEY (list_id)
                    REFERENCES lists (list_id),
                FOREIGN KEY (task_id)
                    REFERENCES tasks (task_id),
                PRIMARY KEY (list_id, task_id)
            );

            CREATE TABLE tags (
                tag_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                color TEXT
            );

            CREATE TABLE task_tags (
                task_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                FOREIGN KEY (task_id)
                    REFERENCES tasks (task_id),
                FOREIGN KEY (tag_id)
                    REFERENCES tags (tag_id),
                PRIMARY KEY (task_id, tag_id)
            );

            CREATE TABLE task_attributes (
                task_id INTEGER NOT NULL,
                attr_key TEXT NOT NULL,
                attr_type TEXT NOT NULL,
                attr_value TEXT NOT NULL,
                FOREIGN KEY (task_id)
                    REFERENCES tasks (task_id),
                PRIMARY KEY (task_id, attr_key)
            );

            CREATE TABLE task_relations (
                task_from_id INTEGER NOT NULL,
                task_to_id INTEGER NOT NULL,
                relationship TEXT NOT NULL,
                FOREIGN KEY (task_from_id)
                    REFERENCES tasks (task_id),
                FOREIGN KEY (task_to_id)
                    REFERENCES tasks (task_id),
                PRIMARY KEY (task_from_id, task_to_id, relationship)
            );

            CREATE TABLE notifications (
                task_id INTEGER NOT NULL,
                dtm TEXT NOT NULL,
                FOREIGN KEY (task_id)
                    REFERENCES tasks (task_id),
                PRIMARY KEY (task_id, dtm)
            );
        """
        )

    if not isinstance(path, sqlite3.Connection):
        conn.close()
