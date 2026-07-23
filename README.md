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
