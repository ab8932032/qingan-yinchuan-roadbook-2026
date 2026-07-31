(function () {
  "use strict";

  /*
   * 高德 Web 端 JS API 配置。
   * 本文件会随项目提交；浏览器端 Key 仍可在网络请求中查看，
   * 请务必在高德控制台配置正式域名白名单与额度告警。
   */
  var amapKey = "8fb38c2694be2eb80ed252eaf0ad0fec";
  window._AMapSecurityConfig = {
    securityJsCode: "a69ef31b0a92ed7f2d49cbe74b0743a3"
  };

  document.write(
    '<script src="https://webapi.amap.com/maps?v=2.0&key=' +
      encodeURIComponent(amapKey) +
      '&plugin=AMap.Driving,AMap.Weather,AMap.ToolBar,AMap.Scale"><\/script>'
  );
})();
