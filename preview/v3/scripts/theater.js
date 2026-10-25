(() => {
  "use strict";
  const safeSource = (value) => {
    if (typeof value !== "string") return "";
    const src = value.trim();
    if (!src || /[\u0000-\u001f]/.test(src) || src.startsWith("#") || src.startsWith("//")) return "";
    if (/^(https?:\/\/|blob:)/i.test(src)) return src;
    return /^[a-z][a-z0-9+.-]*:/i.test(src) ? "" : src;
  };
  const finite = (value) => value !== null && value !== "" && Number.isFinite(Number(value));
  const normalizeClips = (items) => (Array.isArray(items) ? items : []).flatMap((item) => {
    if (!item || !["video", "photo"].includes(item.type)) return [];
    const src = safeSource(item.src);
    if (!src) return [];
    const start = finite(item.start) ? Math.max(0, Number(item.start)) : 0;
    const duration = finite(item.duration) && Number(item.duration) > 0 ? Number(item.duration) : null;
    const end = finite(item.end) && Number(item.end) > start ? Number(item.end) : (item.type === "video" && duration ? start + duration : null);
    return [{ type: item.type, src, poster: safeSource(item.poster), start, end,
      duration: item.type === "photo" ? Math.min(60, Math.max(1, duration || 4)) : duration,
      caption: typeof item.caption === "string" ? item.caption : "",
      id: typeof item.id === "string" ? item.id : "",
      date: typeof item.date === "string" ? item.date : "",
      title: typeof item.title === "string" ? item.title : "",
      label: typeof item.label === "string" ? item.label : "",
      fit: item.fit === "cover" ? "cover" : "contain" }];
  });
  const resolveFilms = (config, placeId, fallbackMedia = []) => {
    const byPlace = config?.placeFilms;
    // Presence of a place map is an explicit boundary, including empty entries.
    // A missing place must never borrow another stop's daily film or act media.
    if (byPlace && typeof byPlace === "object" && !Array.isArray(byPlace)) {
      const films = Object.prototype.hasOwnProperty.call(byPlace, placeId) ? byPlace[placeId] : null;
      return Array.isArray(films) ? films.filter((film) => film && Array.isArray(film.media)) : [];
    }
    const daily = (Array.isArray(config?.dailyFilms) ? config.dailyFilms : [])
      .filter((film) => Array.isArray(film?.places) && film.places.includes(placeId));
    return daily.length ? daily : [{ media: fallbackMedia }];
  };
  const prepareFilmClips = (films, isPortrait = false) => normalizeClips(films.flatMap((film) =>
    (Array.isArray(film.media) ? film.media : []).map((clip) => ({ ...clip,
      src: isPortrait ? (clip?.portraitSrc || clip?.src) : clip?.src,
      poster: isPortrait ? (clip?.portraitPoster || clip?.poster) : clip?.poster,
      id: film.id ?? clip?.id, date: film.date ?? clip?.date,
      title: film.title ?? clip?.title, label: film.label ?? clip?.label
    }))));
  const findFilmIndex = (items, previous) => {
    const byId = previous?.id ? items.findIndex((clip) => clip.id === previous.id) : -1;
    if (byId >= 0) return byId;
    const byDate = previous?.date ? items.findIndex((clip) => clip.date === previous.date) : -1;
    return Math.max(0, byDate);
  };
  window.RoadbookFilm = Object.freeze({ safeSource, normalizeClips, resolveFilms, prepareFilmClips, findFilmIndex });

  const config = window.ROADBOOK_THEATER, atlas = window.roadbookAtlas, data = window.ROADBOOK;
  if (!config?.acts?.length || !atlas || !data) return;
  const $ = (id) => document.getElementById(id);
  const stage = $("paperCinema"), screen = $("journeyScreen"), mediaRoot = $("journeyMedia");
  const portrait = matchMedia("(max-width:600px) and (orientation:portrait)");
  const landscape = matchMedia("(orientation:landscape) and (max-height:600px)");
  const reducedMotion = matchMedia("(prefers-reduced-motion:reduce)");
  let active = config.acts.find((entry) => entry.places.includes(atlas.getSelectedId())) || config.acts[0];
  let theaterView = false, clips = [], clipIndex = 0, clipTimer = null, video = null, mediaToken = 0;
  let soundEnabled = true;
  try { soundEnabled = localStorage.getItem("roadbook-film-sound") !== "off"; } catch (_) {}
  const syncSound = () => {
    const button = $("toggleMusic"), on = video ? !video.muted : soundEnabled;
    button.hidden = !video;
    button.setAttribute("aria-pressed",String(on));
    button.setAttribute("aria-label",on ? "关闭配乐" : "开启配乐");
    button.textContent = on ? "♫ 配乐" : "♫ 开启配乐";
  };
  const blocked = () => document.hidden || Boolean(document.querySelector("dialog[open]")) || !theaterView;
  const clearMedia = () => {
    ++mediaToken; clearTimeout(clipTimer);
    if (video) { video.pause(); video.removeAttribute("src"); video.load(); video = null; }
    mediaRoot.replaceChildren();
  };
  const schedulePhoto = () => {
    clearTimeout(clipTimer);
    if (clips.length > 1 && !blocked() && !reducedMotion.matches) clipTimer = setTimeout(nextClip, clips[clipIndex].duration * 1000);
  };
  const resume = () => {
    if (blocked()) return;
    const currentVideo = video;
    if (currentVideo && !reducedMotion.matches) currentVideo.play().catch(() => {
      // Initial navigation may disallow audible autoplay. Keep a visible music control.
      if (video === currentVideo && !video.muted) {
        video.dataset.autoplayMuted = "true"; video.muted = true;
        syncSound(); video.play().catch(() => {});
      }
    });
    else if (clips[clipIndex]?.type === "photo") schedulePhoto();
  };
  const pause = () => { clearTimeout(clipTimer); video?.pause(); };
  const nextClip = () => renderClip((clipIndex + 1) % clips.length);
  const showPaper = () => { clearMedia(); mediaRoot.hidden = true; screen.classList.remove("has-media"); syncSound(); };
  function renderClip(index, attempts = 0) {
    clearMedia();
    const clip = clips[index];
    if (!clip) { showPaper(); return; }
    clipIndex = index;
    document.querySelectorAll("[data-film-index]").forEach((button) => button.setAttribute("aria-pressed",String(Number(button.dataset.filmIndex) === index)));
    screen.setAttribute("aria-label",clip.date ? `${clip.date} · ${clip.title}` : active.title);
    const token = mediaToken;
    const onError = () => {
      if (token !== mediaToken) return;
      if (attempts < clips.length - 1) renderClip((index + 1) % clips.length, attempts + 1);
      else showPaper();
    };
    const element = document.createElement(clip.type === "photo" ? "img" : "video");
    element.style.objectFit = clip.fit;
    element.addEventListener("error", onError);
    if (clip.type === "photo") {
      element.alt = clip.caption || active.title;
      element.addEventListener("load", () => { if (token === mediaToken) schedulePhoto(); }, { once: true });
    } else {
      video = element;
      element.controls = true; element.playsInline = true; element.muted = !soundEnabled; element.preload = "metadata";
      element.addEventListener("volumechange",() => {
        if (video !== element) return;
        syncSound();
        if (element.dataset.autoplayMuted === "true" && element.muted) return;
        delete element.dataset.autoplayMuted;
        soundEnabled = !element.muted;
        try { localStorage.setItem("roadbook-film-sound",soundEnabled ? "on" : "off"); } catch (_) {}
      });
      element.setAttribute("aria-label",`${clip.date} · ${clip.title}，双击全屏观看`);
      element.addEventListener("dblclick", () => {
        if (element.requestFullscreen) element.requestFullscreen().catch(() => {});
        else if (element.webkitEnterFullscreen) element.webkitEnterFullscreen();
      });
      if (clip.poster) element.poster = clip.poster;
      element.addEventListener("loadedmetadata", () => {
        if (token !== mediaToken) return;
        if (Number.isFinite(element.duration) && clip.start >= element.duration) { onError(); return; }
        element.currentTime = clip.start;
        resume();
      }, { once: true });
      element.addEventListener("play", () => {
        if (element.currentTime < clip.start || (clip.end !== null && element.currentTime >= clip.end)) element.currentTime = clip.start;
      });
      let advancing = false;
      const advance = () => { if (!advancing && token === mediaToken) { advancing = true; nextClip(); } };
      element.addEventListener("ended", advance);
      element.addEventListener("timeupdate", () => { if (clip.end !== null && element.currentTime >= clip.end) advance(); });
    }
    mediaRoot.hidden = false; screen.classList.add("has-media");
    mediaRoot.append(element);
    if (clip.caption) {
      const caption = document.createElement("span"); caption.className = `inline-caption ${clip.type}`;
      caption.textContent = clip.caption; mediaRoot.append(caption);
    }
    element.src = clip.src;
    syncSound();
  }
  $("toggleMusic").addEventListener("click",() => {
    if (!video) return;
    soundEnabled = video.muted;
    delete video.dataset.autoplayMuted;
    video.muted = !soundEnabled;
    try { localStorage.setItem("roadbook-film-sound",soundEnabled ? "on" : "off"); } catch (_) {}
    syncSound();
    if (soundEnabled) video.play().catch(() => {});
  });
  const updateDisplay = () => {
    stage.dataset.tone = active.tone;
    $("stageActDate").textContent = active.date;
    $("stageActTitle").textContent = active.title;
    screen.setAttribute("aria-label", active.title);
    const actor = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    actor.setAttribute("viewBox", "0 0 90 82");
    const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
    use.setAttribute("href", `#model-${active.kind}`); actor.append(use);
    $("stageActor").replaceChildren(actor);
    const priorClip = clips[clipIndex];
    const films = resolveFilms(config, atlas.getSelectedId(), active.media);
    clips = prepareFilmClips(films, portrait.matches);
    $("filmDays").hidden = clips.length < 2;
    $("filmDays").replaceChildren(...clips.map((clip,index) => {
      const button = document.createElement("button"); button.type = "button";
      button.dataset.filmIndex = index; button.textContent = clip.label || clip.date || String(index+1);
      button.setAttribute("aria-label",`${clip.date} · ${clip.title}`);
      button.addEventListener("click",() => renderClip(index)); return button;
    }));
    if (clips.length) renderClip(findFilmIndex(clips, priorClip)); else showPaper();
  };
  const setView = (theater) => {
    theaterView = theater; stage.hidden = !theater;
    $("toggleTheater").textContent = theater ? "全程地图" : "旅程总览";
    $("toggleTheater").setAttribute("aria-label", theater ? "切换到全程地图" : "回到旅程总览");
    const tall = theater && portrait.matches, wide = theater && landscape.matches;
    stage.classList.toggle("portrait-stage", tall); stage.classList.toggle("landscape-stage", wide);
    const frame = tall ? config.portrait.screen : (wide ? config.landscape.screen : config.screen);
    stage.style.left = `${frame.x}px`; stage.style.top = `${frame.y}px`; stage.style.width = `${frame.width}px`;
    atlas.setLayout(theater ? (tall ? config.portrait.layout : (wide ? config.landscape.layout : config.layout)) : null,
      theater ? (tall ? "assets/paper-portrait.svg" : "assets/paper-theater.svg") : "assets/sandtable.svg",
      tall ? config.portrait.size : (wide ? config.landscape.size : { width: data.width, height: data.height }));
    $("mapHint").textContent = "点击地点切换，再点查看记录";
    if (theater) resume(); else pause();
  };
  $("toggleTheater").addEventListener("click", () => {
    setView(!theaterView);
    try { localStorage.setItem("roadbook-stage-view", theaterView ? "theater" : "map"); } catch (_) {}
  });
  window.addEventListener("roadbook:placechange", (event) => {
    const next = active.places.includes(event.detail.id) ? active : config.acts.find((entry) => entry.places.includes(event.detail.id)) || config.acts[0];
    active = next; updateDisplay();
    if (event.detail.open) pause();
  });
  window.addEventListener("roadbook:recordopen",pause);
  document.querySelectorAll("dialog").forEach((dialog) => dialog.addEventListener("close", () => {
    if (portrait.matches && theaterView && video && !document.querySelector("dialog[open]")) atlas.fit();
    resume();
  }));
  $("openLibrary").addEventListener("click", pause);
  document.addEventListener("visibilitychange", () => document.hidden ? pause() : resume());
  document.addEventListener("click", (event) => {
    const menu = $("headerMenu");
    if (menu.open && (!menu.contains(event.target) || event.target.closest("a,button"))) menu.open = false;
  });
  portrait.addEventListener("change", () => { setView(theaterView); updateDisplay(); });
  landscape.addEventListener("change", () => { setView(theaterView); updateDisplay(); });
  let savedView;
  try { savedView = localStorage.getItem("roadbook-stage-view"); } catch (_) {}
  setView(savedView ? savedView !== "map" : config.defaultView !== "map"); updateDisplay();
})();
