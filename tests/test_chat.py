import asyncio
import tempfile
import unittest
from pathlib import Path

from database.chat_database import ChatDatabase
from services.chat_service import ChatService, make_title
from services.env_file import remove_api_key, save_api_key
from services.errors import ChatError, from_error_payload, map_exception, redact
from services.key_store import KeyStore
from services.openrouter_client import StreamChunk, Usage, parse_usage

MODEL = "vendor/model:free"
SECRET = "sk-or-v1-abcdef1234567890abcdef"


class FakeClient:
    """Stands in for OpenRouterClient. Records what it was asked to send."""

    def __init__(self, chunks=None, error=None, hang=False):
        self.chunks, self.error, self.hang = chunks or [], error, hang
        self.calls = []

    async def stream_chat(self, model_id, messages, temperature=None):
        self.calls.append((model_id, messages, temperature))
        for chunk in self.chunks:
            yield chunk
        if self.error:
            raise self.error
        if self.hang:
            await asyncio.sleep(30)


class FakeApiError(Exception):
    def __init__(self, status, body=None):
        super().__init__("boom")
        self.status_code, self.body = status, body


class ChatServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = ChatDatabase(Path(self.tmp.name) / "t.db")
        self.keys = KeyStore(SECRET)
        self.conv = self.db.create_conversation(MODEL)

    def tearDown(self):
        self.tmp.cleanup()

    def service(self, client):
        return ChatService(self.db, self.keys, lambda key: client)

    async def collect(self, svc, **kw):
        return [e async for e in svc.generate(self.conv.id, MODEL, **kw)]

    def test_streams_and_saves_real_metrics(self):
        client = FakeClient([StreamChunk("Hel"), StreamChunk("lo"),
                             StreamChunk(usage=Usage(5, 2, 7), finish_reason="stop")])
        svc = self.service(client)
        svc.add_user_message(self.conv.id, "Hi there")
        events = asyncio.run(self.collect(svc, system_prompt="Be brief", temperature=0.3))
        self.assertEqual([e.kind for e in events], ["delta", "delta", "final"])
        msg = events[-1].message
        self.assertEqual((msg.content, msg.model_id, msg.total_tokens), ("Hello", MODEL, 7))
        self.assertIsNotNone(msg.response_ms)
        model, payload, temp = client.calls[0]
        self.assertEqual(payload[0], {"role": "system", "content": "Be brief"})
        self.assertEqual(temp, 0.3)

    def test_no_fabricated_tokens(self):
        svc = self.service(FakeClient([StreamChunk("ok")]))
        svc.add_user_message(self.conv.id, "q")
        msg = asyncio.run(self.collect(svc))[-1].message
        self.assertIsNone(msg.total_tokens)
        self.assertIsNone(msg.prompt_tokens)

    def test_switching_models_keeps_history(self):
        svc = self.service(FakeClient([StreamChunk("A1")]))
        svc.add_user_message(self.conv.id, "first")
        asyncio.run(self.collect(svc))
        second = FakeClient([StreamChunk("B1")])
        svc2 = self.service(second)
        svc2.add_user_message(self.conv.id, "second")

        async def run():
            return [e async for e in svc2.generate(self.conv.id, "other/model:free")]

        asyncio.run(run())
        model, payload, _ = second.calls[0]
        self.assertEqual(model, "other/model:free")
        self.assertEqual([m["content"] for m in payload], ["first", "A1", "second"])

    def test_missing_key_and_bad_model(self):
        svc = ChatService(self.db, KeyStore(""), lambda k: FakeClient())
        svc.add_user_message(self.conv.id, "q")
        with self.assertRaises(ChatError) as ctx:
            asyncio.run(self.collect(svc))
        self.assertEqual(ctx.exception.code, "no_key")
        svc = self.service(FakeClient())

        async def bad():
            return [e async for e in svc.generate(self.conv.id, "bad id")]

        with self.assertRaises(ChatError) as ctx:
            asyncio.run(bad())
        self.assertEqual(ctx.exception.code, "bad_model")

    def test_empty_response_is_an_error(self):
        svc = self.service(FakeClient([StreamChunk(finish_reason="stop")]))
        svc.add_user_message(self.conv.id, "q")
        with self.assertRaises(ChatError) as ctx:
            asyncio.run(self.collect(svc))
        self.assertEqual(ctx.exception.code, "empty_response")

    def test_midstream_error_saves_partial(self):
        err = ChatError("rate", code="rate_limited", retryable=True)
        svc = self.service(FakeClient([StreamChunk("partial")], error=err))
        svc.add_user_message(self.conv.id, "q")
        with self.assertRaises(ChatError):
            asyncio.run(self.collect(svc))
        last = self.db.get_last_message(self.conv.id)
        self.assertEqual((last.content, last.status), ("partial", "error"))

    def test_cancel_saves_partial_as_stopped(self):
        svc = self.service(FakeClient([StreamChunk("part")], hang=True))
        svc.add_user_message(self.conv.id, "q")

        async def run():
            async def consume():
                async for _ in svc.generate(self.conv.id, MODEL):
                    pass

            task = asyncio.create_task(consume())
            await asyncio.sleep(0.05)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

        asyncio.run(run())
        last = self.db.get_last_message(self.conv.id)
        self.assertEqual((last.content, last.status), ("part", "stopped"))

    def test_user_message_validation_and_title(self):
        svc = self.service(FakeClient())
        with self.assertRaises(ChatError):
            svc.add_user_message(self.conv.id, "   ")
        with self.assertRaises(ChatError):
            svc.add_user_message(self.conv.id, "x" * 20_001)
        svc.add_user_message(self.conv.id, "  What is   the capital of France?  ")
        self.assertEqual(self.db.get_conversation(self.conv.id).title, "What is the capital of France?")
        self.assertTrue(make_title("word " * 40).endswith("\u2026"))


