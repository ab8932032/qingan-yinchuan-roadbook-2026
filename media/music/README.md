# 每日短片配乐

本项目的三组原创合成轻器乐：`courtyard.wav`（院落）、`open-road.wav`（荒原）、`lake-light.wav`（湖光）。旋律、和弦及音色由本地脚本编排和合成，未导入外部曲库或采样。

`python scripts/compose_film_music.py` 生成母带；`build_daily_films.py` 根据每日配置把配乐编码为 AAC、渐入渐出后写进 MP4。曲目信息见 `credits.json`。

播放器保留原生音量控制，并在纸片画面下方提供配乐开关。浏览器允许时随点击播放有声影片；首次自动播放被限制时先静音播放，点“开启配乐”即可。音量开关偏好只存在当前浏览器。
