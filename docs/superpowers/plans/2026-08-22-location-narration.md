# 风里的站定位与旁白 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让用户可定位并自动打开最近的“风里的站”，且可用系统语音朗读该站正文。

**Architecture:** 在现有单页 `index.html` 的风里站脚本中加入两个纯函数：一个计算 Haversine 距离，一个从坐标列表找出最近站。界面层从已有高德标注链接和少量补齐坐标建立站点数据，再调用浏览器的单次定位与 `speechSynthesis`；按钮与状态置于既有风里站导航区和每站操作区。

**Tech Stack:** 原生 HTML、CSS、JavaScript、Python `unittest`、Node.js 测试 harness。

## Global Constraints

- 不新增运行时依赖或第三方位置/语音服务。
- 定位、朗读均只由用户点击触发；不持续追踪、不自动播放声音。
- 最近站基于近似坐标匹配，状态不得将远距离位置称为“已到达”。
- 保持现有中文文案、横滑、筛选、导航与无障碍模式兼容。

---

### Task 1: 为最近站匹配建立可执行回归测试

**Files:**
- Modify: `tests/test_roadbook_content.py`

**Interfaces:**
- Consumes: `nearestSpotByCoordinates(spots, latitude, longitude)`，返回最近站对象或 `null`。
- Produces: Node harness 在真实内联脚本上验证的地理匹配回归测试。

- [ ] **Step 1: 写出失败测试**

```python
def test_nearest_station_matcher_prefers_geographically_closest_station(self) -> None:
    result = run_nearest_station_matcher(
        [
            {"id": "helan", "title": "贺兰山", "lat": 38.727, "lng": 105.997},
            {"id": "danxia", "title": "七彩丹霞", "lat": 38.970, "lng": 100.120},
        ],
        latitude=38.972,
        longitude=100.062,
    )
    self.assertEqual(result["id"], "danxia")
```

- [ ] **Step 2: 验证失败**

Run: `python -m unittest tests.test_roadbook_content.RoadbookContentTests.test_nearest_station_matcher_prefers_geographically_closest_station -v`

Expected: FAIL，因为最近站函数尚不存在。

- [ ] **Step 3: 写最小实现**

```js
const nearestSpotByCoordinates = (spots, latitude, longitude) => {
  // 使用 Haversine 距离遍历有效坐标，返回 `{ spot, distanceKm }` 或 null。
};
```

- [ ] **Step 4: 验证通过**

Run: `python -m unittest tests.test_roadbook_content.RoadbookContentTests.test_nearest_station_matcher_prefers_geographically_closest_station -v`

Expected: PASS。

### Task 2: 实现定位控件与最近站自动切换

**Files:**
- Modify: `index.html:风里的站标题区、样式区、风里站脚本`
- Test: `tests/test_roadbook_content.py`

**Interfaces:**
- Consumes: `nearestSpotByCoordinates(spots, latitude, longitude)` 与现有 `applySpotFilter`、`goSpot`。
- Produces: “定位当前站”按钮、状态区域、站点坐标收集与单次地理定位处理。

- [ ] **Step 1: 扩展失败测试以覆盖空输入**

```python
self.assertIsNone(run_nearest_station_matcher([], latitude=38.972, longitude=100.062))
```

- [ ] **Step 2: 验证失败**

Run: `python -m unittest tests.test_roadbook_content.RoadbookContentTests.test_nearest_station_matcher_prefers_geographically_closest_station -v`

Expected: FAIL，直到空输入处理已实现。

- [ ] **Step 3: 实现控件和状态**

```html
<div class="spot-location no-print">
  <button id="spotLocate" type="button">定位当前站</button>
  <p id="spotLocateStatus" role="status" aria-live="polite">点击定位，自动打开离你最近的风里的站。</p>
</div>
```

从高德 `position` 参数和内置补齐表建立坐标；成功后显示最近站和约化距离、切换全部筛选并自动定位，失败时按权限、超时与不支持分别提示。

- [ ] **Step 4: 验证通过**

Run: `python -m unittest discover -s tests -v`

Expected: PASS。

### Task 3: 实现每站旁白朗读

**Files:**
- Modify: `index.html:风里的站样式与脚本`
- Test: `tests/test_roadbook_content.py`

**Interfaces:**
- Consumes: 站点的 `h3`、`.spot-meta`、`.spot-teaser`、`.spot-aside`、`.spot-detail`/`.spot-prose`。
- Produces: `spotNarrationText(slide)`、开始/停止朗读控制和用户可见状态。

- [ ] **Step 1: 写出失败测试**

```python
result = run_spot_narration_text({
    "title": "七彩丹霞", "meta": "9.28 傍晚", "teaser": "等斜光。",
    "aside": "岩层显出颜色。", "detail": "沿观景台慢慢走。"
})
self.assertEqual(result, "七彩丹霞。9.28 傍晚。等斜光。岩层显出颜色。沿观景台慢慢走。")
```

- [ ] **Step 2: 验证失败**

Run: `python -m unittest tests.test_roadbook_content.RoadbookContentTests.test_station_narration_text_preserves_reading_order -v`

Expected: FAIL，因为旁白文本函数尚不存在。

- [ ] **Step 3: 实现最小朗读控制**

```js
const utterance = new SpeechSynthesisUtterance(spotNarrationText(slide));
utterance.lang = "zh-CN";
utterance.rate = 0.92;
speechSynthesis.speak(utterance);
```

创建“朗读这一站”按钮，朗读期间变为“停止朗读”；结束、取消或浏览器不支持时恢复控制状态。文本只取可阅读的站点正文。

- [ ] **Step 4: 验证通过**

Run: `python -m unittest discover -s tests -v`

Expected: PASS。

### Task 4: 手动验证与交付检查

**Files:**
- Modify: `index.html`（仅修复验证发现的问题）

- [ ] **Step 1: 运行完整自动测试**

Run: `python -m unittest discover -s tests -v`

Expected: 全部 PASS。

- [ ] **Step 2: 浏览器手动检查**

打开 `index.html`，检查：拒绝定位的提示；允许定位后自动跳转；七彩丹霞手动翻页与筛选；朗读启动、停止、结束后按钮复位；窄屏按钮不溢出。

- [ ] **Step 3: 检查变更范围**

Run: `git diff --check && git status --short`

Expected: 无空白错误，只有功能、测试和文档相关文件变更。
