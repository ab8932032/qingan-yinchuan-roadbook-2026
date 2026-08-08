from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVERSE = re.compile(r"不|别|没|无|否则|免得|避免|禁止|取消|失败|跳过|尚未|未能|未载入|未开放|未知")
ATTRS = {"alt", "aria-label", "placeholder", "title"}


class VisibleCopy(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hidden_depth = 0
        self.in_script = False
        self.script_parts: list[tuple[int, str]] = []
        self.items: list[tuple[int, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script":
            self.in_script = True
        if tag in {"style", "template"}:
            self.hidden_depth += 1
        line, _ = self.getpos()
        for name, value in attrs:
            if name in ATTRS and value:
                self.items.append((line, value))

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self.in_script = False
        if tag in {"style", "template"}:
            self.hidden_depth = max(0, self.hidden_depth - 1)

    def handle_data(self, data: str) -> None:
        line, _ = self.getpos()
        if self.in_script:
            self.script_parts.append((line, data))
        elif self.hidden_depth == 0 and data.strip():
            self.items.append((line, data))


def js_visible_strings(parts: list[tuple[int, str]]) -> list[tuple[int, str]]:
    results: list[tuple[int, str]] = []
    for base_line, source in parts:
        source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
        for match in re.finditer(r"(['\"])(.*?)(?<!\\)\1", source, flags=re.S):
            value = match.group(2)
            if re.search(r"[\u4e00-\u9fff]", value):
                results.append((base_line + source[: match.start()].count("\n"), value))
    return results


def markdown_copy(path: Path) -> list[tuple[int, str]]:
    in_fence = False
    items: list[tuple[int, str]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence and not line.lstrip().startswith("<!--"):
            items.append((line_no, line))
    return items


def main() -> int:
    parser = VisibleCopy()
    parser.feed((ROOT / "index.html").read_text(encoding="utf-8"))
    sources = {
        "index.html": parser.items + js_visible_strings(parser.script_parts),
        "README.md": markdown_copy(ROOT / "README.md"),
    }
    failures: list[str] = []
    for path, items in sources.items():
        for line_no, text in items:
            hit = REVERSE.search(text)
            if hit:
                excerpt = " ".join(text.split())[:160]
                failures.append(f"{path}:{line_no}: {hit.group(0)} :: {excerpt}")
    if failures:
        print("Reverse phrasing remains in user-visible copy:")
        print("\n".join(failures))
        return 1
    print("Positive-copy check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