class ErrorMappingTests(unittest.TestCase):
    def test_status_codes(self):
        expect = {401: "invalid_key", 402: "insufficient_credits", 403: "forbidden",
                  404: "model_unavailable", 429: "rate_limited", 503: "provider_error",
                  400: "bad_request"}
        for status, code in expect.items():
            self.assertEqual(map_exception(FakeApiError(status)).code, code)
        self.assertTrue(map_exception(FakeApiError(429)).retryable)

    def test_network_and_timeout_by_name(self):
        class APITimeoutError(Exception): ...
        class APIConnectionError(Exception): ...
        self.assertEqual(map_exception(APITimeoutError()).code, "timeout")
        self.assertEqual(map_exception(APIConnectionError()).code, "network")
        self.assertEqual(map_exception(ValueError("x")).code, "unexpected")

    def test_secrets_never_reach_messages(self):
        body = {"error": {"message": f"bad key {SECRET} sent"}}
        err = map_exception(FakeApiError(403, body), secrets=[SECRET])
        self.assertNotIn(SECRET, err.message)
        self.assertNotIn("sk-or-", err.message)
        self.assertNotIn("abcdef1234567890", redact(f"Bearer {SECRET}"))
        self.assertNotIn(SECRET, from_error_payload({"code": 429, "message": SECRET}).message)

    def test_error_payload_in_stream(self):
        err = from_error_payload({"code": 402, "message": "no credits"})
        self.assertEqual(err.code, "insufficient_credits")


class HelperTests(unittest.TestCase):
    def test_usage_parsing(self):
        self.assertEqual(parse_usage({"prompt_tokens": 2, "completion_tokens": 3}), Usage(2, 3, 5))
        self.assertIsNone(parse_usage(None))
        self.assertIsNone(parse_usage({}))

    def test_key_store(self):
        ks = KeyStore("  env-key-1234567890 ")
        self.assertEqual(ks.source, "environment (.env)")
        ks.set_session("sk-or-v1-session-key-1234")
        self.assertEqual(ks.get(), "sk-or-v1-session-key-1234")
        self.assertFalse(ks.is_validated())
        ks.mark_validated()
        self.assertTrue(ks.is_validated())
        ks.clear_session()
        self.assertFalse(ks.is_validated())
        self.assertNotIn("1234567890", ks.masked()[7:-4] or "x")
        self.assertFalse(KeyStore.looks_valid("short"))

    def test_env_file_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / ".env"
            p.write_text("HOST=127.0.0.1\nOPENROUTER_API_KEY=\n", encoding="utf-8")
            save_api_key(p, SECRET)
            self.assertIn(f"OPENROUTER_API_KEY={SECRET}", p.read_text())
            self.assertIn("HOST=127.0.0.1", p.read_text())
            remove_api_key(p)
            self.assertNotIn(SECRET, p.read_text())
            with self.assertRaises(ValueError):
                save_api_key(p, 'bad"key')


if __name__ == "__main__":
    unittest.main()
