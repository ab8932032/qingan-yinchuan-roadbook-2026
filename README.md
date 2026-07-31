# 青甘银川 · 2026 自驾路书（Web）

手机友好的单页 HTML 路书：从粗到细分层，含景点介绍、预算、清单勾选，以及高德导航深链。

## 怎么打开

1. 用手机/电脑浏览器打开本目录下的 `index.html`  
   - Windows：双击，或把文件拖进 Chrome/Edge  
   - 也可放到任意静态托管（GitHub Pages / 网盘分享链接）
2. **手机加到主屏幕**（像 App）  
   - iOS Safari：分享 → 添加到主屏幕  
   - Android Chrome：菜单 → 添加到主屏幕 / 安装应用
3. 配图来自 Unsplash，需联网；高德按钮在手机上可唤起高德 App。

## 页面结构（关心程度由浅入深）

| 区块 | 内容 |
|------|------|
| 先看这个 | 整趟顺序、怎么排 |
| 路线 | 站点 + 高德导航 |
| 按天 | 每天细节（可折叠） |
| 景点 | 怎么玩、大概票价 |
| 花钱 | 预算和住宿 |
| 待办 | 勾选清单（存在本机） |
| 零碎备忘 | 日落、吃的、充电、起床等 |

## 高德说明

- 使用 [高德 URI](https://lbs.amap.com/api/uri-api/guide/travel/route) 生成导航/标注链接（`callnative=1` 优先唤起 App）。
- 坐标为路书用近似点；到店请以「搜店名」为准。
- 若你有自己的高德 JS Key，可再升级为页内可拖拽多途径点路线（当前版本无需 Key）。

## 与 Markdown 原稿

详细底稿仍在：`C:\Users\Administrator\Documents\2026青甘银川自驾路书.md`  
本 HTML 为阅读/路上执行版；改行程时两边可同步更新。

## 本地预览（可选）

```bash
# 若已装 Python
python -m http.server 8080
# 浏览器打开 http://localhost:8080
```

## 后续加入旅途影像

- 照片可直接替换日程卡片或景点卡片中的 `<img>` 地址，现有大图灯箱会自动沿用。
- 视频可放进同一个 `.day-cover` 或 `.spot-img` 容器，使用 `<video controls playsinline preload="metadata" poster="封面图地址">`；页面已预留与照片一致的比例、底色和移动端播放样式。
- 建议每一天只留一张主图，其余素材放在对应景点卡片中；照片与短视频穿插会比连续堆叠更像一本旅途影集。
- 每个日期展开后都有“途中补记”，可以填写当天一句、实际节奏，并直接加入照片或视频。文字使用本地存储，媒体使用浏览器 IndexedDB；两者都只存在当前设备。清理浏览器数据或更换设备前，应先把重要内容另行备份。

### 统一媒体格式

所有正式素材使用同一套 `data-media` 规则：

```html
<!-- 静态照片：自动使用缓慢呼吸效果 -->
<div class="day-cover" data-media="photo" data-caption="9.28 · 平山湖">
  <img src="assets/2026-09-28-pingshanhu.jpg" alt="平山湖大峡谷" />
</div>

<!-- Live Photo：使用关联的 MOV/MP4，poster 是静态封面；自动静音循环 -->
<div class="day-cover" data-media="live" data-caption="风穿过峡谷">
  <video src="assets/2026-09-28-live.mov" poster="assets/2026-09-28-live.jpg" muted loop autoplay playsinline controls></video>
</div>

<!-- 普通视频：不使用呼吸效果，显示原生播放控件 -->
<div class="day-cover" data-media="video" data-caption="去往丹霞的路上">
  <video src="assets/2026-09-28-road.mp4" poster="assets/2026-09-28-road-cover.jpg" playsinline controls preload="metadata"></video>
</div>
```

“风里的站”背景也使用相同规则：照片保留 `data-full="图片地址"`；视频或 Live Photo 在对应 `.spot-slide` 上填写 `data-media="video"` 或 `data-media="live"`、`data-video="视频地址"`，并可用 `data-poster="封面地址"`。切换到视频时，照片呼吸动画会自动停止。

## 高德配置

高德 Web 端 Key 与安全密钥集中在 `scripts/amap-config.js`，主 HTML 不直接出现具体值。该文件会随 Git 提交。浏览器端地图无法从技术上完全隐藏 Key，正式部署时必须在高德控制台配置域名白名单和额度告警；若要隐藏安全密钥，需要改为服务端代理。
