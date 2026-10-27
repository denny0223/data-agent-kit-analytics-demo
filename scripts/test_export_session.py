import json
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

from export_session import ROOT, export, public_records, render, markdown


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.ids = []
        self.attributes = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attributes.extend(attrs)
        self.ids.extend(value for key, value in attrs if key == "id")


def row(step, kind, **extra):
    return {"step_index": step, "type": kind, "source": "MODEL", "status": "DONE",
            "created_at": "2026-10-26T18:00:00Z", **extra}


class ExportTests(unittest.TestCase):
    def test_public_fields_and_environment_redaction(self):
        original = [
            row(0, "USER_INPUT", content="原文 /home/alice/work gen-lang-client-12345"),
            row(1, "PLANNER_RESPONSE", thinking="not public", input_tokens=42,
                tool_calls=[{"name": "read", "args": {"path": "/home/alice/work"}}]),
            row(2, "GENERIC", content="service-123456789@gcp-sa-bigqueryconnection.iam.gserviceaccount.com"),
            row(3, "SYSTEM_MESSAGE", content="not public"),
        ]
        public = public_records(original)
        self.assertEqual(len(public), 3)
        self.assertNotIn("thinking", public[1])
        self.assertEqual(public[1]["input_tokens"], 42)
        self.assertEqual(public[1]["tool_calls"][0]["args"]["path"], "/home/USER/work")
        self.assertEqual(public[0]["content"], "原文 /home/USER/work YOUR_PROJECT_ID")
        self.assertIn("service-PROJECT_NUMBER@", public[2]["content"])
        self.assertIn("thinking", original[1])

    def test_credentials_block_export(self):
        with self.assertRaises(ValueError):
            public_records([row(0, "GENERIC", content="ya29." + "x" * 40)])

    def test_markdown_renders_tables_lists_code_and_rejects_active_html(self):
        content = ("## 原始標題\n\n**粗體** 與 `order_id`\n\n"
                   "| 月份 | AOV |\n| --- | ---: |\n| 一月 | 25 |\n\n"
                   "- 原始清單\n\n```sql\nSELECT '<script>' AS value;\n```\n\n"
                   "[連結](https://example.com) [惡意](javascript:alert(1))\n"
                   "![圖片](https://example.com/tracker.png) <iframe src=x></iframe>")
        page = markdown(content)
        parser = Elements()
        parser.feed(page)
        for tag in ['h2', 'strong', 'code', 'table', 'th', 'td', 'ul', 'li']:
            self.assertIn(tag, parser.tags)
        for tag in ['script', 'iframe', 'img']:
            self.assertNotIn(tag, parser.tags)
        self.assertNotIn(('href', 'javascript:alert(1)'), parser.attributes)
        self.assertIn(('href', 'https://example.com'), parser.attributes)
        self.assertIn("SELECT &#x27;&lt;script&gt;&#x27; AS value;", page)

    def test_consecutive_calls_group_without_hiding_interleaved_messages(self):
        call = [{"name": "run_command", "args": {"CommandLine": "pwd"}}]
        records = [
            row(0, "USER_INPUT", content="第一個問題"),
            row(1, "PLANNER_RESPONSE", tool_calls=call),
            row(2, "GENERIC", content="結果一"),
            row(3, "PLANNER_RESPONSE", tool_calls=call),
            row(4, "GENERIC", content="結果二"),
            row(5, "PLANNER_RESPONSE", content="中途回覆", tool_calls=call),
            row(6, "GENERIC", content="結果三"),
            row(7, "PLANNER_RESPONSE", content="第一個回答"),
            row(8, "USER_INPUT", content="第二個問題"),
            row(9, "PLANNER_RESPONSE", tool_calls=call),
            row(10, "GENERIC", status="ERROR", content="原始錯誤"),
        ]
        template = (ROOT / "scripts/transcript-template.html").read_text()
        page, stats = render(records, "abc", template)
        parser = Elements()
        parser.feed(page)
        self.assertEqual(page.count('class="tool-group"'), 3)
        self.assertEqual(page.count('class="turn"'), 2)
        self.assertIn('2 次工具呼叫', page)
        self.assertIn('1 次錯誤', page)
        self.assertLess(page.index('id="step-3"'), page.index('id="message-5"'))
        self.assertLess(page.index('id="message-5"'), page.index('id="step-5"'))
        self.assertEqual(len(parser.ids), len(set(parser.ids)))
        self.assertTrue({f"step-{i}" for i in range(11)}.issubset(parser.ids))
        self.assertEqual(stats['calls'], 4)

    def test_html_is_text_and_all_steps_remain_addressable(self):
        attack = '</pre><script>alert("x")</script><img src=x onerror=alert(1)>'
        records = [
            row(0, "USER_INPUT", content="<USER_REQUEST>原文 " + attack + "</USER_REQUEST>"),
            row(1, "PLANNER_RESPONSE", content="進度原文",
                tool_calls=[{"name": "run_command", "args": {"CommandLine": json.dumps(attack)}}]),
            row(2, "GENERIC", status="ERROR", error=attack, content="\x1b[31m" + attack),
            row(3, "PLANNER_RESPONSE", content="回覆 {{ENTRIES}} 保持原文"),
        ]
        template = (ROOT / "scripts/transcript-template.html").read_text()
        page, stats = render(records, "abc", template)
        parser = Elements()
        parser.feed(page)
        self.assertEqual(parser.tags.count("script"), 1)
        self.assertNotIn("img", parser.tags)
        self.assertTrue({"step-0", "step-1", "step-2", "step-3"}.issubset(parser.ids))
        self.assertEqual(len(parser.ids), len(set(parser.ids)))
        self.assertIn("回覆 {{ENTRIES}} 保持原文", page)
        self.assertIn("進度原文", page)
        self.assertEqual(stats["replies"], 2)
        self.assertEqual(stats["calls"], 1)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.jsonl"
            source.write_text("".join(json.dumps(r) + "\n" for r in records))
            destination = Path(directory) / "public"
            export(source, destination, template)
            saved = [json.loads(line) for line in (destination / "session.jsonl").read_text().splitlines()]
            self.assertEqual(saved, records)
            self.assertIn("\x1b[31m", saved[2]["content"])


if __name__ == "__main__":
    unittest.main()
