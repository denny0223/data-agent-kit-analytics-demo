"""Export this lab session as a static Markdown transcript and public JSONL."""
import argparse
import hashlib
import html
import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


from markdown_it import MarkdownIt

# Raw HTML stays text; image references never load remote content.
MARKDOWN = MarkdownIt("js-default").disable("image")


def code_block(tokens, index, options, env):
    token = tokens[index]
    language = token.info.strip().split()[0] if token.info.strip() else "text"
    return (
        '<div class="code-block"><div class="code-label"><span>'
        + html.escape(language) + '</span><button type="button" data-copy-code>複製程式碼</button></div>'
        + "<pre><code>" + html.escape(token.content) + "</code></pre></div>"
    )


MARKDOWN.renderer.rules["fence"] = code_block
MARKDOWN.renderer.rules["code_block"] = code_block
MARKDOWN.renderer.rules["table_open"] = lambda *args: '<div class="table-wrap" tabindex="0" role="region" aria-label="資料表格"><table>'
MARKDOWN.renderer.rules["table_close"] = lambda *args: "</table></div>"

ROOT = Path(__file__).resolve().parents[1]
SESSION_ID = "f65ce8cb-13d1-4499-a7dd-fd83a9b78d67"
CREDENTIAL = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    r"|AIza[0-9A-Za-z_-]{30,}|ya29\.[A-Za-z0-9._-]+"
    r"|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"
    r"|(?i:Bearer\s+[A-Za-z0-9._~+/=-]{20,})"
)
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def public_records(rows):
    records = [{k: v for k, v in row.items() if k != "thinking"}
               for row in rows if row["type"] != "SYSTEM_MESSAGE"]
    serialized = json.dumps(records, ensure_ascii=False)
    if CREDENTIAL.search(serialized):
        raise ValueError("Credential-like content found; review the source before publishing.")
    numbers = set(re.findall(r"(?:bqcx-|service-)(\d{6,})", serialized))

    def clean(value):
        if isinstance(value, str):
            value = re.sub(r"/home/[^/\s\"'<>\\]+", "/home/USER", value)
            value = re.sub(r"\bgen-lang-client-\d+\b", "YOUR_PROJECT_ID", value)
            for number in numbers:
                value = value.replace(number, "PROJECT_NUMBER")
            return value
        if isinstance(value, list):
            return [clean(item) for item in value]
        if isinstance(value, dict):
            return {key: clean(item) for key, item in value.items()}
        return value

    return clean(records)


def literal(value, class_name="literal"):
    return '<pre class="' + class_name + '">' + html.escape(ANSI.sub("", value)) + "</pre>"


def pretty(value):
    return json.dumps(value, ensure_ascii=False, indent=2)


def stamp(row):
    return datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")).astimezone(
        ZoneInfo("Asia/Taipei")).strftime("%Y-%m-%d %H:%M:%S")


def user_text(row):
    content = row.get("content", "")
    match = re.search(r"<USER_REQUEST>\s*(.*?)\s*</USER_REQUEST>", content, re.S)
    return match.group(1) if match else content


def metadata(row):
    fields = {k: v for k, v in row.items() if k not in ("content", "tool_calls")}
    return "<details class=\"metadata\"><summary>紀錄中繼資料</summary>" + literal(pretty(fields)) + "</details>"


def raw_records(rows):
    text = pretty(rows[0] if len(rows) == 1 else rows)
    return ('<details class="raw"><summary>原始 JSON 紀錄</summary>'
            '<button type="button" class="copy" data-copy>複製 JSON</button>'
            + literal(text) + "</details>")


def call_name(call):
    args = call.get("args", {})
    name = args.get("ToolName", call["name"])
    if isinstance(name, str):
        try:
            name = json.loads(name)
        except (ValueError, TypeError):
            pass
    return str(name)


def calls_html(calls):
    parts = []
    for call in calls:
        parts.append("<h3>" + html.escape(call["name"]) + "</h3><dl class=\"arguments\">")
        for key, value in call.get("args", {}).items():
            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except ValueError:
                    pass
            shown = value if isinstance(value, str) else pretty(value)
            parts.append("<dt>" + html.escape(key) + "</dt><dd>" + literal(shown) + "</dd>")
        parts.append("</dl>")
    return "".join(parts)


def markdown(value):
    return '<div class="prose">' + MARKDOWN.render(ANSI.sub("", value)) + "</div>"


def dialogue(row, number=None, attached=False):
    is_user = row["type"] == "USER_INPUT"
    step = row["step_index"]
    anchor = f"message-{step}" if attached else f"step-{step}"
    label = f"提問 {number:02}" if is_user else "Agent 回覆"
    time = (f'<time datetime="{html.escape(row["created_at"])}" title="{stamp(row)}（臺灣）">'
            + stamp(row)[11:] + "</time>")
    return (
        f'<article class="record message-card {"user" if is_user else "agent"}" id="{anchor}">'
        + '<header class="message-meta"><span class="role-mark" aria-hidden="true">'
        + ("Q" if is_user else "A") + "</span><h2>" + label + "</h2>"
        + f'<a class="step" href="#step-{step}">Step {step}</a>' + time + "</header>"
        + markdown(user_text(row) if is_user else row.get("content", ""))
        + ("" if attached else raw_records([row])) + "</article>"
    )


