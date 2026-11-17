import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from config import settings
from models.model_registry import ModelRegistry, RegistryError, is_valid_model_id
from services.errors import ChatError
from services.model_service import Availability, ModelService

EXPECTED_IDS = {
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3.5-super-vl:free",
    "baidu/ernie-5.5-flash-preview:free",
    "thinkingmachines/inkling-2-small:free",
    "particle-ai/particle-1:free",
}


class FakeClient:
    def __init__(self, items=None, error=None):
        self.items, self.error = items or [], error

    async def list_models(self):
        if self.error:
            raise self.error
        return self.items


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.user = Path(self.tmp.name) / "user_models.json"
        self.reg = ModelRegistry(settings.builtin_models_path, self.user)

    def tearDown(self):
        self.tmp.cleanup()

    def test_five_builtin_models(self):
        self.assertEqual({m.id for m in self.reg.list()}, EXPECTED_IDS)
        self.assertIn(self.reg.default_id, EXPECTED_IDS)

    def test_id_validation(self):
        self.assertTrue(is_valid_model_id("vendor/model-1:free"))
        for bad in ["", "nomodel", "a b/c", "../x/y", "vendor/", "/model"]:
            self.assertFalse(is_valid_model_id(bad), bad)

    def test_add_and_remove_custom(self):
        info = self.reg.add_custom("My Model", "vendor/my-model:free")
        self.assertFalse(info.builtin)
        reloaded = ModelRegistry(settings.builtin_models_path, self.user)
        self.assertIsNotNone(reloaded.get("vendor/my-model:free"))
        reloaded.remove_custom("vendor/my-model:free")
        self.assertIsNone(ModelRegistry(settings.builtin_models_path, self.user).get("vendor/my-model:free"))

    def test_rejects_bad_input(self):
        with self.assertRaises(RegistryError):
            self.reg.add_custom("", "vendor/x")
        with self.assertRaises(RegistryError):
            self.reg.add_custom("X", "not valid")
        with self.assertRaises(RegistryError):
            self.reg.add_custom("Dup", next(iter(EXPECTED_IDS)))
        with self.assertRaises(RegistryError):
            self.reg.remove_custom(next(iter(EXPECTED_IDS)))

    def test_corrupt_user_file_is_ignored(self):
        self.user.write_text("{not json", encoding="utf-8")
        self.assertEqual(len(ModelRegistry(settings.builtin_models_path, self.user).list()), 5)

    def test_name_for_unknown(self):
        self.assertEqual(self.reg.name_for("x/y"), "x/y")
        self.assertEqual(self.reg.name_for(None), "Unknown model")


class ModelServiceTests(unittest.TestCase):
    def test_availability(self):
        items = [{"id": "a/b:free", "name": "AB", "context_length": 8000,
                  "architecture": {"input_modalities": ["text", "image"]}}, {"bad": 1}]
        svc = ModelService(lambda: FakeClient(items))
        self.assertEqual(svc.availability("a/b:free"), Availability.UNKNOWN)
        self.assertTrue(asyncio.run(svc.refresh()))
        self.assertEqual(svc.availability("a/b:free"), Availability.AVAILABLE)
        self.assertEqual(svc.availability("c/d:free"), Availability.UNAVAILABLE)
        remote = svc.remote("a/b:free")
        self.assertEqual(remote.context_length, 8000)
        self.assertEqual(remote.input_modalities, ("text", "image"))

    def test_failure_keeps_unknown(self):
        err = ChatError("offline", code="network")
        svc = ModelService(lambda: FakeClient(error=err))
        self.assertFalse(asyncio.run(svc.refresh()))
        self.assertEqual(svc.availability("a/b"), Availability.UNKNOWN)
        self.assertEqual(svc.last_error, "offline")


if __name__ == "__main__":
    unittest.main()
