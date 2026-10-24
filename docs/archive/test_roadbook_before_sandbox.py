from __future__ import annotations

import json
import re
import subprocess
import unittest
from html.parser import HTMLParser
from pathlib import Path

import check_positive_copy as checker


ROOT = Path(__file__).resolve().parents[1]
INDEX_SOURCE = ROOT.joinpath("index.html").read_text(encoding="utf-8")
MANIFEST = json.loads(ROOT.joinpath("manifest.webmanifest").read_text(encoding="utf-8"))
SERVICE_WORKER_SOURCE = ROOT.joinpath("service-worker.js").read_text(encoding="utf-8")


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


def run_nearest_station_matcher(
    spots: list[dict[str, float | str]],
    *,
    latitude: float,
    longitude: float,
    source: str = INDEX_SOURCE,
) -> dict[str, object] | None:
    try:
        start = source.index("      const locationMath = (() => {")
        end = source.index("      const spotKnownCoordinates =", start)
    except ValueError:
        return None

    harness = source[start:end] + """
const result = locationMath.nearestSpotByCoordinates(
  JSON.parse(process.argv[1]),
  Number(process.argv[2]),
  Number(process.argv[3])
);
process.stdout.write(JSON.stringify(result));
"""
    result = subprocess.run(
        ["node", "-e", harness, json.dumps(spots), str(latitude), str(longitude)],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    return json.loads(result.stdout)


def run_station_copy_text(
    parts: dict[str, str], source: str = INDEX_SOURCE
) -> str | None:
    try:
        start = source.index("      const stationBodyTextFromParts =")
        end = source.index("      const spotBodyText =", start)
    except ValueError:
        return None

    harness = source[start:end] + """
process.stdout.write(stationBodyTextFromParts(JSON.parse(process.argv[1])));
"""
    result = subprocess.run(
        ["node", "-e", harness, json.dumps(parts, ensure_ascii=False)],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    return result.stdout


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
    def test_pwa_manifest_and_ios_icon_are_wired(self) -> None:
        self.assertIn('<link rel="manifest" href="manifest.webmanifest" />', INDEX_SOURCE)
        self.assertIn('<link rel="apple-touch-icon" href="assets/app-icon-180.png" />', INDEX_SOURCE)
        self.assertEqual(MANIFEST["display"], "standalone")
        self.assertEqual(MANIFEST["start_url"], "./")
        self.assertEqual({icon["sizes"] for icon in MANIFEST["icons"]}, {"192x192", "512x512"})
        for size in (180, 192, 512):
            self.assertTrue(ROOT.joinpath(f"assets/app-icon-{size}.png").exists())

    def test_service_worker_precaches_the_offline_shell(self) -> None:
        self.assertIn('navigator.serviceWorker.register("./service-worker.js"', INDEX_SOURCE)
        for asset in ("./index.html", "./manifest.webmanifest", "./scripts/amap-config.js"):
            self.assertIn(f'"{asset}"', SERVICE_WORKER_SOURCE)
        self.assertIn('request.mode === "navigate"', SERVICE_WORKER_SOURCE)
        self.assertIn('await caches.match("./index.html")', SERVICE_WORKER_SOURCE)

    def test_929_mogao_purchase_and_hard_times_are_consistent(self) -> None:
        for expected_copy in (
            "常规 A 类票已购 · 两人 476",
            "莫高窟 9.29 14:00 常规 A 类票 ×2 · 已购 476",
        ):
            self.assertIn(expected_copy, VISIBLE_TEXT)
        for expected_markup in (
            "<b>上午</b> 城市散步",
            "<b>13:15前</b> 停好车",
            "<b>13:30前</b> 到数字中心",
            "<b>14:00</b> 莫高入场",
        ):
            self.assertIn(expected_markup, INDEX_SOURCE)
        self.assertNotIn("计划预约 9 月 29 日下午场", VISIBLE_TEXT)

    def test_nearby_options_never_reuse_the_day_cover_as_a_fallback(self) -> None:
        self.assertIn("const nearbyImageByTitle = {", INDEX_SOURCE)
        self.assertNotIn("const fallbackImage = dayCover", INDEX_SOURCE)
        self.assertNotIn('generatedSpot.dataset.full = fallbackImage', INDEX_SOURCE)
        self.assertIn('const imageUrl = spot?.dataset.full || dedicatedImage;', INDEX_SOURCE)

        mapping_start = INDEX_SOURCE.index("const nearbyImageByTitle = {")
        mapping_end = INDEX_SOURCE.index("      };", mapping_start)
        mapping_source = INDEX_SOURCE[mapping_start:mapping_end]
        image_urls = [
            line.split('"')[3]
            for line in mapping_source.splitlines()
            if line.strip().startswith('"') and line.count('"') >= 4
        ]
        self.assertEqual(len(image_urls), len(set(image_urls)))

    def test_nearest_station_matcher_prefers_geographically_closest_station(self) -> None:
        result = run_nearest_station_matcher(
            [
                {"id": "helan", "title": "贺兰山", "lat": 38.727, "lng": 105.997},
                {"id": "danxia", "title": "七彩丹霞", "lat": 38.970, "lng": 100.120},
            ],
            latitude=38.972,
            longitude=100.062,
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["spot"]["id"], "danxia")
        self.assertLess(result["distanceKm"], 6)
        self.assertIsNone(run_nearest_station_matcher([], latitude=38.972, longitude=100.062))

    def test_station_copy_text_reads_only_the_station_body(self) -> None:
        result = run_station_copy_text(
            {
                "title": "七彩丹霞",
                "meta": "9.28 傍晚",
                "teaser": "等斜光。",
                "aside": "岩层显出颜色",
                "detail": "沿观景台慢慢走。",
            }
        )

        self.assertEqual(
            result,
            "沿观景台慢慢走。",
        )

    def test_exact_names_and_marked_quotation_are_visible(self) -> None:
        self.assertIn("瓜州大地之子与无界", VISIBLE_TEXT)
        self.assertIn("梵尘别院", VISIBLE_TEXT)
        self.assertIn("「无垠的沙漠热烈追求一叶绿草的爱，她摇摇头笑着飞开了。」", VISIBLE_TEXT)
        self.assertNotIn("瓜州荒野雕塑群", VISIBLE_TEXT)
        self.assertNotIn("梵尘民宿", VISIBLE_TEXT)

    def test_930_city_day_replaces_the_west_line_obligation(self) -> None:
        day_start = INDEX_SOURCE.index('<details class="day" id="d930"')
        day_end = INDEX_SOURCE.index('<details class="day" id="d1001"', day_start)
        day = INDEX_SOURCE[day_start:day_end]
        for expected in ("无界", "印局", "旅行写真", "鸣沙山", "收藏池", "傍晚", "尚待实测"):
            self.assertIn(expected, day)
        self.assertNotIn("09:00 出城", day)
        self.assertNotIn("9.30 09:00 西线出发", VISIBLE_TEXT)
        self.assertNotIn("第二天 09:00 还要走敦煌西线", VISIBLE_TEXT)
        self.assertIn("当天公示的末班车与日落安排", VISIBLE_TEXT)
        self.assertIn("官方班次允许时预留一班余量", VISIBLE_TEXT)

    def test_shapotou_is_saved_for_a_separate_half_day(self) -> None:
        heading_position = INDEX_SOURCE.index("<h4>沙坡头</h4>")
        option_start = INDEX_SOURCE.rfind("<article", 0, heading_position)
        option_end = INDEX_SOURCE.index("</article>", heading_position)
        option_source = INDEX_SOURCE[option_start:option_end]
        self.assertIn('class="nearby-option skip"', option_source)
        self.assertIn("收藏池 · 另留半天", option_source)
        self.assertIn("本次转场日收进收藏池", option_source)

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
        # Generated stories retain the actual day's instructions, including
        # deferred stops, separately from the opening of the narration.
        self.assertIn('aside.textContent = teaser.textContent;', INDEX_SOURCE)
        self.assertIn('aside.className = "spot-detail spot-prose";', INDEX_SOURCE)
        self.assertIn('if (opening) teaser.textContent = opening.textContent;', INDEX_SOURCE)
        self.assertLess(
            INDEX_SOURCE.index('aside.textContent = teaser.textContent;'),
            INDEX_SOURCE.index('if (opening) teaser.textContent = opening.textContent;'),
        )
        self.assertIn("这次经过，专程参观另留半天", VISIBLE_TEXT)
        self.assertIn("独立安排一天", VISIBLE_TEXT)
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


    def test_actual_timing_and_primary_limits_are_consistent(self) -> None:
        days = re.findall(r'<details class="day" id="(d[0-9]+)".*?(?=<details class="day"|<section id="citywalk")', INDEX_SOURCE, re.S)
        self.assertEqual(len(days), 12)
        plans = re.findall(r'<ol class="main-plan">(.*?)</ol>', INDEX_SOURCE, re.S)
        self.assertEqual(len(plans), 12)
        for plan in plans:
            self.assertLessEqual(plan.count("<li>"), 3)
            self.assertGreaterEqual(plan.count("<li>"), 1)
        for timing in ("10:00 出发", "11:00 到首个园区", "15:00 左右出园", "17:30 进场", "18:20 左右到4号观景台"):
            self.assertIn(timing, VISIBLE_TEXT)
        for stale in ("最迟 17:00", "17:30 前入园", "嘉峪关南湖车宿", "入住漫葡天沐"):
            self.assertNotIn(stale, VISIBLE_TEXT)
        self.assertIn("实付待补记", VISIBLE_TEXT)

    def test_city_guide_navigation_and_station_layers(self) -> None:
        guide_ids = re.findall(r'<details class="city-guide layer" id="([^"]+)"', INDEX_SOURCE)
        self.assertEqual(len(guide_ids), 10)
        for guide_id in guide_ids:
            self.assertIn('href="#' + guide_id + '"', INDEX_SOURCE)
        self.assertIn('window.addEventListener("hashchange", openCityGuide)', INDEX_SOURCE)
        self.assertIn("敦煌无界", VISIBLE_TEXT)
        self.assertIn("敦煌印局", VISIBLE_TEXT)
        self.assertIn("拜寺口双塔", VISIBLE_TEXT)
        self.assertIn("贺兰山东麓酒庄", VISIBLE_TEXT)
        self.assertEqual(INDEX_SOURCE.count('class="station-priority"'), 23)
        self.assertIn('priority.className = "station-priority"', INDEX_SOURCE)
        self.assertIn('point.type !== "optional"', INDEX_SOURCE)
        self.assertIn('const CACHE_VERSION = "qinggan-roadbook-', SERVICE_WORKER_SOURCE)


if __name__ == "__main__":
    unittest.main()
