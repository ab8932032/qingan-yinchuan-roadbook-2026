from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import check_positive_copy as checker


def html_items(source: str) -> list[tuple[int, str]]:
    parser = checker.VisibleCopy()
    parser.feed(source)
    parser.close()
    return (
        parser.items
        + checker.js_visible_strings(parser.script_parts)
        + checker.css_visible_strings(parser.style_parts)
    )


class VisibleCopyTests(unittest.TestCase):
    def test_rendered_data_attributes_are_scanned_and_entities_are_decoded(self) -> None:
        items = html_items(
            '<div data-caption="&#26410;&#23436;&#25104;" '
            'data-placeholder="&#19981;&#35201;&#20572;&#36710;"></div>'
        )

        self.assertEqual(items, [(1, "未完成"), (1, "不要停车")])

    def test_html_template_contents_stay_out_of_visible_copy(self) -> None:
        items = html_items("<template><p>未完成</p></template><p>直接出发</p>")

        self.assertEqual(items, [(1, "直接出发")])

    def test_javascript_unicode_escapes_and_html_entities_are_decoded(self) -> None:
        items = checker.js_visible_strings(
            [
                (
                    10,
                    r'''const escaped = "\u672a\u5b8c\u6210";
const entity = "&#26410;&#23436;&#25104;";''',
                )
            ]
        )

        self.assertEqual(items, [(10, "未完成"), (11, "未完成")])

    def test_javascript_template_literals_are_scanned_but_comments_and_regex_are_not(self) -> None:
        items = checker.js_visible_strings(
            [
                (
                    20,
                    '''// "注释里的未完成"
const visible = `第一行
第二行未完成`;
const matcher = /不要|未完成/g;
/* `块注释里的禁止` */''',
                )
            ]
        )

        self.assertEqual(items, [(21, "第一行\n第二行未完成")])

    def test_regex_after_return_is_excluded_without_hiding_following_literal(self) -> None:
        items = checker.js_visible_strings(
            [
                (
                    40,
                    '''function quoteMatcher() { return /["']foo/; }
const visible = "不要停车";''',
                )
            ]
        )

        self.assertEqual(items, [(41, "不要停车")])

    def test_css_content_escapes_and_entities_are_decoded(self) -> None:
        items = checker.css_visible_strings(
            [(30, r'.notice::before { content: "\672a \5b8c \6210 "; }')]
        )

        self.assertEqual(items, [(30, "未完成")])


class ReversePhraseTests(unittest.TestCase):
    def test_bare_wei_is_detected(self) -> None:
        hit = checker.reverse_hit("灯影未到")

        self.assertIsNotNone(hit)
        self.assertEqual(hit.group(0), "未")

    def test_approved_future_term_and_exact_names_or_quotation_are_allowed(self) -> None:
        approved = (
            "当行程日期进入未来 16 天预报范围后",
            "梵尘别院",
            "瓜州大地之子与无界",
            "无垠的沙漠",
        )

        self.assertTrue(all(checker.reverse_hit(text) is None for text in approved))

    def test_allowance_does_not_hide_an_unapproved_hit_in_the_same_item(self) -> None:
        hit = checker.reverse_hit("未来 16 天内仍未完成")

        self.assertIsNotNone(hit)
        self.assertEqual(hit.group(0), "未")

    def test_report_lists_every_hit_with_the_hits_own_line_and_centered_excerpt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.joinpath("index.html").write_text(
                '<p>' + ('前文' * 90) + '不合适，随后未完成，末尾继续。</p>\n'
                '<script>const detail = `第一行\n第三处禁止。`;</script>',
                encoding="utf-8",
            )
            root.joinpath("README.md").write_text("直接写推荐动作。\n", encoding="utf-8")
            output = io.StringIO()

            with patch.object(checker, "ROOT", root), redirect_stdout(output):
                result = checker.main()

        report = output.getvalue()
        self.assertEqual(result, 1)
        self.assertIn("index.html:1: 不", report)
        self.assertIn("index.html:1: 未", report)
        self.assertIn("index.html:3: 禁止", report)
        self.assertEqual(report.count("index.html:1:"), 2)
        self.assertIn("…", report)


class MarkdownTests(unittest.TestCase):
    def test_fenced_examples_and_comments_are_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "README.md")
            path.write_text(
                "直接写推荐动作。\n```html\n<p>未完成</p>\n```\n<!-- 不要扫描 -->\n",
                encoding="utf-8",
            )

            self.assertEqual(checker.markdown_copy(path), [(1, "直接写推荐动作。")])


if __name__ == "__main__":
    unittest.main()
