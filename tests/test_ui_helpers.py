import importlib.util
import unittest

HAS_NICEGUI = importlib.util.find_spec("nicegui") is not None


@unittest.skipUnless(HAS_NICEGUI, "nicegui is not installed")
class HelperTests(unittest.TestCase):
    def test_initials_and_hue(self):
        from ui.helpers import fmt_duration, initials, model_hue

        self.assertEqual(initials("NVIDIA Nemotron 3 Ultra"), "NN")
        self.assertEqual(initials("Particle-1"), "PA")
        self.assertEqual(initials("***"), "?")
        self.assertEqual(model_hue("a/b"), model_hue("a/b"))
        self.assertEqual(fmt_duration(420), "420 ms")
        self.assertEqual(fmt_duration(2500), "2.5 s")

    def test_app_modules_import(self):
        import ui.chat_interface, ui.page, ui.settings, ui.sidebar  # noqa: F401


if __name__ == "__main__":
    unittest.main()
