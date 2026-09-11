import contextlib
import datetime as dt
import importlib.util
import io
import pathlib
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "breakfast_xhs.py"
spec = importlib.util.spec_from_file_location("breakfast_local", SCRIPT)
breakfast = importlib.util.module_from_spec(spec)
spec.loader.exec_module(breakfast)


def markdown(count=10):
    rows = ["## Top10", "", "| 序号 | 话题 | 入选类型 | 原始依据 |", "| --- | --- | --- | --- |"]
    rows.extend(f"| {i} | 早餐话题{i} | 随机补位 | 原始候选{i} |" for i in range(1, count + 1))
    return "\n".join(rows) + "\n\n## 原始内容\n这里的 #额外话题 不应入选\n"


class LocalTop10Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.patch = patch.object(breakfast, "HOT_TOPICS_DIR", self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.target = dt.date(2026, 9, 11)

    def source(self, date, text=None):
        path = self.root / f"{date}.md"
        path.write_text(markdown() if text is None else text, encoding="utf-8")
        return path

    def test_latest_date_not_mtime_and_ignore_demo_future(self):
        newest = self.source("2026-09-10")
        self.source("2026-09-01")
        self.source("9999-01-01")
        self.source("demo")
        self.assertEqual(breakfast.latest_top10_source()[1], newest)

    def test_top10_order_and_truncation(self):
        items = breakfast.parse_top10_markdown(markdown(12))
        self.assertEqual([i["tag"] for i in items], [f"#早餐话题{i}" for i in range(1, 11)])

    def test_missing_source(self):
        with self.assertRaisesRegex(ValueError, "缺少日期"):
            breakfast.build_latest_topic_registry(self.target)

    def test_invalid_latest_never_falls_back(self):
        self.source("2026-09-01")
        self.source("2026-09-10", markdown(9))
        with self.assertRaisesRegex(ValueError, "不足 10"):
            breakfast.build_latest_topic_registry(self.target)

    def test_duplicates_and_rank_gaps(self):
        for text in [markdown().replace("早餐话题10", "早餐话题1"), markdown().replace("| 2 |", "| 12 |")]:
            with self.assertRaises(ValueError):
                breakfast.parse_top10_markdown(text)

    def test_frozen_snapshot_and_tamper_detection(self):
        source = self.source("2026-09-10")
        registry = breakfast.build_latest_topic_registry(self.target)
        self.assertEqual(breakfast.validate_weekly_hot_tag_registry(registry, self.target), [])
        source.write_text("source later changed", encoding="utf-8")
        self.assertEqual(breakfast.validate_weekly_hot_tag_registry(registry, self.target), [])
        registry["candidates"][0]["tag"] = "#篡改"
        self.assertTrue(breakfast.validate_weekly_hot_tag_registry(registry, self.target))
        registry["source_markdown"] += "changed"
        self.assertTrue(any("摘要" in e for e in breakfast.validate_weekly_hot_tag_registry(registry, self.target)))

    def test_title_rules(self):
        for title in ["直接抄作业！四口之家的20分钟早餐", "答应我，早餐一定试试这碗番茄虾仁面", "有手就会！这套早餐让全家吃得热乎乎", "", "早" * 21]:
            errors = breakfast.validate_manifest_data({"title": title})
            self.assertEqual(any(e.startswith("title ") for e in errors), not title or len(title) > 20)

    def test_publish_command_cannot_call_network(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("network not allowed")), contextlib.redirect_stderr(io.StringIO()):
            args = breakfast.build_parser().parse_args(["publish", "unused.json"])
            self.assertEqual(args.func(args), 1)


if __name__ == "__main__":
    unittest.main()
