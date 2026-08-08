from __future__ import annotations

import json
import subprocess
import unittest
from html.parser import HTMLParser
from pathlib import Path

import check_positive_copy as checker


ROOT = Path(__file__).resolve().parents[1]
INDEX_SOURCE = ROOT.joinpath("index.html").read_text(encoding="utf-8")


def extracted_visible_items() -> list[tuple[int, str]]:
    parser = checker.VisibleCopy()
    parser.feed(INDEX_SOURCE)
    parser.close()
    return (
        parser.items
        + checker.js_visible_strings(parser.script_parts)
        + checker.css_visible_strings(parser.style_parts)
    )


VISIBLE_ITEMS = extracted_visible_items()
VISIBLE_TEXT = "\n".join(text for _, text in VISIBLE_ITEMS)


def render_out_of_window_cached_weather(source: str = INDEX_SOURCE) -> dict[str, str]:
    render_start = source.index("      const renderWeatherData =")
    render_end = source.index("      const syncWeather =", render_start)
    render_function = source[render_start:render_end]
    harness = """
const weatherGrid = { innerHTML: "" };
const weatherSummary = { textContent: "" };
const weatherWindowNote = { textContent: "" };
const weatherPlaces = [{
  date: "2026-09-25",
  dateLabel: "9.25",
  timeLabel: "17:00 前后",
  label: "贺兰山宿集",
  hour: 17
}];
const weatherDayMs = 24 * 60 * 60 * 1000;
const weatherDaysFromToday = () => 30;
const weatherPointLine = () => "景点坐标";
const weatherOpenDate = () => new Date(Date.UTC(2026, 8, 10));
const weatherRound = (value) => Number.isFinite(value) ? Math.round(value) : null;
const weatherRiskText = () => "";
const weatherShortDate = () => "9/10";
const weatherText = () => "晴";
const weatherTodayAtBeijing = () => new Date(Date.UTC(2026, 7, 8));
const weatherDateAtBeijing = (value) => new Date(value);
""" + render_function + """
renderWeatherData({
  current: {
    temperature_2m: 22,
    apparent_temperature: 21,
    wind_gusts_10m: 18,
    cloud_cover: 10,
    weather_code: 0
  },
  daily: { time: [] },
  hourly: { time: [] }
}, true);
process.stdout.write(JSON.stringify({
  grid: weatherGrid.innerHTML,
  note: weatherWindowNote.textContent
}));
"""
    result = subprocess.run(
        ["node", "-e", harness],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    return json.loads(result.stdout)


class NearbyStructure(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.detail_stack: list[str | None] = []
        self.days_with_nearby: set[str] = set()
        self.nearby_option_count = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = set((values.get("class") or "").split())
        if tag == "article" and "nearby-option" in classes:
            self.nearby_option_count += 1
        if tag != "details":
            return
        detail_id = values.get("id")
        active_day = next((item for item in reversed(self.detail_stack) if item), None)
        if detail_id and detail_id.startswith("d"):
            active_day = detail_id
        if active_day and "nearby-options" in classes:
            self.days_with_nearby.add(active_day)
        self.detail_stack.append(detail_id if detail_id and detail_id.startswith("d") else None)

    def handle_endtag(self, tag: str) -> None:
        if tag == "details" and self.detail_stack:
            self.detail_stack.pop()


class RoadbookContentTests(unittest.TestCase):
    def test_exact_names_and_marked_quotation_are_visible(self) -> None:
        self.assertIn("瓜州大地之子与无界", VISIBLE_TEXT)
        self.assertIn("梵尘别院", VISIBLE_TEXT)
        self.assertIn("「无垠的沙漠热烈追求一叶绿草的爱，她摇摇头笑着飞开了。」", VISIBLE_TEXT)
        self.assertNotIn("瓜州荒野雕塑群", VISIBLE_TEXT)
        self.assertNotIn("梵尘民宿", VISIBLE_TEXT)

    def test_930_uses_0900_as_the_west_line_departure_everywhere(self) -> None:
        self.assertIn("9.30 09:00 西线出发", VISIBLE_TEXT)
        self.assertIn("09:00 出城", VISIBLE_TEXT)
        for conflicting_copy in (
            "13:00 左右去西线",
            "吃过午饭再去敦煌西线",
            "第二天下午还要走敦煌西线",
            "一两点前",
            "可睡懒觉",
            "倒数第二班",
            "末班常见约 18:30",
            "末班观光车常见约 18:30",
        ):
            self.assertNotIn(conflicting_copy, VISIBLE_TEXT)
        self.assertIn("当天公示的末班车与日落安排", VISIBLE_TEXT)
        self.assertIn("官方班次允许时预留一班余量", VISIBLE_TEXT)
        self.assertIn("第二天 09:00 还要走敦煌西线", VISIBLE_TEXT)

    def test_shapotou_tier_matches_the_current_trip_conditional_decision(self) -> None:
        heading_position = INDEX_SOURCE.index("<h4>沙坡头</h4>")
        option_start = INDEX_SOURCE.rfind("<article", 0, heading_position)
        option_end = INDEX_SOURCE.index("</article>", heading_position)
        option_source = INDEX_SOURCE[option_start:option_end]

        self.assertIn('class="nearby-option"', option_source)
        self.assertIn('<span class="nearby-tier">条件满足时加入</span>', option_source)
        self.assertIn("12:00 前离开西夏陵且驾驶状态充足时加入", option_source)
        self.assertNotIn("适合另排", option_source)
        self.assertIn(
            "12:00 前离开西夏陵且两位司机状态充足时，可以顺路在中卫沙坡头停一两小时",
            VISIBLE_TEXT,
        )

    def test_terminal_map_and_weather_statuses_state_results_and_fallbacks(self) -> None:
        self.assertIn("完整行程底线已显示；已载入 ", VISIBLE_TEXT)
        self.assertIn(" 个日期的详细道路；其余日期可使用下方分段导航。", VISIBLE_TEXT)
        self.assertIn("高德地图连接异常；下方路线示意与分段导航可继续使用", VISIBLE_TEXT)
        self.assertIn("坐标天气连接异常", VISIBLE_TEXT)
        self.assertNotIn("详细道路正在分段载入", VISIBLE_TEXT)
        self.assertNotIn("高德地图等待连接", VISIBLE_TEXT)
        self.assertNotIn("坐标天气等待连接", VISIBLE_TEXT)
        self.assertIn("网络异常，显示上次缓存；点击“刷新预报”可重试", VISIBLE_TEXT)
        self.assertIn("当前显示上次缓存；点击“刷新预报”可重试。", VISIBLE_TEXT)

    def test_cached_waiting_weather_path_renders_retry_on_card_and_window_note(self) -> None:
        rendered = render_out_of_window_cached_weather()

        self.assertIn("等待行程预报", rendered["grid"])
        self.assertIn("网络异常，显示上次缓存；点击“刷新预报”可重试", rendered["grid"])
        self.assertTrue(
            rendered["note"].startswith("当前显示上次缓存；点击“刷新预报”可重试。"),
            rendered["note"],
        )

    def test_generated_stop_guidance_respects_immediate_and_deferred_tiers(self) -> None:
        self.assertIn("按上方时间成本与执行条件加入本次行程", VISIBLE_TEXT)
        self.assertIn("按上方绕行成本加入本次行程", VISIBLE_TEXT)
        self.assertIn("单独安排；本次行程继续遵循当天主路线", VISIBLE_TEXT)
        self.assertNotIn("这处停靠适合在时间、天气与精神都宽裕时加入", VISIBLE_TEXT)

    def test_chaka_and_u315_decisions_are_explicit(self) -> None:
        self.assertIn(
            "本次直接经过茶卡，把傍晚留给青海湖东岸；茶卡完整游览需另排半天。",
            VISIBLE_TEXT,
        )
        self.assertIn(
            "人员在停车区一侧的观景范围内活动；前往另一侧时，所有人先上车，由驾驶员从正规入口驶入对侧停车区后再下车。",
            VISIBLE_TEXT,
        )

    def test_refined_safety_budget_and_forecast_copy_is_visible(self) -> None:
        for copy in (
            "膝盖疼痛或负担明显",
            "明显高原反应",
            "在高速服务区或熟悉路线沿线补给",
            "车内关闭全部火源，热食在服务区完成",
            "当行程日期进入未来 16 天预报范围后",
            "基础门票之外",
            "其他私人安排另行确认",
            "只看待办",
        ):
            self.assertIn(copy, VISIBLE_TEXT)

    def test_nearby_structure_is_durably_covered_without_compatibility_comments(self) -> None:
        parser = NearbyStructure()
        parser.feed(INDEX_SOURCE)
        parser.close()

        expected_days = {
            "d926", "d927", "d928", "d929", "d930", "d1001", "d1002", "d1003", "d1004"
        }
        self.assertTrue(expected_days.issubset(parser.days_with_nearby), expected_days - parser.days_with_nearby)
        self.assertGreaterEqual(parser.nearby_option_count, 12)
        self.assertNotIn("旧版结构检查的层级标记", INDEX_SOURCE)


if __name__ == "__main__":
    unittest.main()
