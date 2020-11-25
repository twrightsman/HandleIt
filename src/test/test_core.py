import datetime
import sqlite3
from typing import Union
import unittest

from handleit.core import Journal, TaskRelationship
from handleit.io.sqlite import create_new_database


class TestJournal(unittest.TestCase):
    def setUp(self):
        self.temp_db = sqlite3.connect(":memory:")
        create_new_database(self.temp_db)
        populate_test_db(self.temp_db)
        self.journal = Journal(self.temp_db)

    def test_get_list_tasks(self):
        tasks = self.journal.get_list_tasks(6)
        self.assertEqual(tasks[1].description, "Learn Spanish")

    def test_get_list_count(self):
        self.assertEqual(self.journal.get_list_count(6), 2)
        self.assertEqual(
            self.journal.get_list_count(2), 1, msg="Not filtering to only pending tasks"
        )
        self.assertEqual(self.journal.get_list_count(1000), 0)

    def test_lists(self):
        journal_lists = [l.name for l in self.journal.lists]
        self.assertIn("Scheduled", journal_lists)

    def test_get_list(self):
        self.assertEqual(self.journal.get_list(4).name, "Waiting")
        self.assertIsNone(self.journal.get_list(1000))

    def test_get_lists(self):
        lists = self.journal.get_lists([1, 2])
        self.assertEqual({"Focus", "Inbox"}, {l.name for l in lists})
        self.assertEqual([], self.journal.get_lists([]))

    def test_add_list(self):
        list_id = self.journal.add_list("Testing", "testing")
        new_list = self.journal.get_list(list_id)
        self.assertEqual(new_list.name, "Testing")
        self.assertEqual(new_list.icon, "testing")
        self.assertEqual(new_list.list_id, list_id)

    def test_update_list(self):
        list_id = self.journal.add_list("OldAndBusted", "test")
        self.journal.update_list(list_id, new_name="NewHotness", new_icon="benz")
        updated_list = self.journal.get_list(list_id)
        self.assertEqual(updated_list.name, "NewHotness")
        self.assertEqual(updated_list.icon, "benz")
        self.assertEqual(updated_list.list_id, list_id)

    def test_swap_list_positions(self):
        list3_old_pos = self.journal.get_list(3).position
        list5_old_pos = self.journal.get_list(5).position
        self.journal.swap_list_positions(3, 5)
        self.assertEqual(self.journal.get_list(3).position, list5_old_pos)
        self.assertEqual(self.journal.get_list(5).position, list3_old_pos)

    def test_delete_list(self):
        self.journal.delete_list(3)
        deleted_list = self.journal.get_list(3)
        self.assertIsNone(deleted_list)

    def test_get_task(self):
        task1 = self.journal.get_task(1)
        self.assertEqual(task1.description, "Call mom")
        self.assertIsNone(task1.notes)
        self.assertEqual(task1.priority, 5)
        self.assertEqual(
            task1.creation_time,
            datetime.datetime.fromisoformat("2020-06-01T17:30:05-04:00"),
        )
        self.assertIsNone(task1.completion_time)
        self.assertEqual(
            task1.start_time,
            datetime.datetime.fromisoformat("2020-06-15T12:30:00-04:00"),
        )
        self.assertIsNone(task1.due_time)
        self.assertFalse(task1.is_trashed)
        self.assertIn(3, task1.lists)

    def test_get_tasks(self):
        tasks = self.journal.get_tasks([1, 3])
        task1 = tasks[0]
        self.assertEqual(task1.description, "Call mom")
        self.assertIsNone(task1.notes)
        self.assertEqual(task1.priority, 5)
        self.assertEqual(
            task1.creation_time,
            datetime.datetime.fromisoformat("2020-06-01T17:30:05-04:00"),
        )
        self.assertIsNone(task1.completion_time)
        self.assertEqual(
            task1.start_time,
            datetime.datetime.fromisoformat("2020-06-15T12:30:00-04:00"),
        )
        self.assertIsNone(task1.due_time)
        self.assertFalse(task1.is_trashed)
        self.assertIn(3, task1.lists)

        task3 = tasks[1]
        self.assertEqual(task3.description, "Build shed")
        self.assertIsNone(task3.notes)
        self.assertEqual(task3.priority, -1)
        self.assertEqual(
            task3.creation_time,
            datetime.datetime.fromisoformat("2020-06-01T17:35:00-04:00"),
        )
        self.assertIsNone(task3.completion_time)
        self.assertEqual(
            task3.start_time, datetime.datetime.fromisoformat("2020-06-10")
        )
        self.assertEqual(
            task3.due_time, datetime.datetime.fromisoformat("2020-06-25T17:00:00-04:00")
        )
        self.assertFalse(task3.is_trashed)
        self.assertFalse(task3.lists)

    def test_add_task(self):
        new_task_id = self.journal.add_task("Test task")
        new_task = self.journal.get_task(new_task_id)
        self.assertEqual(new_task.description, "Test task")

    def test_update_task(self):
        task_id = self.journal.add_task("Testing")
        new_time = datetime.datetime.now()
        self.journal.update_task(
            task_id,
            new_description="NewTesting",
            new_priority=5,
            new_creation_time=new_time,
            is_trashed=True,
            new_notes="TestNotes",
            new_completion_time=new_time,
            new_due_time=new_time,
            new_start_time=new_time,
        )
        updated_task = self.journal.get_task(task_id)
        self.assertEqual(updated_task.description, "NewTesting")
        self.assertEqual(updated_task.priority, 5)
        self.assertEqual(updated_task.creation_time, new_time)
        self.assertTrue(updated_task.is_trashed)
        self.assertEqual(updated_task.notes, "TestNotes")
        self.assertEqual(updated_task.completion_time, new_time)
        self.assertEqual(updated_task.due_time, new_time)
        self.assertEqual(updated_task.start_time, new_time)

        self.journal.update_task(
            task_id,
            new_notes=None,
            new_completion_time=None,
            new_due_time=None,
            new_start_time=None,
        )
        updated_task = self.journal.get_task(task_id)
        self.assertIsNone(updated_task.notes)
        self.assertIsNone(updated_task.completion_time)
        self.assertIsNone(updated_task.due_time)
        self.assertIsNone(updated_task.start_time)

    def test_delete_task(self):
        self.journal.delete_task(1)
        self.assertIsNone(self.journal.get_task(1))

    def test_get_task_lists(self):
        # pylint: disable=protected-access
        self.assertEqual({1, 3}, set(self.journal._get_task_lists(1)[1]))
        self.assertEqual({2}, set(self.journal._get_task_lists(4)[4]))

        # test vectorized function
        lists = self.journal._get_task_lists([1, 4])
        self.assertEqual({1, 3}, set(lists[1]))
        self.assertEqual({2}, set(lists[4]))

    def test_add_task_to_list(self):
        # pylint: disable=protected-access
        self.journal.add_task_to_list(1, 4)
        self.assertEqual({1, 3, 4}, set(self.journal._get_task_lists(1)[1]))

    def test_delete_task_from_list(self):
        # pylint: disable=protected-access
        self.journal.delete_task_from_list(1, 3)
        self.assertEqual({1}, set(self.journal._get_task_lists(1)[1]))

    def test_get_task_tags(self):
        # pylint: disable=protected-access
        tag1_dict = self.journal._get_task_tags(1)
        tag12_dict = self.journal._get_task_tags([1, 2])
        self.assertEqual(tag1_dict[1], {"@phone"})
        self.assertEqual(tag12_dict[2], {"@errands"})

    def test_add_task_tag(self):
        self.journal.add_task_tag(1, "test")
        self.assertIn("test", self.journal.get_task(1).tags)

    def test_delete_task_tag(self):
        self.journal.delete_task_tag(2, "@errands")
        self.assertNotIn("@errands", self.journal.get_task(2).tags)

    def test_get_tag(self):
        self.assertEqual(self.journal.get_tag(1).name, "@errands")
        self.assertIsNone(self.journal.get_tag(1000))
        self.assertRaises(TypeError, self.journal.get_tag, tag=0.5)

    def test_add_tag(self):
        new_tag_id = self.journal.add_tag(name="test")
        self.assertEqual(self.journal.get_tag(new_tag_id).name, "test")

    def test_update_tag(self):
        self.journal.update_tag(1, "test_update", new_tag_color="#000000")
        updated_tag = self.journal.get_tag(1)
        self.assertEqual(updated_tag.name, "test_update")
        self.assertEqual(updated_tag.color, "#000000")

        self.journal.update_tag(1, new_tag_name=None, new_tag_color=None)
        updated_tag = self.journal.get_tag(1)
        self.assertEqual(updated_tag.name, "test_update")
        self.assertIsNone(updated_tag.color)

    def test_delete_tag(self):
        self.journal.delete_tag("@errands")
        self.assertIsNone(self.journal.get_tag("@errands"))
        self.assertNotIn("@errands", self.journal.get_task(2).tags)

    def test_get_task_attributes(self):
        # pylint: disable=protected-access
        task_attrs = self.journal._get_task_attributes([1, 5])
        self.assertIn(1, task_attrs.keys())
        self.assertIn(5, task_attrs.keys())
        self.assertEqual(task_attrs[1]["time-needed-minutes"], 32.5)
        self.assertIs(float, type(task_attrs[1]["time-needed-minutes"]))
        self.assertEqual(task_attrs[5]["energy-level"], 3)

    def test_add_task_attribute(self):
        self.journal.add_task_attribute(1, "energy-level", 2)
        task1 = self.journal.get_task(1)
        self.assertEqual(task1.attributes["energy-level"], 2)
        self.assertRaises(
            TypeError,
            self.journal.add_task_attribute,
            task_id=2,
            key="test",
            value={"set"},
        )

    def test_delete_task_attribute(self):
        self.journal.delete_task_attribute(1, "time-needed-minutes")
        task1 = self.journal.get_task(1)
        self.assertNotIn("time-needed-minutes", task1.attributes)

    def test_update_task_attribute(self):
        self.journal.update_task_attribute(1, "time-needed-minutes", 22)
        task1 = self.journal.get_task(1)
        self.assertEqual(task1.attributes["time-needed-minutes"], 22)
        self.assertIs(int, type(task1.attributes["time-needed-minutes"]))

    def test_swap_task_positions(self):
        task3_old_pos = self.journal.get_task(3).position
        task5_old_pos = self.journal.get_task(5).position
        self.journal.swap_task_positions(3, 5)
        self.assertEqual(self.journal.get_task(3).position, task5_old_pos)
        self.assertEqual(self.journal.get_task(5).position, task3_old_pos)

    def test_get_task_relationships(self):
        self.assertEqual(
            {TaskRelationship.PARENT}, self.journal.get_task_relationships(3, 4)
        )

    def test_add_task_relationship(self):
        self.journal.add_task_relationship(5, 6, TaskRelationship.DEPENDENCY)
        self.assertEqual(
            {TaskRelationship.DEPENDENCY}, self.journal.get_task_relationships(5, 6)
        )

    def test_delete_task_relationship(self):
        self.journal.delete_task_relationship(3, 4, TaskRelationship.PARENT)
        self.assertFalse(self.journal.get_task_relationships(3, 4))

    def test_update_task_relationship(self):
        self.journal.update_task_relationship(3, 4, TaskRelationship.DEPENDENCY)
        self.assertEqual(
            {TaskRelationship.DEPENDENCY}, self.journal.get_task_relationships(3, 4)
        )

    def test_get_subtasks(self):
        # pylint: disable=protected-access
        self.assertEqual({4, 5, 6, 7, 8}, set(self.journal._get_subtasks(3)[3]))
        self.assertEqual({13, 14}, set(self.journal._get_subtasks(12)[12]))
        self.assertEqual([], self.journal._get_subtasks(1)[1])

        # test for bug where dependents show up in subtasks
        self.assertNotIn(3, self.journal._get_subtasks([9])[9])

        # test vectorized function
        subtasks = self.journal._get_subtasks([3, 12, 1])
        self.assertEqual({4, 5, 6, 7, 8}, set(subtasks[3]))
        self.assertEqual({13, 14}, set(subtasks[12]))
        self.assertEqual([], subtasks[1])

    def test_get_parent(self):
        # pylint: disable=protected-access
        self.assertEqual(3, self.journal._get_parent(4)[4])
        self.assertEqual(3, self.journal._get_parent(6)[6])
        self.assertEqual(12, self.journal._get_parent(14)[14])
        self.assertIsNone(self.journal._get_parent(2)[2])

        # test vectorized function
        parents = self.journal._get_parent([4, 6, 14, 2])
        self.assertEqual(3, parents[4])
        self.assertEqual(3, parents[6])
        self.assertEqual(12, parents[14])
        self.assertIsNone(parents[2])

    def test_get_dependencies(self):
        # pylint: disable=protected-access
        self.assertIn(3, self.journal._get_dependencies(9)[9])
        self.assertIn(15, self.journal._get_dependencies(14)[14])

        # test vectorized function
        dependencies = self.journal._get_dependencies([9, 14])
        self.assertIn(3, dependencies[9])
        self.assertIn(15, dependencies[14])

    def test_get_dependents(self):
        # pylint: disable=protected-access
        self.assertIn(9, self.journal._get_dependents(3)[3])
        self.assertIn(14, self.journal._get_dependents(15)[15])

        # test vectorized function
        dependents = self.journal._get_dependents([3, 15])
        self.assertIn(9, dependents[3])
        self.assertIn(14, dependents[15])

    def test_search_tasks(self):
        self.assertEqual(
            {3, 5, 8}, {t.task_id for t in self.journal.search_tasks("shed")}
        )

    def tearDown(self):
        self.journal.close()
        self.temp_db.close()


