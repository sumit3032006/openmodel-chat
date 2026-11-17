import unittest

from ui.markdown_render import harden_html, render_markdown


class MarkdownSafetyTests(unittest.TestCase):
    def test_raw_html_is_not_passed_through(self):
        out = render_markdown("hello <script>alert(1)</script> <img src=x onerror=alert(1)>")
        self.assertNotIn("<script", out.lower())
        self.assertNotIn("<img", out.lower())

    def test_javascript_links_neutralised(self):
        out = harden_html('<a href="javascript:alert(1)">x</a> <a href=\'JaVaScRiPt:evil()\'>y</a>')
        self.assertNotIn("javascript:", out.lower())
        self.assertIn('rel="noopener noreferrer"', out)

    def test_remote_images_blocked(self):
        out = harden_html('<p><img src="https://evil.example/t.png?q=secret" alt="chart"></p>')
        self.assertNotIn("evil.example", out)
        self.assertIn("image blocked", out)
        self.assertIn("chart", out)

    def test_normal_text_survives(self):
        self.assertIn("hello", render_markdown("hello **world**"))


if __name__ == "__main__":
    unittest.main()
