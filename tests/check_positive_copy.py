from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVERSE = re.compile(r"不|别|没|无|否则|免得|避免|禁止|取消|失败|跳过|尚未|未能|未载入|未开放|未知")
ATTRS = {"alt", "aria-label", "placeholder", "title"}
PROPER_NAME_ALLOWANCES = ("梵尘别院",)
FORBIDDEN_ALIASES = ("梵尘民宿",)
MISLEADING_STATES = ("高德地图进入基础模式", "天气服务正在重新连接")


class VisibleCopy(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hidden_depth = 0
        self.in_script = False
        self.in_style = False
        self.script_parts: list[tuple[int, str]] = []
        self.style_parts: list[tuple[int, str]] = []
        self.items: list[tuple[int, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script":
            self.in_script = True
        if tag == "style":
            self.in_style = True
            self.hidden_depth += 1
        line, _ = self.getpos()
        for name, value in attrs:
            if name in ATTRS and value:
                self.items.append((line, value))

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self.in_script = False
        if tag == "style":
            self.in_style = False
            self.hidden_depth = max(0, self.hidden_depth - 1)

    def handle_data(self, data: str) -> None:
        line, _ = self.getpos()
        if self.in_script:
            self.script_parts.append((line, data))
        elif self.in_style:
            self.style_parts.append((line, data))
        elif self.hidden_depth == 0 and data.strip():
            self.items.append((line, data))


def js_visible_strings(parts: list[tuple[int, str]]) -> list[tuple[int, str]]:
    results: list[tuple[int, str]] = []
    for base_line, source in parts:
        index = 0
        line_offset = 0
        while index < len(source):
            if source.startswith("//", index):
                newline = source.find("\n", index + 2)
                if newline == -1:
                    break
                line_offset += 1
                index = newline + 1
                continue
            if source.startswith("/*", index):
                end = source.find("*/", index + 2)
                if end == -1:
                    break
                line_offset += source[index : end + 2].count("\n")
                index = end + 2
                continue
            if source[index] == "/" and index + 1 < len(source) and source[index + 1] not in {"/", "*"}:
                previous = index - 1
                while previous >= 0 and source[previous].isspace():
                    previous -= 1
                if previous < 0 or source[previous] in "(=[:,!&|?{};":
                    index += 1
                    in_class = False
                    while index < len(source):
                        char = source[index]
                        if char == "\\" and index + 1 < len(source):
                            index += 2
                            continue
                        if char == "[":
                            in_class = True
                        elif char == "]":
                            in_class = False
                        elif char == "/" and not in_class:
                            index += 1
                            while index < len(source) and source[index].isalpha():
                                index += 1
                            break
                        if char == "\n":
                            line_offset += 1
                        index += 1
                    continue
            quote = source[index]
            if quote not in {"'", '"', "`"}:
                if quote == "\n":
                    line_offset += 1
                index += 1
                continue
            start_line = base_line + line_offset
            index += 1
            value: list[str] = []
            while index < len(source):
                char = source[index]
                if char == "\\" and index + 1 < len(source):
                    value.extend((char, source[index + 1]))
                    if source[index + 1] == "\n":
                        line_offset += 1
                    index += 2
                    continue
                if char == quote:
                    index += 1
                    break
                value.append(char)
                if char == "\n":
                    line_offset += 1
                index += 1
            text = "".join(value)
            if re.search(r"[\u4e00-\u9fff]", text):
                results.append((start_line, text))
    return results


def css_visible_strings(parts: list[tuple[int, str]]) -> list[tuple[int, str]]:
    results: list[tuple[int, str]] = []
    for base_line, source in parts:
        for match in re.finditer(r"content\s*:\s*(['\"])(.*?)\1", source, flags=re.S):
            value = match.group(2)
            if re.search(r"[\u4e00-\u9fff]", value):
                results.append((base_line + source[: match.start()].count("\n"), value))
    return results


def reverse_hit(text: str) -> re.Match[str] | None:
    checked = text
    for proper_name in PROPER_NAME_ALLOWANCES:
        checked = checked.replace(proper_name, "")
    return REVERSE.search(checked)


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
        "index.html": parser.items + js_visible_strings(parser.script_parts) + css_visible_strings(parser.style_parts),
        "README.md": markdown_copy(ROOT / "README.md"),
    }
    failures: list[str] = []
    for path, items in sources.items():
        for line_no, text in items:
            hit = reverse_hit(text)
            if hit:
                excerpt = " ".join(text.split())[:160]
                failures.append(f"{path}:{line_no}: {hit.group(0)} :: {excerpt}")
    index_source = (ROOT / "index.html").read_text(encoding="utf-8")
    for alias in FORBIDDEN_ALIASES:
        if alias in index_source:
            failures.append(f"index.html: forbidden proper-name alias remains: {alias}")
    for proper_name in PROPER_NAME_ALLOWANCES:
        if proper_name not in index_source:
            failures.append(f"index.html: required proper name is missing: {proper_name}")
    for state in MISLEADING_STATES:
        if state in index_source:
            failures.append(f"index.html: misleading fallback state remains: {state}")
    if failures:
        print("Reverse phrasing remains in user-visible copy:")
        print("\n".join(failures))
        return 1
    print("Positive-copy check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