def tool_group(pairs):
    calls = [call for row, result in pairs for call in row["tool_calls"]]
    names = list(dict.fromkeys(call_name(call) for call in calls))
    name_label = " · ".join(names[:3]) + (f" · +{len(names) - 3} 種" if len(names) > 3 else "")
    errors = sum(result is not None and result["status"] == "ERROR" for row, result in pairs)
    parts = [
        '<details class="tool-group"><summary><span class="tool-glyph" aria-hidden="true">↳</span>'
        + f'<span class="group-label"><strong>{len(calls)} 次工具呼叫</strong>'
        + f'<span class="group-names">{html.escape(name_label)}</span></span>'
        + (f'<span class="error-tag">{errors} 次錯誤</span>' if errors else "")
        + '<span class="group-action">查看紀錄 <span aria-hidden="true">⌄</span></span></summary>'
        + '<div class="group-body">'
    ]
    for order, (row, result) in enumerate(pairs, 1):
        step = row["step_index"]
        names = " · ".join(call_name(call) for call in row["tool_calls"])
        related = [row] + ([result] if result else [])
        end = " → " + str(result["step_index"]) if result else ""
        failed = result is not None and result["status"] == "ERROR"
        parts.append(
            f'<article class="record tool-entry" id="step-{step}"><details class="tool-details">'
            + f'<summary><span class="tool-order">{order:02}</span><span class="tool-name">{html.escape(names)}</span>'
            + ('<span class="error-tag">ERROR</span>' if failed else "")
            + f'<a class="step" href="#step-{step}">Step {step}{end}</a></summary>'
            + '<div class="detail-body"><div class="meta">'
            + stamp(row) + "（臺灣） · " + html.escape(row["status"]) + "</div>"
            + calls_html(row["tool_calls"]) + metadata(row)
        )
        if result:
            parts.append(
                f'<h3 id="step-{result["step_index"]}">工具結果 · Step {result["step_index"]}'
                + " · " + html.escape(result["status"]) + "</h3>"
                + literal(result.get("content", "")) + metadata(result)
            )
        parts.append(raw_records(related) + "</div></details></article>")
    parts.append("</div></details>")
    return "".join(parts)


def render(records, source_hash, template):
    entries, questions, pending = [], [], []
    index, number = 0, 0
    section_open = False

    def flush_tools():
        if pending:
            entries.append(tool_group(pending))
            pending.clear()

    while index < len(records):
        row = records[index]
        step, kind = row["step_index"], row["type"]
        if kind == "USER_INPUT":
            flush_tools()
            if section_open:
                entries.append("</section>")
            number += 1
            text = user_text(row)
            lines = [line for line in text.splitlines() if line.strip() and not line.startswith("/")]
            title = lines[0] if lines else text
            questions.append(
                f'<li><a href="#step-{step}" title="{html.escape(title, quote=True)}">'
                + f'<span class="question-number">{number:02}</span>'
                + '<span class="question-label">' + html.escape(title) + "</span></a></li>"
            )
            entries.append(f'<section class="turn" data-question="step-{step}" data-number="{number:02}">')
            section_open = True
            entries.append(dialogue(row, number))
        elif row.get("tool_calls"):
            if row.get("content"):
                flush_tools()
                entries.append(dialogue(row, attached=True))
            result = None
            if index + 1 < len(records) and records[index + 1]["type"] == "GENERIC":
                result = records[index + 1]
                index += 1
            pending.append((row, result))
        else:
            flush_tools()
            entries.append(dialogue(row))
        index += 1
    flush_tools()
    if section_open:
        entries.append("</section>")

    stats = {
        "records": len(records),
        "users": sum(row["type"] == "USER_INPUT" for row in records),
        "replies": sum(row["type"] == "PLANNER_RESPONSE" and bool(row.get("content")) for row in records),
        "calls": sum(len(row.get("tool_calls", [])) for row in records),
        "results": sum(row["type"] == "GENERIC" for row in records),
    }
    replacements = {
        "SESSION_ID": SESSION_ID,
        "LAST_TIME": stamp(records[-1]),
        "USERS": str(stats["users"]),
        "REPLIES": str(stats["replies"]),
        "CALLS": str(stats["calls"]),
        "RESULTS": str(stats["results"]),
        "RECORDS": str(stats["records"]),
        "SOURCE_HASH": source_hash,
        "QUESTIONS": "".join(questions),
        "ENTRIES": "\n".join(entries),
    }
    # Replace only template placeholders, never text originating in the transcript.
    page = re.sub(r"\{\{([A-Z_]+)\}\}", lambda match: replacements[match.group(1)], template)
    return page, stats

def export(source, destination, template):
    raw = source.read_bytes()
    rows = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    if not rows or any(row.get("truncated_fields") for row in rows):
        raise ValueError("Expected a nonempty, untruncated transcript_full.jsonl.")
    steps = [row["step_index"] for row in rows]
    if steps != sorted(set(steps)):
        raise ValueError("Step numbers must be unique and ordered.")
    records = public_records(rows)
    source_hash = hashlib.sha256(raw).hexdigest()
    page, stats = render(records, source_hash, template)
    jsonl = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in records)
    assert [json.loads(line) for line in jsonl.splitlines()] == records
    destination.mkdir(parents=True, exist_ok=True)
    for name, content in [("index.html", page), ("session.jsonl", jsonl)]:
        (destination / name).write_text(content, encoding="utf-8")
    return {**stats, "source_sha256": source_hash, "last_step": steps[-1], "last_time": rows[-1]["created_at"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Latest original transcript_full.jsonl")
    args = parser.parse_args()
    result = export(args.source, ROOT / "transcript",
                    (ROOT / "scripts/transcript-template.html").read_text(encoding="utf-8"))
    print(json.dumps(result, ensure_ascii=False))
