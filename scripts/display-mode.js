(() => {
  const root = document.documentElement;
  const embedded = window.self !== window.top && new URLSearchParams(location.search).get('view') === 'projection';
  const read = (key, fallback) => { try { return localStorage.getItem(key) || fallback; } catch (_) { return fallback; } };
  const save = (key, value) => { try { localStorage.setItem(key, value); } catch (_) {} };
  const storedWidth = Number(read('roadbook-reading-width', '1280'));
  const width = Number.isFinite(storedWidth) ? Math.min(1800, Math.max(960, storedWidth)) : 1280;
  const apply = (mode, size) => {
    root.classList.toggle('reading-wide', mode === 'wide');
    root.style.setProperty('--reading-width', `${size}px`);
    window.dispatchEvent(new Event('resize'));
  };
  if (embedded) {
    apply('wide', 1800);
    return;
  }
  const mode = read('roadbook-reading-mode', 'normal') === 'wide' ? 'wide' : 'normal';
  apply(mode, width);
  const controls = document.createElement('details');
  controls.className = 'display-tools no-print';
  controls.innerHTML = `<summary>显示模式</summary><div class="display-panel">
    <label>阅读布局 <select id="readingMode"><option value="normal">原版 · 手机阅读</option><option value="wide">宽屏 · 电脑阅读</option></select></label>
    <label id="readingWidthLabel">正文宽度 <output id="readingWidthValue"></output><input id="readingWidth" type="range" min="960" max="1800" step="40" aria-label="正文最大宽度"></label>
    <button type="button" id="openProjection">进入 16:9 投屏</button>
    <p>宽屏可调正文宽度；16:9 模式可调显示大小。手机投屏时，请同时横放手机。</p>
  </div>`;
  document.body.append(controls);
  const modeSelect = controls.querySelector('#readingMode');
  const widthInput = controls.querySelector('#readingWidth');
  modeSelect.value = mode;
  widthInput.value = width;
  const sync = () => {
    controls.querySelector('#readingWidthValue').textContent = `${widthInput.value} px`;
    controls.querySelector('#readingWidthLabel').hidden = modeSelect.value !== 'wide';
    apply(modeSelect.value, Number(widthInput.value));
    save('roadbook-reading-mode', modeSelect.value);
    save('roadbook-reading-width', widthInput.value);
  };
  sync();
  modeSelect.addEventListener('change', sync);
  widthInput.addEventListener('input', sync);

  const dialog = document.createElement('dialog');
  dialog.className = 'projection-dialog no-print';
  dialog.setAttribute('aria-label', '16:9 路书投屏');
  dialog.innerHTML = `<div class="projection-toolbar">
    <strong>16:9 投屏</strong>
    <label>显示大小 <select id="projectionSize"><option value="1600">小 · 更多内容</option><option value="1280" selected>中 · 标准</option><option value="960">大 · 远距离阅读</option></select></label>
    <button type="button" id="projectionFullscreen">全屏</button>
    <button type="button" id="closeProjection">退出投屏</button>
  </div><div class="projection-space"><div class="projection-frame"></div></div>
  <p class="projection-help" role="status">画面固定为 16:9，内容可上下滚动；底部导航可切换章节。</p>`;
  document.body.append(dialog);
  const sizeSelect = dialog.querySelector('#projectionSize');
  const savedSize = read('roadbook-projection-size', '1280');
  sizeSelect.value = ['960', '1280', '1600'].includes(savedSize) ? savedSize : '1280';
  const space = dialog.querySelector('.projection-space');
  const frame = dialog.querySelector('.projection-frame');
  let iframe;
  const resize = () => {
    if (!dialog.open || !iframe) return;
    const w = Number(sizeSelect.value), h = w * 9 / 16;
    const scale = Math.min(space.clientWidth / w, space.clientHeight / h);
    frame.style.width = `${w * scale}px`;
    frame.style.height = `${h * scale}px`;
    iframe.style.width = `${w}px`;
    iframe.style.height = `${h}px`;
    iframe.style.transform = `scale(${scale})`;
  };
  new ResizeObserver(resize).observe(space);
  sizeSelect.addEventListener('change', () => { save('roadbook-projection-size', sizeSelect.value); resize(); });
  controls.querySelector('#openProjection').addEventListener('click', () => {
    controls.open = false;
    iframe = document.createElement('iframe');
    iframe.title = '青甘银川路书 · 16:9 横屏阅读';
    const url = new URL(location.href);
    url.searchParams.set('view', 'projection');
    // Start with the itinerary when opening from the cover, retaining chapter links.
    if (!url.hash || url.hash === '#top') url.hash = '#overview';
    iframe.src = url.href;
    frame.replaceChildren(iframe);
    dialog.showModal();
    root.classList.add('projection-open');
    resize();
  });
  dialog.querySelector('#closeProjection').addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => {
    root.classList.remove('projection-open');
    if (document.fullscreenElement === dialog) document.exitFullscreen().catch(() => {});
    frame.replaceChildren();
    iframe = null;
    controls.querySelector('summary').focus();
  });
  const fullscreen = dialog.querySelector('#projectionFullscreen');
  fullscreen.addEventListener('click', async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else if (dialog.requestFullscreen) await dialog.requestFullscreen();
      else throw new Error('Fullscreen unavailable');
    } catch (_) {
      dialog.querySelector('.projection-help').textContent = '当前浏览器未开启全屏，可使用浏览器全屏功能；16:9 画面仍可正常阅读。';
    }
  });
  document.addEventListener('fullscreenchange', () => {
    fullscreen.textContent = document.fullscreenElement ? '退出全屏' : '全屏';
    resize();
  });
})();
