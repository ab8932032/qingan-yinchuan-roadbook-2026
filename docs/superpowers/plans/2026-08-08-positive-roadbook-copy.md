# Positive Roadbook Copy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite every user-visible roadbook sentence as a positive recommendation, direct fact, executable condition, or current-state instruction.

**Architecture:** Keep the single-page structure and route data unchanged. Add a small Python acceptance checker that extracts rendered HTML text, accessibility attributes, user-visible JavaScript string literals, and README prose, then reports reverse phrasing. Use that report as the editorial work queue and finish with browser-level sampling of the main reading surfaces.

**Tech Stack:** HTML, CSS, vanilla JavaScript, Python 3 standard library, PowerShell, local HTTP preview.

## Global Constraints

- Every user-visible sentence must state what to do, when to do it, what the place is, or what information is currently available.
- Rewrite factual negation as direct factual description.
- Rewrite safety negation as an executable safe action.
- Keep the main route, attraction data, map algorithms, card structure, folding behavior, and visual layout unchanged.
- Apply the same positive-writing rule to `README.md`.
- Code comments, program branches, error handling, and third-party field names are outside the prose rule.
- Perform semantic rewrites; never remove or replace negative characters mechanically.

---

### Task 1: Add a user-visible copy checker

**Files:**
- Create: `tests/check_positive_copy.py`
- Read: `index.html`
- Read: `README.md`

**Interfaces:**
- Consumes: repository-root `index.html` and `README.md` encoded as UTF-8.
- Produces: exit code `0` when extracted user-visible copy contains no reverse phrasing; exit code `1` plus `path:line: phrase` reports otherwise.

- [ ] **Step 1: Write the failing acceptance checker**

Create `tests/check_positive_copy.py` with a real HTML extraction pass rather than a source grep:

```python
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
```

- [ ] **Step 2: Run the checker and verify RED**

Run:

```powershell
python tests/check_positive_copy.py
```

Expected: exit code `1` with current examples such as `不建议当天加入`, `不要直接开往窟区`, factual `不是/并不是`, and README reverse rules.

- [ ] **Step 3: Mutation-check the extractor**

Create a temporary copy of the checker input in memory by invoking the parser from a one-off Python command with `<p>车辆驶入正规停车区后再拍照</p>` and `<p>不要在公路停车</p>`. Confirm the first produces no match and the second produces `不`. Do not modify production files for this check.

- [ ] **Step 4: Commit the failing acceptance checker**

```powershell
git add tests/check_positive_copy.py
git commit -m "test: detect reverse phrasing in roadbook copy"
```

---

### Task 2: Rewrite the complete roadbook and editing rules

**Files:**
- Modify: `index.html`
- Modify: `README.md`
- Test: `tests/check_positive_copy.py`

**Interfaces:**
- Consumes: every failure reported by `python tests/check_positive_copy.py`.
- Produces: semantically equivalent route guidance expressed entirely through positive actions and direct facts.

- [ ] **Step 1: Export the editorial work queue**

Run:

```powershell
python tests/check_positive_copy.py 2>&1 | Tee-Object positive-copy-report.txt
```

Read every reported `index.html` and `README.md` line. Keep `positive-copy-report.txt` untracked and delete it after the task.

- [ ] **Step 2: Rewrite itinerary summaries and daily action copy**

Edit the overview timeline, daily cards, day leads, nearby-option summaries, tiers, costs, and action lists. Apply these concrete transformations throughout:

```text
“不再赶路” → “留宿山下，整晚休息”
“不建议当天加入” → “适合另排半天”
“不额外停车” → “沿途车览”
“今天不再追景点” → “今天专注返程”
“否则不拿夜路交换” → “12:00 前离开西夏陵且驾驶状态充足时加入”
```

When a choice is excluded, name the recommended plan first and place the alternative in a future positive slot: `当天把斜光留给七彩丹霞；冰沟丹霞适合另排半天。`

- [ ] **Step 3: Rewrite safety guidance as executable actions**

Cover parking, alcohol, protected areas, private pasture, road shoulders, salt crust, cave photography, night driving, charging, and car sleeping. Use forms such as:

```text
“不要直接开往窟区” → “导航至莫高窟数字展示中心，从这里乘摆渡车进入窟区”
“不在公路停车” → “车辆驶入正规停车区后再拍照”
“司机不碰酒” → “司机全程保持零酒精”
“不要穿过私人牧场” → “沿公开入口和开放岸线进入湖边”
```

