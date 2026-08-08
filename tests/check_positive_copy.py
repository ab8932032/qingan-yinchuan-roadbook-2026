from __future__ import annotations

import html
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVERSE = re.compile(r"尚未|未能|未载入|未开放|未知|否则|免得|避免|禁止|取消|失败|跳过|不|别|没|无|未")
ATTRS = {"alt", "aria-label", "placeholder", "title", "data-caption", "data-placeholder"}
APPROVED_ALLOWANCES = (
    "梵尘别院",
    "瓜州大地之子与无界",
    "无垠的沙漠",
    "未来",
)
JS_REGEX_PREFIX_KEYWORDS = {
    "await",
    "case",
    "delete",
    "do",
    "else",
    "in",
    "instanceof",
    "of",
    "return",
    "throw",
    "typeof",
    "void",
    "yield",
}


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
        elif tag == "template":
            self.hidden_depth += 1
        line, _ = self.getpos()
        if self.hidden_depth == 0:
            for name, value in attrs:
                if name in ATTRS and value:
                    self.items.append((line, html.unescape(value)))

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self.in_script = False
        if tag == "style":
            self.in_style = False
            self.hidden_depth = max(0, self.hidden_depth - 1)
        elif tag == "template":
            self.hidden_depth = max(0, self.hidden_depth - 1)

    def handle_data(self, data: str) -> None:
        line, _ = self.getpos()
        if self.in_script:
            self.script_parts.append((line, data))
        elif self.in_style:
            self.style_parts.append((line, data))
        elif self.hidden_depth == 0 and data.strip():
            self.items.append((line, data))


def decode_js_text(value: str) -> str:
    def braced_codepoint(match: re.Match[str]) -> str:
        codepoint = int(match.group(1), 16)
        return chr(codepoint) if codepoint <= 0x10FFFF else "\ufffd"

    value = re.sub(r"\\u\{([0-9a-fA-F]{1,6})\}", braced_codepoint, value)
    value = re.sub(r"\\u([0-9a-fA-F]{4})", lambda match: chr(int(match.group(1), 16)), value)
    value = re.sub(r"\\x([0-9a-fA-F]{2})", lambda match: chr(int(match.group(1), 16)), value)
    value = re.sub(r"\\\r?\n", "", value)
    value = re.sub(r"\\[nrtbfv]", " ", value)
    value = re.sub(r"\\(.)", r"\1", value, flags=re.S)
    try:
        value = value.encode("utf-16", "surrogatepass").decode("utf-16")
    except UnicodeError:
        pass
    return html.unescape(value)


def js_regex_starts_here(source: str, index: int) -> bool:
    previous = index - 1
    while previous >= 0 and source[previous].isspace():
        previous -= 1
    if previous < 0 or source[previous] in "(=[:,!&|?{};,+-*%^~<>":
        return True
    prefix = source[:index].rstrip()
    if prefix.endswith("=>"):
        return True
    if source[previous].isalnum() or source[previous] in "_$":
        word_start = previous
        while word_start >= 0 and (source[word_start].isalnum() or source[word_start] in "_$"):
            word_start -= 1
        return source[word_start + 1 : previous + 1] in JS_REGEX_PREFIX_KEYWORDS
    return False


def js_visible_strings(parts: list[tuple[int, str]]) -> list[tuple[int, str]]:
    results: list[tuple[int, str]] = []
    for base_line, source in parts:
        index = 0
        while index < len(source):
            if source.startswith("//", index):
                newline = source.find("\n", index + 2)
                if newline == -1:
                    break
                index = newline + 1
                continue
            if source.startswith("/*", index):
                end = source.find("*/", index + 2)
                if end == -1:
                    break
                index = end + 2
                continue
            if source[index] == "/" and index + 1 < len(source) and source[index + 1] not in {"/", "*"}:
                if js_regex_starts_here(source, index):
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
                        index += 1
                    continue
            quote = source[index]
            if quote not in {"'", '"', "`"}:
                index += 1
                continue
            start_line = base_line + source[:index].count("\n")
            index += 1
            value: list[str] = []
            while index < len(source):
                char = source[index]
                if char == "\\" and index + 1 < len(source):
                    value.extend((char, source[index + 1]))
                    index += 2
                    continue
                if char == quote:
                    index += 1
                    break
                value.append(char)
                index += 1
            text = decode_js_text("".join(value))
            if re.search(r"[\u4e00-\u9fff]", text):
                results.append((start_line, text))
    return results


def decode_css_text(value: str) -> str:
    value = re.sub(
        r"\\([0-9a-fA-F]{1,6})(?:\s)?",
        lambda match: chr(int(match.group(1), 16)),
        value,
    )
    value = re.sub(r"\\(.)", r"\1", value, flags=re.S)
    return html.unescape(value)


def css_visible_strings(parts: list[tuple[int, str]]) -> list[tuple[int, str]]:
    results: list[tuple[int, str]] = []
    for base_line, source in parts:
        for match in re.finditer(r"content\s*:\s*(['\"])(.*?)\1", source, flags=re.S):
            value = decode_css_text(match.group(2))
            if re.search(r"[\u4e00-\u9fff]", value):
                results.append((base_line + source[: match.start()].count("\n"), value))
    return results


def reverse_hits(text: str) -> list[re.Match[str]]:
    checked = text
    for allowance in APPROVED_ALLOWANCES:
        checked = checked.replace(allowance, " " * len(allowance))
    return list(REVERSE.finditer(checked))


def reverse_hit(text: str) -> re.Match[str] | None:
    hits = reverse_hits(text)
    return hits[0] if hits else None


def markdown_copy(path: Path) -> list[tuple[int, str]]:
    in_fence = False
    items: list[tuple[int, str]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence and not line.lstrip().startswith("<!--"):
            items.append((line_no, html.unescape(line)))
    return items


def centered_excerpt(text: str, start: int, end: int, radius: int = 72) -> str:
    excerpt_start = max(0, start - radius)
    excerpt_end = min(len(text), end + radius)
    excerpt = " ".join(text[excerpt_start:excerpt_end].split())
    if excerpt_start:
        excerpt = "…" + excerpt
    if excerpt_end < len(text):
        excerpt += "…"
    return excerpt


def item_failures(path: str, items: list[tuple[int, str]]) -> list[str]:
    failures: list[str] = []
    for line_no, text in items:
        for hit in reverse_hits(text):
            hit_line = line_no + text[: hit.start()].count("\n")
            excerpt = centered_excerpt(text, hit.start(), hit.end())
            failures.append(f"{path}:{hit_line}: {hit.group(0)} :: {excerpt}")
    return failures


def main() -> int:
    parser = VisibleCopy()
    parser.feed((ROOT / "index.html").read_text(encoding="utf-8"))
    sources = {
        "index.html": parser.items + js_visible_strings(parser.script_parts) + css_visible_strings(parser.style_parts),
        "README.md": markdown_copy(ROOT / "README.md"),
    }
    failures: list[str] = []
    for path, items in sources.items():
        failures.extend(item_failures(path, items))
    if failures:
        print("Reverse phrasing remains in user-visible copy:")
        print("\n".join(failures))
        return 1
    print("Positive-copy check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
