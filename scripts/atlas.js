(() => {
  "use strict";
  const data = window.ROADBOOK;
  if (!data?.places?.length) return;
  const $ = (id) => document.getElementById(id);
  const escape = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const paragraphs = (items) => (items || []).map((p) => `<p>${escape(p)}</p>`).join("");
  const read = (key) => { try { return localStorage.getItem(key) || ""; } catch (_) { return ""; } };
  const noteKey = (id) => `roadbook-place:${id}:note`;
  const sessionNotes = new Map();
  const readNote = (id) => sessionNotes.has(id) ? sessionNotes.get(id) : read(noteKey(id));
  const places = data.places;
  const byId = new Map(places.map((p) => [p.id, p]));
  const mainPlaces = places.filter((p) => !p.parent);
  const viewport = $("mapViewport"), world = $("mapWorld"), panel = $("placePanel");
  const mobile = window.matchMedia("(max-width:760px)");
  const archive = window.JOURNEY_ARCHIVE;
  const plan = window.JOURNEY_PLAN;
  let recordTab = "memory", stageSize = { width: data.width, height: data.height };
  let selectedId = data.defaultPlace, lastTrigger = null, stageLayout = null;
  let view = { x: 0, y: 0, k: 1, min: .2, max: 2.2 }, initialized = false;
  let ignoredClickUntil = 0, renderToken = 0, mediaUrls = [], statusTimer;
  const say = (message) => {
    clearTimeout(statusTimer);
    $("appStatus").textContent = message;
    statusTimer = setTimeout(() => { $("appStatus").textContent = ""; }, 4400);
  };
  const pad = (number) => String(number).padStart(2, "0");
  const model = (kind, cls = "") => `<svg class="${cls}" viewBox="0 0 90 82" aria-hidden="true"><use href="#model-${escape(kind)}"/></svg>`;

  const point = (id) => stageLayout?.[id] ? { ...byId.get(id), ...stageLayout[id] } : byId.get(id);
  const segment = (a, b) => {
    if (a.id === "chengdu" && b.id === "helan") return `M${a.x},${a.y} C${stageSize.width - 20},${stageSize.height * .7} ${stageSize.width - 20},150 ${b.x},${b.y}`;
    if (stageLayout && a.id === "xining" && b.id === "chengdu") return `M${a.x},${a.y} C${stageSize.width - 15},${stageSize.height * .45} ${stageSize.width - 15},${stageSize.height - 100} ${b.x},${b.y}`;
    const dx = (b.x - a.x) * .52;
    return `M${a.x},${a.y} C${a.x + dx},${a.y} ${b.x - dx},${b.y} ${b.x},${b.y}`;
  };
  const landscapeLayoutName = () => !stageLayout ? "map" : (stageSize.height > 1200 ? "portrait" : (stageSize.width > 1400 ? "landscape" : "desktop"));
  const drawRoute = () => {
    const landscapeLayout = landscapeLayoutName();
    $("landscapeDrawing").innerHTML = (data.landscapes || []).map((feature) => {
      const [x,y,w,h,rotation,lx,ly] = feature.layouts[landscapeLayout];
      return `<g class="landform landform-${escape(feature.kind)}" data-landform="${escape(feature.id)}"><use class="landform-art" href="#terrain-${escape(feature.kind)}" x="${x-w/2}" y="${y-h/2}" width="${w}" height="${h}" transform="rotate(${rotation},${x},${y})"/><text class="landform-name" x="${lx}" y="${ly}">${escape(feature.name)}</text></g>`;
    }).join("");
    const routeD = data.route.slice(1).map((id, index) => segment(point(data.route[index]), point(id))).join(" ");
    $("routeUnder").setAttribute("d", routeD);
    $("routeMain").setAttribute("d", routeD);
    const settlements = places.filter((p) => p.branches?.length);
    $("settlementDrawing").innerHTML = settlements.map((parent) => {
      const nodes = [parent.id,...parent.branches].map(point);
      const left = Math.min(...nodes.map((p) => p.x)) - 60, right = Math.max(...nodes.map((p) => p.x)) + 65;
      const top = Math.min(...nodes.map((p) => p.y)) - 48, bottom = Math.max(...nodes.map((p) => p.y)) + 48;
      const patch = `M${left+48},${top} Q${left-7},${top+8} ${left},${top+62} L${left+5},${bottom-37} Q${left+10},${bottom+5} ${left+58},${bottom} L${right-53},${bottom-8} Q${right+7},${bottom-15} ${right},${bottom-64} L${right-4},${top+46} Q${right-13},${top-7} ${right-64},${top-2} Z`;
      const trees = parent.branches.map((id) => {
        const p = point(id);
        return `<g transform="translate(${p.x-43},${p.y-7})"><path d="M0,8 V-13 M12,9 V-6" stroke="#9d9270" stroke-width="2"/><path d="M0,-28 Q-12,-13 0,0 Q11,-12 0,-28 M12,-19 Q3,-7 12,3 Q21,-7 12,-19" fill="#9fa88a" stroke="#f4ecd6" stroke-width="1"/></g>`;
      }).join("");
      return `<g class="settlement"><path class="settlement-edge" d="${patch}" transform="translate(0,5)"/><path class="settlement-paper" d="${patch}"/>${trees}</g>`;
    }).join("");
    $("branchRoutes").innerHTML = places.filter((p) => p.parent).map((p) => {
      const d = segment(point(p.parent),point(p.id));
      return `<path class="branch-under" d="${d}"/><path data-branch="${p.id}" d="${d}"/>`;
    }).join("");
    $("roadLabels").innerHTML = (data.roadLabels || []).map((label) => {
      const a = point(label.fr), b = point(label.to), width = label.text.length * 14 + 24;
      return `<g class="road-label" transform="translate(${(a.x+b.x)/2+(label.offsetX || 0)},${(a.y+b.y)/2+(label.offsetY || 0)})"><rect x="${-width/2}" y="-14" width="${width}" height="28" rx="3"/><text text-anchor="middle" dominant-baseline="central">${escape(label.text)}</text></g>`;
    }).join("");
  };
  drawRoute();

  const majorPlaces = new Set(["chengdu", "helan", "danxia", "dunhuang", "lenghu", "water", "lake", "xining"]);
  $("mapStops").innerHTML = places.map((p, index) => `<button type="button" class="place-pin${p.parent ? " branch-pin" : ""}${majorPlaces.has(p.id) ? " major" : ""}" data-place="${p.id}" style="left:${p.x}px;top:${p.y}px" aria-label="${escape(p.name)}，${escape(p.date)}" aria-pressed="false">${model(p.kind, "pin-model")}<span class="pin-label">${p.locality ? `<small class="pin-locality">${escape(p.locality)} · </small>` : ""}${escape(p.shortName || p.name)}</span><span class="pin-date">${p.parent ? "9.29" : pad(mainPlaces.indexOf(p) + 1) + " · " + escape(p.date)}</span></button>`).join("");
  $("routeList").innerHTML = mainPlaces.map((p, index) => `<li><button type="button" data-place="${p.id}"><span class="list-number">${pad(index + 1)}</span><strong>${escape(p.name)}</strong><small>${escape(p.date)}${p.status ? " · " + escape(p.status) : ""}</small></button>${p.branches?.length ? `<ol class="route-subplaces">${p.branches.map((id) => `<li><button type="button" data-place="${id}"><span class="list-number">↳</span><strong>${escape(byId.get(id).shortName)}</strong><small>${escape(byId.get(id).date)}</small></button></li>`).join("")}</ol>` : ""}</li>`).join("");
  $("dailyList").innerHTML = (plan?.days || []).map((day) => `<section class="daily-card"><h3><time>${escape(day.date)}</time>${escape(day.title)}</h3>${day.drivingReference ? `<p class="daily-driving">驾车参考合计 ${escape(day.drivingReference.duration)} · 停留另计</p>` : ""}${day.steps.map((step) => `<button type="button" data-place="${step.place}" data-show-guide="true"><time>${escape(step.time)}</time><span>${escape(step.text)}</span></button>`).join("")}</section>`).join("");
  $("routeViewTabs").addEventListener("click", (event) => {
    const button = event.target.closest("[data-route-view]");
    if (!button) return;
    const days = button.dataset.routeView === "days";
    $("dailyList").hidden = !days; $("routeList").hidden = days;
    document.querySelectorAll("[data-route-view]").forEach((item) => item.setAttribute("aria-pressed", String(item === button)));
  });

  const transform = () => {
    world.style.transform = `translate(${view.x}px, ${view.y}px) scale(${view.k})`;
    world.style.setProperty("--map-label-size", `${Math.min(28, Math.max(16, 10.5 / view.k))}px`);
    world.style.setProperty("--map-date-size", `${Math.min(22, Math.max(11, 8 / view.k))}px`);
    world.style.setProperty("--cinema-title-size", `${Math.min(50, Math.max(34, 19 / view.k))}px`);
    world.classList.toggle("overview", mobile.matches && view.k < .5);
    if (panel.open) requestAnimationFrame(() => positionPanel(false));
  };
  const dimensions = () => ({ w: viewport.clientWidth, h: viewport.clientHeight });
  const clamp = (value, low, high) => Math.min(high, Math.max(low, value));
  const clampPan = () => {
    const { w, h } = dimensions();
    view.x = clamp(view.x, 80 - stageSize.width * view.k, w - 80);
    view.y = clamp(view.y, 100 - stageSize.height * view.k, h - 100);
  };
  const fit = (list = places) => {
    const { w, h } = dimensions();
    if (!w || !h) return;
    const xs = list.map((p) => point(p.id).x), ys = list.map((p) => point(p.id).y);
    let left = Math.min(...xs) - 92, right = Math.max(...xs) + 92;
    let top = Math.min(...ys) - 100, bottom = Math.max(...ys) + 80;
    if (list !== places) {
      const regions = new Set(list.map((p) => p.region));
      for (const feature of data.landscapes || []) {
        if (!regions.has(feature.region)) continue;
        const [x,y,fw,fh,,lx,ly] = feature.layouts[landscapeLayoutName()];
        left = Math.min(left,x-fw/2-20,lx-65); right = Math.max(right,x+fw/2+20,lx+65);
        top = Math.min(top,y-fh/2-20,ly-25); bottom = Math.max(bottom,y+fh/2+20,ly+15);
      }
    }
    if (list === places) { left = 0; right = stageSize.width; top = 0; bottom = stageSize.height; }
    const landscape = innerWidth > innerHeight && innerHeight < 600;
    const topSpace = landscape ? 52 : (mobile.matches ? 98 : 65), bottomSpace = landscape ? 58 : (mobile.matches ? 112 : 88);
    const availableHeight = Math.max(190, h - topSpace - bottomSpace);
    view.k = clamp(Math.min((w - 28) / Math.max(240, right - left), availableHeight / Math.max(210, bottom - top)), view.min, view.max);
    view.x = w / 2 - (left + right) / 2 * view.k;
    view.y = topSpace + availableHeight / 2 - (top + bottom) / 2 * view.k;
    transform();
  };
  const focusPlace = (p, zoom = false) => {
    p = point(p.id);
    const { w, h } = dimensions();
    if (zoom) view.k = Math.max(view.k, mobile.matches ? .88 : .77);
    view.x = w * .5 - p.x * view.k;
    view.y = h * .45 - p.y * view.k;
    clampPan(); transform();
  };
  const zoomAt = (k, x, y) => {
    const next = clamp(k, view.min, view.max);
    view.x = x - (x - view.x) * next / view.k;
    view.y = y - (y - view.y) * next / view.k;
    view.k = next;
    clampPan(); transform();
  };

  const showList = (open) => {
    $("routeMenu").hidden = !open;
    $("toggleList").setAttribute("aria-expanded", String(open));
  };
  $("toggleList").addEventListener("click", () => showList($("routeMenu").hidden));
  $("closeList").addEventListener("click", () => { showList(false); $("toggleList").focus(); });

  const openPanel = () => {
    resetGesture();
    if (!panel.open) panel.show();
    window.dispatchEvent(new CustomEvent("roadbook:recordopen"));
    positionPanel(true);
  };
  const closePanel = () => {
    resetGesture();
    if (panel.open) panel.close();
    $("placeConnector").setAttribute("hidden", "");
  };
  function positionPanel(allowPan = false) {
    if (!panel.open) return;
    const pin = world.querySelector(`.place-pin[data-place="${selectedId}"] .pin-model`);
    if (!pin) return;
    const margin = 14, gap = 20, pageWidth = innerWidth, pageHeight = innerHeight;
    const topLimit = $("siteHeader").getBoundingClientRect().bottom + 10;
    let anchor = pin.getBoundingClientRect();
    let side = (pageWidth - anchor.right) >= anchor.left ? "right" : "left";
    let room = side === "right" ? pageWidth - margin - anchor.right - gap : anchor.left - gap - margin;
    if (allowPan && (room < 235 || anchor.right < margin || anchor.left > pageWidth - margin || anchor.bottom < topLimit || anchor.top > pageHeight - 50)) {
      const targetX = side === "right" ? 48 : pageWidth - 48;
      view.x += targetX - (anchor.left + anchor.width / 2);
      const targetY = clamp(anchor.top + anchor.height / 2, topLimit + 28, pageHeight - 60);
      view.y += targetY - (anchor.top + anchor.height / 2);
      transform();
      anchor = pin.getBoundingClientRect();
      room = side === "right" ? pageWidth - margin - anchor.right - gap : anchor.left - gap - margin;
    }
    const width = Math.min(420, Math.max(200, room));
    const height = Math.min(650, pageHeight - topLimit - 16);
    const left = clamp(side === "right" ? anchor.right + gap : anchor.left - gap - width, margin, pageWidth - width - margin);
    const anchorY = anchor.top + anchor.height / 2;
    const top = clamp(anchorY - 105, topLimit, Math.max(topLimit, pageHeight - height - margin));
    const pointerY = clamp(anchorY - top, 26, height - 26);
    panel.dataset.side = side;
    Object.assign(panel.style, { left: `${left}px`, top: `${top}px`, width: `${width}px`, height: `${height}px` });
    panel.style.setProperty("--pointer-y", `${pointerY}px`);
    const startX = side === "right" ? anchor.right - 5 : anchor.left + 5;
    const endX = side === "right" ? left - 7 : left + width + 7;
    $("placeConnectorLine").setAttribute("d", `M${startX},${anchorY} C${(startX+endX)/2},${anchorY} ${(startX+endX)/2},${top+pointerY} ${endX},${top+pointerY}`);
    $("placeConnectorDot").setAttribute("cx", startX);
    $("placeConnectorDot").setAttribute("cy", anchorY);
    $("placeConnector").removeAttribute("hidden");
  }
  const setRecordTab = (tab) => {
    recordTab = tab;
    panel.dataset.record = tab;
    document.querySelectorAll("[data-record-tab]").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.recordTab === tab));
    });
    document.querySelectorAll("[data-record-pane]").forEach((pane) => { pane.hidden = pane.dataset.recordPane !== tab; });
    $("placeScroll").scrollTop = 0;
  };
  $("recordTabs").addEventListener("click", (event) => {
    const button = event.target.closest("[data-record-tab]");
    if (button) setRecordTab(button.dataset.recordTab);
  });
  $("closePanel").addEventListener("click", closePanel);
  $("mobilePeek").addEventListener("click", () => {
    lastTrigger = $("mobilePeek"); openPanel();
  });
  [panel].forEach((dialog) => dialog.addEventListener("click", (event) => {
    if (event.target !== dialog) return;
    const rect = dialog.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) closePanel();
  }));
  const restoreStageFocus = () => {
    if (!document.querySelector("dialog[open]")) world.querySelector(`.place-pin[data-place="${selectedId}"]`)?.focus({ preventScroll: true });
  };
  [panel, $("libraryDialog")].forEach((dialog) => dialog.addEventListener("close", () => {
    if (dialog === panel) $("placeConnector").setAttribute("hidden", "");
    resetGesture(); requestAnimationFrame(restoreStageFocus);
  }));
  document.addEventListener("click", (event) => {
    if (panel.open && !panel.contains(event.target) && !event.target.closest("[data-place],#mobilePeek,#libraryPlaces")) closePanel();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && panel.open) { event.preventDefault(); closePanel(); }
  });
  window.addEventListener("resize", () => { if (panel.open) requestAnimationFrame(() => positionPanel(true)); });
  const archiveEntry = (key) => {
    const entry = archive?.entries[key];
    return entry ? `<details class="archive-entry"><summary>${escape(entry.title)}</summary><div class="archive-body">${entry.html}</div></details>` : "";
  };
  const legsFor = (p) => (plan?.legs || []).filter((leg) => leg.fr === p.id || leg.to === p.id);
  const renderLegs = (p, full = true) => {
    const legs = legsFor(p);
    if (!legs.length) return "";
    return `<section class="route-legs"><h3>前后路程</h3>${legs.map((leg) => `<div class="route-leg"><p class="leg-date">${escape(leg.date)}</p><p class="leg-title">${escape(byId.get(leg.fr)?.name)} → ${escape(byId.get(leg.to)?.name)}</p><p class="leg-duration">${escape(leg.duration)}<span class="leg-basis${leg.basis === "实测时间" ? " measured" : ""}">${escape(leg.basis)}</span></p>${leg.amap ? `<span class="leg-distance">${escape(leg.amap.distanceLabel)}</span>` : ""}${!full && leg.routeCaveat ? `<p class="leg-note">${escape(leg.routeCaveat)}</p>` : ""}${full ? `<p class="leg-note">${escape(leg.note)}</p>${leg.reference ? `<p class="leg-reference">${escape(leg.reference)}</p>` : ""}${(leg.amap || leg.amapBaseline)?.url ? `<a class="leg-map" href="${escape((leg.amap || leg.amapBaseline).url)}" target="_blank" rel="noopener">高德路线 ↗</a>` : ""}` : ""}</div>`).join("")}</section>`;
  };
  const renderSchedule = (p) => (plan?.days || []).filter((day) => day.steps.some((step) => step.place === p.id || p.branches?.includes(step.place))).map((day) => `<section class="day-schedule"><h3><span>${escape(day.date)}</span>${escape(day.title)}</h3>${day.drivingReference ? `<div class="day-driving"><strong>${escape(day.drivingReference.duration)}</strong><span>高德驾车参考合计</span><p>${escape(day.drivingReference.note)}</p></div>` : ""}<ol>${day.steps.map((step) => `<li class="${step.place === p.id ? "current-step" : ""}"><time>${escape(step.time)}</time><span>${escape(step.text)}</span></li>`).join("")}</ol>${day.note ? `<p class="day-note">${escape(day.note)}</p>` : ""}</section>`).join("");
  const renderGuide = (p) => {
    const guide = plan?.guides[p.id];
    if (!guide) return "";
    return `${renderSchedule(p)}${renderLegs(p)}<section class="station-guide"><h3>游玩参考</h3><p class="guide-duration">${escape(guide.duration)}</p><ul>${guide.tips.map((tip) => `<li>${escape(tip)}</li>`).join("")}</ul><p class="guide-basis">${escape(guide.basis)}</p>${guide.sources?.length ? `<div class="guide-sources">${guide.sources.filter((source) => /^https?:\/\//.test(source.url)).map((source) => `<a href="${escape(source.url)}" target="_blank" rel="noopener">${escape(source.title)} ↗</a>`).join("")}</div>` : ""}</section>`;
  };
  $("libraryPlaces").innerHTML = places.map((p) => `<button type="button" data-library-place="${p.id}">${model(p.kind)}<span>${escape(p.name)}</span><small>${escape(p.date)}</small></button>`).join("");
  $("libraryShared").innerHTML = (archive?.shared || []).map(archiveEntry).join("");
  $("libraryUnused").innerHTML = (archive?.unused || []).map(archiveEntry).join("");
  $("openLibrary").addEventListener("click", () => { closePanel(); $("libraryDialog").showModal(); });
  $("closeLibrary").addEventListener("click", () => $("libraryDialog").close());
  $("libraryPlaces").addEventListener("click", (event) => {
    const button = event.target.closest("[data-library-place]");
    if (!button) return;
    $("libraryDialog").close();
    selectPlace(button.dataset.libraryPlace, { tab: "book", trigger: $("openLibrary") });
  });

  let mediaPromise;
  const oldMedia = () => {
    if (mediaPromise) return mediaPromise;
    mediaPromise = new Promise((resolve) => {
      if (!("indexedDB" in window)) { resolve([]); return; }
      const request = indexedDB.open("qinggan-roadbook-media", 1);
      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains("media")) {
          const store = db.createObjectStore("media", { keyPath: "id", autoIncrement: true });
          store.createIndex("dayId", "dayId", { unique: false });
        }
      };
      request.onerror = () => resolve([]);
      request.onblocked = () => resolve([]);
      request.onsuccess = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains("media")) { db.close(); resolve([]); return; }
        const tx = db.transaction("media", "readonly"), query = tx.objectStore("media").getAll();
        query.onsuccess = () => resolve(query.result || []);
        tx.oncomplete = () => db.close();
        tx.onerror = () => { db.close(); resolve([]); };
      };
    }).catch(() => []);
    return mediaPromise;
  };
  const dayLabel = (day) => {
    const value = day.slice(1);
    return value.length === 3 ? `${value[0]}.${value.slice(1)}` : `${value.slice(0, 2)}.${value.slice(2)}`;
  };
  const renderLegacy = async (p, token) => {
    const items = await oldMedia();
    if (token !== renderToken) return;
    const root = $("legacyNotes");
    if (!root) return;
    for (const [id, target] of Object.entries(data.placeAliases || {})) {
      const note = readNote(id);
      if (target !== p.id || !note.trim()) continue;
      const detail = document.createElement("details"); detail.className = "place-story";
      const name = ({siju:"敦煌四局",nightmarket:"沙洲夜市",ebol:"俄博梁旧页"})[id] || id;
      detail.innerHTML = `<summary>${name}的补记</summary><div class="story-body"><p class="legacy-text">${escape(note)}</p></div>`;
      root.append(detail);
    }
    for (const day of p.legacyDays || []) {
      const line = read(`roadbook-note:${day}:line`), timing = read(`roadbook-note:${day}:timing`);
      const media = items.filter((item) => item.dayId === day && item.blob instanceof Blob);
      if (!line.trim() && !timing.trim() && !media.length) continue;
      const detail = document.createElement("details");
      detail.className = "place-story";
      detail.innerHTML = `<summary>${escape(dayLabel(day))} 的途中补记</summary><div class="story-body">${line.trim() ? `<p class="legacy-text">${escape(line)}</p>` : ""}${timing.trim() ? `<p class="legacy-text">${escape(timing)}</p>` : ""}</div>`;
      const body = detail.querySelector(".story-body");
      for (const item of media) {
        const isVideo = (item.type || item.blob.type || "").startsWith("video/");
        const element = document.createElement(isVideo ? "video" : "img");
        const url = URL.createObjectURL(item.blob); mediaUrls.push(url);
        element.src = url; element.className = "legacy-media";
        if (isVideo) { element.controls = true; element.playsInline = true; element.preload = "metadata"; }
        else { element.alt = item.name || "当天影像"; element.loading = "lazy"; }
        const caption = document.createElement("p"); caption.className = "legacy-name";
        caption.textContent = item.name || "当天影像";
        body.append(element, caption);
      }
      root.append(detail);
    }
  };

  const renderPlace = (p) => {
    const token = ++renderToken;
    mediaUrls.forEach((url) => URL.revokeObjectURL(url)); mediaUrls = [];
    const index = mainPlaces.findIndex((item) => item.id === (p.parent || p.id));
    const number = `${pad(index + 1)} / ${mainPlaces.length}${p.parent ? " · 支线" : ""}`;
    $("placeRegion").textContent = p.region;
    $("placeNumber").textContent = number;
    $("pagerPosition").textContent = number;
    $("previousPlace").disabled = !p.parent && index === 0;
    $("previousPlace").textContent = p.parent ? `← ${byId.get(p.parent).name}` : "← 上一站";
    $("nextPlace").disabled = false;
    $("nextPlace").textContent = index === mainPlaces.length - 1 ? "回到成都 →" : "下一站 →";
    $("peekDate").textContent = p.date;
    $("peekName").textContent = p.name;
    const facts = p.facts?.length ? `<dl class="place-facts">${p.facts.map(([key, value]) => `<div><dt>${escape(key)}</dt><dd>${escape(value)}</dd></div>`).join("")}</dl>` : "";
    const timeline = p.timeline?.length ? `<ol class="place-timeline">${p.timeline.map(([time, text]) => `<li><time>${escape(time)}</time><span>${escape(text)}</span></li>`).join("")}</ol>` : "";
    const stay = p.stay ? `<section class="place-block"><h3>住宿</h3><p class="stay-name">${escape(p.stay.name)}</p><p>${escape(p.stay.text)}</p></section>` : "";
    const food = p.food?.length ? `<section class="place-block"><h3>吃喝</h3>${paragraphs(p.food)}</section>` : "";
    const sources = (p.sources || []).filter((source) => /^https?:\/\//.test(source.url)).map((source) => `<a href="${escape(source.url)}" target="_blank" rel="noopener">${escape(source.title)} ↗</a>`).join("");
    const book = (archive?.byPlace[p.id] || []).map(archiveEntry).join("");
    document.querySelector('[data-record-tab="story"]').hidden = !p.story?.length;
    if (recordTab === "story" && !p.story?.length) recordTab = "memory";
    const related = p.parent ? byId.get(p.parent) : p;
    const branches = related.branches?.length ? `<nav class="place-branches" aria-label="敦煌市内地点">${p.parent ? `<button type="button" class="branch-back" data-place="${p.parent}">← 敦煌</button>` : ""}${related.branches.map((id) => `<button type="button" class="branch-card${id === p.id ? " active" : ""}" data-place="${id}" aria-pressed="${id === p.id}"><small>9.29</small><span>${escape(byId.get(id).shortName)}</span><b aria-hidden="true">↗</b></button>`).join("")}</nav>` : "";
    const walk = p.stops?.length ? `<ul class="walk-stops">${p.stops.map((stop) => `<li><strong>${escape(stop.name)}</strong><br>${escape(stop.text)}</li>`).join("")}</ul>` : "";
    $("placeContent").innerHTML = `<p class="place-date">${escape(p.date)}${p.status ? " · " + escape(p.status) : ""}</p><h2 id="placeTitle" tabindex="-1">${escape(p.name)}</h2>${branches}${p.road ? `<div class="place-road"><span>${escape(p.road)}</span><p>${escape(p.roadNote)}</p></div>` : ""}<div class="place-vignette">${model(p.kind)}</div><section data-record-pane="memory"><div class="place-memory">${paragraphs(p.memory)}</div>${walk}${facts}${timeline}${renderLegs(p,false)}${stay}${food}<div id="legacyNotes"></div><div class="place-block place-notes"><label for="placeNote">补记</label><textarea id="placeNote" aria-label="${escape(p.name)}的补记" placeholder="写下这一站还记得的事……"></textarea><p class="note-status" id="noteStatus" role="status">保存在当前浏览器</p></div></section><section data-record-pane="guide" hidden>${renderGuide(p)}</section><section data-record-pane="story" hidden>${p.story?.length ? `<div class="story-body">${paragraphs(p.story)}${sources ? `<div class="story-sources">${sources}</div>` : ""}</div>` : '<p class="page-blank">这一页，留待慢慢写。</p>'}</section><section data-record-pane="book" class="archive-pages" hidden><p class="archive-note">出发前留下的计划与资料，保留当时的版本。</p>${book || '<p class="page-blank">这一站的行前存页留白。</p>'}</section>`;
    setRecordTab(recordTab);
    const input = $("placeNote"); input.value = readNote(p.id);
    input.addEventListener("input", () => {
      sessionNotes.set(p.id, input.value);
      try { localStorage.setItem(noteKey(p.id), input.value); $("noteStatus").textContent = "已保存到当前浏览器"; }
      catch (_) { $("noteStatus").textContent = "浏览器暂时无法保存，请用页首“保存文字”备份。"; }
    });
    $("placeScroll").scrollTop = 0;
    renderLegacy(p, token);
  };
  const syncSelection = () => {
    document.querySelectorAll("[data-place]").forEach((el) => {
      const on = el.dataset.place === selectedId;
      el.classList.toggle("selected", on && el.classList.contains("place-pin"));
      el.classList.toggle("active", on && !el.classList.contains("place-pin"));
      el.setAttribute("aria-pressed", String(on));
    });
    const selected = byId.get(selectedId);
    const routeIndex = data.route.indexOf(selectedId);
    const previous = selected.parent ? point(selected.parent) : (routeIndex > 0 ? point(data.route[routeIndex - 1]) : null);
    $("routeActive").setAttribute("d", previous ? segment(previous, point(selectedId)) : "");
    document.querySelectorAll("[data-branch]").forEach((el) => el.classList.toggle("active",el.dataset.branch === selectedId || byId.get(el.dataset.branch).parent === selectedId));
  };
  const selectPlace = (id, options = {}) => {
    const p = byId.get(id);
    if (!p) return;
    const { open = true, focus = true, center = false, push = true, trigger = null, tab = "memory" } = options;
    recordTab = tab;
    selectedId = id;
    if (trigger) lastTrigger = trigger;
    renderPlace(p); syncSelection();
    if (center) focusPlace(p, true);
    if (push && location.hash !== `#place=${id}`) history.pushState({ place: id }, "", `#place=${id}`);
    if (open) openPanel();
    if (focus && open) $("placeTitle").focus({ preventScroll: true });
    document.title = `${p.name} · 青甘银川`;
    window.dispatchEvent(new CustomEvent("roadbook:placechange", { detail: { id, open } }));
  };
  $("mapStops").addEventListener("click", (event) => {
    const button = event.target.closest("[data-place]");
    if (!button || performance.now() < ignoredClickUntil) return;
    showList(false);
    if (button.dataset.place === selectedId) {
      lastTrigger = button; openPanel(); $("placeTitle").focus({preventScroll:true});
    } else {
      closePanel(); selectPlace(button.dataset.place, {open:false,focus:false,trigger:button});
    }
  });
  $("placeContent").addEventListener("click", (event) => {
    const button = event.target.closest("[data-place]");
    if (button) selectPlace(button.dataset.place,{ center: true, tab: recordTab });
  });
  $("routeMenu").addEventListener("click", (event) => {
    const button = event.target.closest("[data-place]");
    if (!button) return;
    showList(false);
    selectPlace(button.dataset.place, { center: true, trigger: $("toggleList"), tab: button.dataset.showGuide ? "guide" : "memory" });
  });
  $("fitMap").addEventListener("click", () => { fit(); showList(false); });
  document.querySelector(".brand").addEventListener("click", (event) => { event.preventDefault(); fit(); showList(false); });
  $("zoomIn").addEventListener("click", () => { const { w, h } = dimensions(); zoomAt(view.k * 1.24, w / 2, h / 2); });
  $("zoomOut").addEventListener("click", () => { const { w, h } = dimensions(); zoomAt(view.k / 1.24, w / 2, h / 2); });
  $("previousPlace").addEventListener("click", () => {
    const p = byId.get(selectedId), index = mainPlaces.findIndex((item) => item.id === selectedId);
    if (p.parent) selectPlace(p.parent, { center: true, tab: recordTab });
    else if (index > 0) selectPlace(mainPlaces[index - 1].id, { center: false, tab: recordTab });
  });
  $("nextPlace").addEventListener("click", () => {
    const p = byId.get(selectedId), index = mainPlaces.findIndex((item) => item.id === (p.parent || selectedId));
    selectPlace(mainPlaces[(index + 1) % mainPlaces.length].id, { center: false, tab: recordTab });
  });

  viewport.addEventListener("wheel", (event) => {
    if (event.target.closest(".paper-cinema")) return;
    event.preventDefault();
    const rect = viewport.getBoundingClientRect();
    zoomAt(view.k * Math.exp(-clamp(event.deltaY, -180, 180) * .002), event.clientX - rect.left, event.clientY - rect.top);
  }, { passive: false });
  viewport.addEventListener("keydown", (event) => {
    if (event.target !== viewport) return;
    const { w, h } = dimensions();
    if (["+", "="].includes(event.key)) zoomAt(view.k * 1.2, w / 2, h / 2);
    else if (event.key === "-") zoomAt(view.k / 1.2, w / 2, h / 2);
    else if (event.key === "ArrowLeft") view.x += 50;
    else if (event.key === "ArrowRight") view.x -= 50;
    else if (event.key === "ArrowUp") view.y += 50;
    else if (event.key === "ArrowDown") view.y -= 50;
    else return;
    event.preventDefault(); clampPan(); transform();
  });
  const pointers = new Map();
  let pan = null, pinch = null, dragging = false;
  const pointerDistance = () => {
    const [a, b] = [...pointers.values()];
    return Math.hypot(a.x - b.x, a.y - b.y);
  };
  const pointerCenter = () => {
    const [a, b] = [...pointers.values()], rect = viewport.getBoundingClientRect();
    return { x: (a.x + b.x) / 2 - rect.left, y: (a.y + b.y) / 2 - rect.top };
  };
  viewport.addEventListener("pointerdown", (event) => {
    if (event.target.closest(".paper-cinema")) return;
    if (event.pointerType === "mouse" && event.button !== 0) return;
    pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (pointers.size === 1) pan = { x: event.clientX, y: event.clientY, vx: view.x, vy: view.y };
    if (pointers.size === 2) {
      const c = pointerCenter();
      pinch = { distance: pointerDistance(), k: view.k, wx: (c.x - view.x) / view.k, wy: (c.y - view.y) / view.k };
      dragging = true;
    }
  });
  window.addEventListener("pointermove", (event) => {
    if (!pointers.has(event.pointerId)) return;
    pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (pointers.size === 2 && pinch) {
      const c = pointerCenter();
      view.k = clamp(pinch.k * pointerDistance() / Math.max(1, pinch.distance), view.min, view.max);
      view.x = c.x - pinch.wx * view.k; view.y = c.y - pinch.wy * view.k;
    } else if (pointers.size === 1 && pan) {
      const dx = event.clientX - pan.x, dy = event.clientY - pan.y;
      if (!dragging && Math.hypot(dx, dy) < 5) return;
      dragging = true; viewport.classList.add("dragging");
      view.x = pan.vx + dx; view.y = pan.vy + dy;
    } else return;
    clampPan(); transform();
  });
  const pointerEnd = (event) => {
    if (!pointers.has(event.pointerId)) return;
    pointers.delete(event.pointerId);
    if (dragging) ignoredClickUntil = performance.now() + 250;
    if (pointers.size === 1) {
      const a = [...pointers.values()][0]; pan = { x: a.x, y: a.y, vx: view.x, vy: view.y }; pinch = null;
    } else { pan = null; pinch = null; dragging = false; viewport.classList.remove("dragging"); }
  };
  window.addEventListener("pointerup", pointerEnd);
  window.addEventListener("pointercancel", pointerEnd);
  function resetGesture() {
    pointers.clear(); pan = null; pinch = null; dragging = false; ignoredClickUntil = 0;
    viewport.classList.remove("dragging");
  }
  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !$("routeMenu").hidden) { showList(false); $("toggleList").focus(); }
  });
  viewport.addEventListener("pointerdown", () => showList(false));

  const fromHash = () => {
    let hash;
    try { hash = decodeURIComponent(location.hash.slice(1)); } catch (_) { return null; }
    const candidate = hash.startsWith("place=") ? hash.slice(6) : data.legacyAliases[hash];
    const value = data.placeAliases?.[candidate] || candidate;
    return byId.has(value) ? value : null;
  };
  window.addEventListener("hashchange", () => {
    const id = fromHash();
    if (id) selectPlace(id, { push: false, center: true });
    else if (!location.hash) {
      selectPlace(data.defaultPlace, { open: false, focus: false, push: false });
      closePanel(); fit();
    }
  });
  const resize = () => {
    const { w, h } = dimensions();
    view.min = Math.min(.25, Math.max(.12, Math.min(w / stageSize.width, h / stageSize.height) * .7));
    if (!initialized) {
      initialized = true; fit();
      if (mobile.matches) focusPlace(point(selectedId), true);
    } else { clampPan(); transform(); }
  };
  new ResizeObserver(resize).observe(viewport);
  mobile.addEventListener("change", () => fit());
  const initial = fromHash();
  selectPlace(initial || data.defaultPlace, { open: false, focus: false, push: false });
  resize();

  window.roadbookAtlas = {
    selectPlace,
    getSelectedId: () => selectedId,
    closePanel,
    restoreFocus: restoreStageFocus,
    openRecord: () => { openPanel(); $("placeTitle").focus({ preventScroll: true }); },
    fit: () => { fit(); },
    setLayout: (layout, terrain, size = { width: data.width, height: data.height }) => {
      stageLayout = layout;
      stageSize = size;
      world.style.width = `${size.width}px`; world.style.height = `${size.height}px`;
      document.querySelector(".terrain").style.width = `${size.width}px`;
      document.querySelector(".terrain").style.height = `${size.height}px`;
      $("routeDrawing").setAttribute("viewBox", `0 0 ${size.width} ${size.height}`);
      $("routeDrawing").style.width = `${size.width}px`; $("routeDrawing").style.height = `${size.height}px`;
      $("settlementDrawing").setAttribute("viewBox", `0 0 ${size.width} ${size.height}`);
      $("settlementDrawing").style.width = `${size.width}px`; $("settlementDrawing").style.height = `${size.height}px`;
      $("landscapeDrawing").setAttribute("viewBox", `0 0 ${size.width} ${size.height}`);
      $("landscapeDrawing").style.width = `${size.width}px`; $("landscapeDrawing").style.height = `${size.height}px`;
      $("mapStage").classList.toggle("theater-mode", Boolean(layout));
      $("mapWorld").classList.toggle("paper-world", Boolean(layout));
      document.querySelector(".terrain").src = terrain;
      document.querySelectorAll(".place-pin").forEach((pin) => {
        const p = point(pin.dataset.place);
        pin.style.left = `${p.x}px`; pin.style.top = `${p.y}px`;
      });
      drawRoute(); syncSelection(); fit();
    }
  };

  $("exportTrip").addEventListener("click", () => {
    const lines = ["青甘银川 · 2026", "9.24—10.5", ""], seenDays = new Set();
    for (const p of places) {
      lines.push(`${p.date} · ${p.name}`, ...p.memory);
      if (p.stay) lines.push(`住宿：${p.stay.name}。${p.stay.text}`);
      if (p.timeline) lines.push(...p.timeline.map(([time, text]) => `${time} · ${text}`));
      if (p.story?.length) lines.push(`原路书 · ${p.storyTitle}`, ...p.story);
      for (const leg of legsFor(p)) lines.push(`${leg.date} ${byId.get(leg.fr)?.name} → ${byId.get(leg.to)?.name}：${leg.duration}（${leg.basis}）。${leg.note}${leg.reference || ""}`);
      const guide = plan?.guides[p.id];
      if (guide) lines.push("游玩参考",guide.duration,...guide.tips);
      for (const [id,target] of Object.entries(data.placeAliases || {})) {
        const mergedNote = readNote(id);
        if (target === p.id && mergedNote.trim()) lines.push(`原地点补记（${id}）：${mergedNote}`);
      }
      const note = readNote(p.id);
      if (note.trim()) lines.push(`补记：${note}`);
      for (const day of p.legacyDays || []) {
        if (seenDays.has(day)) continue;
        seenDays.add(day);
        for (const field of ["line", "timing"]) {
          const value = read(`roadbook-note:${day}:${field}`);
          if (value.trim()) lines.push(`${dayLabel(day)} 途中补记：${value}`);
        }
      }
      lines.push("");
    }
    if (archive?.entries) {
      lines.push("行前存页 · 保留出发前的版本", "");
      for (const entry of Object.values(archive.entries)) {
        const page = document.createElement("div"); page.innerHTML = entry.html;
        page.querySelectorAll("p,li,h3,h4,summary,dt,dd,tr").forEach((block) => block.append(document.createTextNode("\n")));
        lines.push(entry.title, page.textContent.trim(), "");
      }
    }
    const url = URL.createObjectURL(new Blob([lines.join("\n\n")], { type: "text/plain;charset=utf-8" }));
    const link = document.createElement("a"); link.href = url; link.download = "2026青甘银川-沿途记录.txt";
    document.body.append(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 30000);
    say("已生成全程文字，包含地点记录和本机补记。");
  });
  window.addEventListener("pagehide", (event) => {
    if (!event.persisted) mediaUrls.forEach((url) => URL.revokeObjectURL(url));
  });
  if ("serviceWorker" in navigator && (location.protocol === "https:" || ["localhost", "127.0.0.1"].includes(location.hostname))) {
    window.addEventListener("load", async () => {
      try {
        const registration = await navigator.serviceWorker.register("./service-worker.js", { scope: "./", updateViaCache: "none" });
        registration.update().catch(() => {});
      } catch (_) { say("离线副本暂未保存，仍可阅读和导出文字。"); }
    });
  }
})();