- [ ] **Step 4: Rewrite factual descriptions as direct explanations**

Cover route introduction and all `spot-teaser` / `spot-aside` prose. State origins and composition directly:

```text
“翡翠湖并不是一整片天然湖面” → “翡翠湖由盐业开采留下的采坑与盐池组成”
“水上雅丹并不是在水下长成的” → “雅丹先在旱地形成，河流改道后湖水包围土丘”
“漫葡不是一座真正的古镇” → “漫葡是一座以酒庄文化、温泉和夜游构成的现代小镇”
```

- [ ] **Step 5: Rewrite dynamic and accessibility copy**

Edit JavaScript strings assigned to `textContent`, HTML strings returned for weather cards, generated spot prose, map status, image fallbacks, `aria-label`, `alt`, `title`, and placeholder attributes. Keep technical branching unchanged. Required state pattern:

```text
“尚未开放” → “等待行程预报”
“这是地点实况，不是行程日预测” → “当前展示地点实况；行程日预报将在进入未来16天后显示”
“部分道路暂未算出” → “完整行程底线已显示；详细道路正在分段载入”
```

- [ ] **Step 6: Rewrite README as affirmative editing guidance**

Replace contrastive prohibitions with explicit desired outcomes. The central rule must read in substance: `成品只写推荐动作、实际路线、执行条件和地点事实。每句话直接回答读者接下来做什么。` Preserve all factual setup instructions and code examples.

- [ ] **Step 7: Run the checker until GREEN**

Run:

```powershell
python tests/check_positive_copy.py
```

Expected: exit code `0`, `Positive-copy check passed.`

Inspect every rewrite made after the last failing run; confirm it preserves the original route decision, time condition, and safety meaning.

- [ ] **Step 8: Run structural regression checks**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check-nearby-attractions.ps1
@'
from html.parser import HTMLParser
from pathlib import Path
p = HTMLParser()
p.feed(Path("index.html").read_text(encoding="utf-8"))
p.close()
print("HTML parser passed")
'@ | python -
git diff --check
```

Expected: nearby-attraction checks pass, HTML parser passes, and `git diff --check` exits `0`.

- [ ] **Step 9: Commit the complete prose rewrite**

```powershell
Remove-Item -LiteralPath positive-copy-report.txt -ErrorAction SilentlyContinue
git add index.html README.md tests/check_positive_copy.py
git commit -m "style: rewrite roadbook guidance as positive actions"
```

---

### Task 3: Verify the rendered reading experience

**Files:**
- Verify: `index.html`
- Verify: `README.md`
- Test: `tests/check_positive_copy.py`

**Interfaces:**
- Consumes: locally served roadbook page after Task 2.
- Produces: evidence that positive copy is visible across all major reading surfaces without layout or interaction regressions.

- [ ] **Step 1: Start a local preview**

Run a hidden local server from the repository root:

```powershell
$preview = Start-Process -FilePath python -ArgumentList '-m','http.server','8765' -WorkingDirectory (Get-Location) -WindowStyle Hidden -PassThru
$preview.Id
```

- [ ] **Step 2: Inspect the major surfaces in the in-app browser**

Open `http://127.0.0.1:8765/index.html` and verify:

- The overview timeline recommends the day’s action directly.
- At least one nearby option in each region uses positive timing or suitability labels.
- `风里的站` factual paragraphs state composition and history directly.
- Long `风里的站` copy still scrolls inside the fixed 贺兰山-height frame.
- Weather waiting cards describe current data and the future forecast window positively.
- Map status states what is visible and how many detailed layers are loaded.
- Accommodation and safety copy gives executable actions.

- [ ] **Step 3: Verify browser console and responsive layout**

Check desktop and a narrow mobile viewport. Confirm there are no new console errors, clipped controls, missing titles, empty cards, or expanded whitespace caused by the text changes.

- [ ] **Step 4: Stop the exact preview process and run final checks**

```powershell
Stop-Process -Id $preview.Id
python tests/check_positive_copy.py
powershell -ExecutionPolicy Bypass -File scripts/check-nearby-attractions.ps1
git status --short
```

Expected: both checks pass; only intentional files are modified or the tree is clean after commits.

- [ ] **Step 5: Commit verification-only adjustments if required**

If rendered verification required copy wrapping or accessibility wording adjustments:

```powershell
git add index.html README.md tests/check_positive_copy.py
git commit -m "fix: refine positive roadbook copy after visual review"
```

If no files changed, skip this commit.
