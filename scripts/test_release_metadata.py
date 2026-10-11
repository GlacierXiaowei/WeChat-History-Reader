from __future__ import annotations

import json
from pathlib import Path
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def load_json(relative_path: str) -> dict:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


class ReleaseMetadataTests(unittest.TestCase):
    def test_codex_display_metadata_has_assets_and_matches_portable_manifest(self) -> None:
        portable = load_json("plugin.json")
        codex = load_json(".codex-plugin/plugin.json")
        portable_interface = portable["extensions"]["com.openai"]["interface"]
        codex_interface = codex["interface"]
        expected_description = (
            "读懂微信（WeChat History Reader）让 AI Agent 能够轻易读取、搜索和总结微信本地聊天记录，使得模型能够充分理解你的工作和生活。"
        )

        self.assertEqual(portable_interface, codex_interface)
        self.assertEqual(portable["description"], expected_description)
        self.assertEqual(codex["description"], expected_description)
        self.assertEqual(portable_interface["longDescription"], expected_description)
        self.assertEqual(portable_interface["brandColor"], "#034823")
        for field in ("composerIcon", "logo"):
            asset = codex_interface.get(field)
            self.assertIsInstance(asset, str)
            self.assertTrue(asset.endswith(".png"), asset)
            self.assertTrue((ROOT / asset).is_file(), asset)

    def test_package_script_stages_declared_assets(self) -> None:
        script = (ROOT / "scripts/package_plugin.ps1").read_text(encoding="utf-8")
        self.assertIn('"assets"', script)

    def test_release_zip_contains_one_wrapped_plugin_directory(self) -> None:
        archive = ROOT / "dist/wechat-history-reader-2.1.2.zip"
        with zipfile.ZipFile(archive) as package:
            names = set(package.namelist())

        self.assertIn("wechat-history-reader/plugin.json", names)
        self.assertIn("wechat-history-reader/.codex-plugin/plugin.json", names)
        self.assertTrue(
            all(name.startswith("wechat-history-reader/") for name in names),
            sorted(names),
        )


if __name__ == "__main__":
    unittest.main()
