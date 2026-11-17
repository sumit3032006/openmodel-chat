import tempfile
import unittest
from pathlib import Path

from database.chat_database import DEFAULT_TITLE, ChatDatabase
from services.exporter import safe_filename, to_markdown, to_text


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = ChatDatabase(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        self.tmp.cleanup()

    def test_conversation_lifecycle(self):
        c = self.db.create_conversation("a/b:free")
        self.assertEqual(c.title, DEFAULT_TITLE)
        self.db.rename_conversation(c.id, "  Hello   world ")
        self.assertEqual(self.db.get_conversation(c.id).title, "Hello world")
        with self.assertRaises(ValueError):
            self.db.rename_conversation(c.id, "   ")
        self.db.set_conversation_model(c.id, "x/y")
        self.assertEqual(self.db.get_conversation(c.id).model_id, "x/y")
        self.db.delete_conversation(c.id)
        self.assertIsNone(self.db.get_conversation(c.id))

    def test_messages_and_cascade(self):
        c = self.db.create_conversation("a/b")
        self.db.add_message(c.id, "user", "hi")
        m = self.db.add_message(c.id, "assistant", "yo", model_id="a/b", response_ms=1200,
                                prompt_tokens=3, completion_tokens=4, total_tokens=7)
        self.assertEqual([x.role for x in self.db.get_messages(c.id)], ["user", "assistant"])
        self.assertEqual(self.db.get_last_message(c.id).id, m.id)
        self.db.delete_message(m.id)
        self.assertEqual(len(self.db.get_messages(c.id)), 1)
        self.db.clear_conversation(c.id)
        self.assertEqual(self.db.get_messages(c.id), [])
        self.db.add_message(c.id, "user", "again")
        self.db.delete_conversation(c.id)
        self.assertEqual(self.db.stats()["user_messages"], 0)

    def test_search_title_and_content_with_wildcards(self):
        a = self.db.create_conversation("m/x", "Python tips")
        b = self.db.create_conversation("m/x", "Cooking")
        self.db.add_message(b.id, "user", "100% real_value")
        self.assertEqual([c.id for c in self.db.list_conversations("python")], [a.id])
        self.assertEqual([c.id for c in self.db.list_conversations("100%")], [b.id])
        self.assertEqual(self.db.list_conversations("%"), [b])
        self.assertEqual(len(self.db.list_conversations()), 2)

    def test_settings_roundtrip(self):
        self.assertEqual(self.db.get_setting("theme", "light"), "light")
        self.db.set_setting("theme", "dark")
        self.db.set_setting("theme", "dark2")
        self.assertEqual(self.db.get_setting("theme"), "dark2")

    def test_stats_use_only_recorded_values(self):
        c = self.db.create_conversation("a/b")
        self.db.add_message(c.id, "assistant", "x", model_id="a/b", response_ms=1000, total_tokens=10)
        self.db.add_message(c.id, "assistant", "y", model_id="a/b", response_ms=3000)
        s = self.db.stats()
        row = s["by_model"][0]
        self.assertEqual((row["replies"], row["avg_response_ms"], row["total_tokens"]), (2, 2000, 10))

    def test_no_api_key_column_or_table(self):
        with self.db._conn() as conn:
            cols = [r[1] for r in conn.execute("SELECT * FROM pragma_table_info('messages')")]
            tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        self.assertFalse(any("key" in c.lower() for c in cols))
        self.assertNotIn("api_keys", tables)

    def test_export(self):
        c = self.db.create_conversation("a/b", "My chat")
        self.db.add_message(c.id, "user", "Question?")
        self.db.add_message(c.id, "assistant", "Answer.", model_id="a/b")
        msgs = self.db.get_messages(c.id)
        name = lambda mid: "Model A" if mid else "?"
        md = to_markdown(self.db.get_conversation(c.id), msgs, name)
        txt = to_text(self.db.get_conversation(c.id), msgs, name)
        self.assertIn("# My chat", md)
        self.assertIn("Model A", md)
        self.assertIn("Question?", txt)
        self.assertEqual(safe_filename("a/b: c?", "md"), "a_b_c.md")
        self.assertEqual(safe_filename("///", "txt"), "conversation.txt")


if __name__ == "__main__":
    unittest.main()