def populate_test_db(path: Union[str, sqlite3.Connection]) -> None:
    if isinstance(path, sqlite3.Connection):
        conn = path
    else:
        conn = sqlite3.connect(path)

    with conn:
        conn.executescript(
            """
            INSERT INTO metadata (property, value)
            VALUES
                ("journal_name", "Test1");

            INSERT INTO lists (name, icon, position)
            VALUES
                ("Focus", "emblem-default-symbolic", 1),
                ("Inbox", "emblem-default-symbolic", 2),
                ("Next", "emblem-default-symbolic", 3),
                ("Waiting", "emblem-default-symbolic", 4),
                ("Scheduled", "emblem-default-symbolic", 5),
                ("Someday/Maybe", "emblem-default-symbolic", 6);

            INSERT INTO tags (name, color)
            VALUES
                ("@errands", "#308bcc"),
                ("@phone", "#44c95c"),
                ("home remodel 2020", "#8244c9"),
                ("@home", "#993333"),
                ("project", NULL),
                ("work", "#cc0066");

            INSERT INTO tasks (position, description, notes, priority, creation_dtm, completion_dtm, start_dtm, due_dtm, is_trashed)
            VALUES
                (1, "Call mom", NULL, 5, "2020-06-01T17:30:05-04:00", NULL, "2020-06-15T12:30:00-04:00", NULL, FALSE),
                (2, "Buy groceries", "eggs, flour, sugar", 1, "2020-06-01T17:30:15-04:00", NULL, NULL, NULL, FALSE),
                (3, "Build shed", NULL, -1, "2020-06-01T17:35:00-04:00", NULL, "2020-06-10", "2020-06-25T17:00:00-04:00", FALSE),
                (4, "Measure yard", NULL, 0, "2020-06-01T17:45:00-04:00", "2020-06-01T18:15:00-04:00", NULL, NULL, FALSE),
                (5, "Design shed", NULL, 0, "2020-06-01T17:46:00-04:00", NULL, NULL, NULL, FALSE),
                (6, "Buy lumber", NULL, 0, "2020-06-01T17:47:00-04:00", NULL, NULL, NULL, FALSE),
                (7, "Buy tools", NULL, 0, "2020-06-01T17:48:00-04:00", NULL, NULL, NULL, FALSE),
                (8, "Assemble shed", NULL, 0, "2020-06-01T17:49:00-04:00", NULL, NULL, NULL, FALSE),
                (9, "Purchase lawnmower", NULL, 0, "2020-06-01T17:55:00-04:00", NULL, NULL, NULL, FALSE),
                (10, "Install cool new game", NULL, 0, "2020-06-01T17:10:00-04:00", NULL, NULL, NULL, TRUE),
                (11, "Clean kitchen", NULL, 2, "2020-06-02T17:20:00-04:00", NULL, NULL, NULL, FALSE),
                (12, "Organize basement", NULL, -1, "2020-06-02T17:25:00-04:00", NULL, NULL, NULL, FALSE),
                (13, "Buy storage containers", NULL, 0, "2020-06-02T12:30:00-04:00", NULL, NULL, NULL, FALSE),
                (14, "Donate old TV", NULL, -1, "2020-06-01T19:23:00-04:00", NULL, NULL, NULL, FALSE),
                (15, "Waiting on Charlie to tell me if he wants TV", NULL, 0, "2020-06-03T10:08:20-04:00", NULL, NULL, NULL, FALSE),
                (16, "Learn Spanish", NULL, 0, "2020-06-01T15:02:00-04:00", NULL, NULL, NULL, FALSE),
                (17, "Call boss back on TPS reports", NULL, 0, "2020-06-02T09:32:47-04:00", NULL, NULL, NULL, FALSE),
                (18, "Buy christmas gifts", "Mom - scarf, dad - mug", 0, "2020-06-05T13:30:25-04:00", NULL, NULL, NULL, FALSE);

            INSERT INTO task_lists (list_id, task_id)
            VALUES
                (1, 1),
                (3, 1),
                (3, 2),
                (2, 4),
                (6, 9),
                (2, 10),
                (1, 11),
                (4, 15),
                (6, 16),
                (2, 18);

            INSERT INTO task_tags (task_id, tag_id)
            VALUES
                (1, 2),
                (2, 1),
                (3, 3),
                (3, 4),
                (3, 5),
                (4, 4),
                (6, 1),
                (7, 1),
                (10, 4),
                (11, 4),
                (12, 4),
                (13, 1),
                (14, 1),
                (17, 2),
                (17, 6);

            INSERT INTO task_relations (task_from_id, task_to_id, relationship)
            VALUES
                (3, 4, "parent_of"),
                (3, 5, "parent_of"),
                (3, 6, "parent_of"),
                (3, 7, "parent_of"),
                (3, 8, "parent_of"),
                (9, 3, "blocked_by"),
                (12, 13, "parent_of"),
                (12, 14, "parent_of"),
                (14, 15, "blocked_by");

            INSERT INTO task_attributes (task_id, attr_key, attr_type, attr_value)
            VALUES
                (1, 'time-needed-minutes', 'float', '32.5'),
                (5, 'energy-level', 'int', '3')
        """
        )

    if not isinstance(path, sqlite3.Connection):
        conn.close()


if __name__ == "__main__":
    unittest.main()
