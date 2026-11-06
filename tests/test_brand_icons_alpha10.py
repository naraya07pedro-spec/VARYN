"""Bounded release checks for genuine third-party logos and one-click setup.

The binary packaging separately tests Tk PhotoImage loading of rasterized PNGs.
"""
from pathlib import Path
import unittest
from xml.etree import ElementTree

from varyn.app_api_connections import guide_for
from varyn.app_hub_ui import FEATURED


ASSETS = (
    "github", "notion", "telegram", "whatsapp", "gmail",
    "google_calendar", "google_drive", "supabase", "linkedin",
    "netlify", "hostinger_mail", "google_docs", "google_sheets",
    "slack", "discord", "hubspot", "dropbox", "spotify",
    "canva", "descript",
)


class BrandArtworkTests(unittest.TestCase):
    def test_real_local_svg_sources_exist_with_explicit_licenses(self):
        root = Path(__file__).resolve().parents[1]
        files = root / "assets" / "brand_svg"
        notice = (root / "assets" / "BRAND-LICENSES.md").read_text("utf-8")
        self.assertIn("SuperTinyIcons", notice)
        self.assertIn("Simple Icons", notice)
        self.assertIn("Devicon", notice)
        self.assertIn("Gilbarbara", notice)
        for brand in ASSETS:
            svg = files / (brand + ".svg")
            with self.subTest(brand=brand):
                self.assertTrue(svg.is_file())
                raw = svg.read_text("utf-8")
                self.assertLess(len(raw), 24000)
                self.assertNotIn("<script", raw.casefold())
                self.assertNotIn("<!doctype", raw.casefold())
                self.assertTrue(ElementTree.fromstring(raw).tag.endswith("svg"))
                self.assertIn(brand + ".svg", notice)

    def test_featured_apps_have_authentic_local_logo_assets(self):
        root = Path(__file__).resolve().parents[1] / "assets" / "brand_svg"
        for service, *_ in FEATURED:
            self.assertTrue((root / (service + ".svg")).is_file())

    def test_official_setup_button_has_real_link_for_relevant_apps(self):
        for service in (
            "gmail", "google_calendar", "google_drive", "linkedin",
            "hostinger_mail", "canva",
        ):
            with self.subTest(service=service):
                guide = guide_for(service)
                self.assertIsNotNone(guide)
                self.assertTrue(guide.startswith("https://"))
        self.assertIsNone(guide_for("totally-unknown-service"))


if __name__ == "__main__":
    unittest.main()
