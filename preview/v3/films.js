(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const grid = $("filmGrid");
  const status = $("pageStatus");
  const dialog = $("filmDialog");
  const video = $("filmVideo");
  const stage = $("videoStage");
  const musicButton = $("musicButton");
  const placeLink = $("placeLink");
  const portraitQuery = window.matchMedia("(orientation: portrait)");
  const soundPreferenceKey = "roadbook-film-sound";
  let films = [];
  let currentIndex = -1;
  let soundEnabled = true;
  try { soundEnabled = localStorage.getItem(soundPreferenceKey) !== "off"; } catch { /* Playback also works without storage. */ }
  let observedMuted = video.muted;
  let sourceToken = 0;
  let pendingMetadata = null;
  let pendingRestore = null;
  let lastTrigger = null;

  function mediaUrl(value) {
    if (typeof value !== "string" || !value.trim()) return "";
    try {
      const parsed = new URL(value, document.baseURI);
      return ["http:", "https:"].includes(parsed.protocol) && parsed.origin === location.origin ? parsed.href : "";
    } catch { return ""; }
  }

  function durationText(value) {
    const seconds = Math.max(0, Math.round(Number(value) || 0));
    return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
  }

  function element(tag, className, value) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (value !== undefined) node.textContent = String(value);
    return node;
  }

  function renderCards() {
    const fragment = document.createDocumentFragment();
    films.forEach((film, index) => {
      const button = element("button", "film-card");
      button.type = "button";
      button.setAttribute("aria-label", `播放：${film.title || film.label || "沿途影像"}`);
      const paper = element("span", "card-paper");
      const frame = element("span", "card-frame");
      const picture = document.createElement("picture");
      const poster = mediaUrl(film.wide?.poster || film.portrait?.poster);
      const image = document.createElement("img");
      image.alt = "";
      image.loading = "lazy";
      image.decoding = "async";
      image.width = 800;
      image.height = 500;
      if (poster) image.src = poster;
      picture.append(image);
      frame.append(picture, element("span", "play-mark", "▶"), element("span", "card-duration", durationText(film.duration)));
      const caption = element("span", "card-caption");
      caption.append(element("span", "card-date", film.date || ""), element("span", "card-title", film.title || film.label || "沿途影像"));
      const photos = Math.max(0, Number(film.stats?.photos) || 0);
      const live = Math.max(0, Number(film.stats?.live) || 0);
      const meta = [];
      if (photos) meta.push(`${photos} 张照片`);
      if (live) meta.push(`${live} 段 Live`);
      if (meta.length) caption.append(element("span", "card-meta", meta.join(" · ")));
      paper.append(frame, caption);
      button.append(paper);
      button.addEventListener("click", () => openFilm(index, button));
      fragment.append(button);
    });
    grid.replaceChildren(fragment);
    status.textContent = films.length ? `${films.length} 段沿途记录` : "还没有影片。";
  }

  function syncMusicButton() {
    const audible = !video.muted;
    musicButton.setAttribute("aria-pressed", String(audible));
    musicButton.textContent = audible ? "♫ 配乐已开启" : "♫ 开启配乐";
    musicButton.setAttribute("aria-label", audible ? "关闭配乐" : "开启配乐");
  }

  function setMuted(muted) {
    // Record changes made by this page before asynchronous volumechange events arrive.
    observedMuted = Boolean(muted);
    video.muted = observedMuted;
    syncMusicButton();
  }

  function saveSoundPreference() {
    try { localStorage.setItem(soundPreferenceKey, soundEnabled ? "on" : "off"); } catch { /* Optional preference. */ }
  }

  function cancelPendingSource() {
    sourceToken += 1;
    if (pendingMetadata) video.removeEventListener("loadedmetadata", pendingMetadata);
    pendingMetadata = null;
    pendingRestore = null;
  }

  function playSource(token) {
    if (token !== sourceToken || currentIndex < 0 || !dialog.open) return;
    const playing = video.play();
    if (!playing || typeof playing.catch !== "function") return;
    playing.catch((error) => {
      if (token !== sourceToken || currentIndex < 0 || !dialog.open || video.muted) return;
      if (error?.name !== "NotAllowedError") return;
      // A browser policy fallback is not a user choice to turn music off.
      setMuted(true);
      const fallback = video.play();
      if (fallback && typeof fallback.catch === "function") fallback.catch(() => {});
    });
  }

  function variantFor(film) {
    const usePortrait = Boolean(film.portrait?.src && (portraitQuery.matches || !film.wide?.src));
    return { usePortrait, variant: usePortrait ? film.portrait : film.wide };
  }

  function loadSource(film, snapshot = null) {
    cancelPendingSource();
    const token = sourceToken;
    video.pause();
    const { usePortrait, variant } = variantFor(film);
    stage.classList.toggle("is-portrait", usePortrait);
    $("videoError").hidden = true;
    const poster = mediaUrl(variant?.poster);
    if (poster) video.poster = poster;
    else video.removeAttribute("poster");
    setMuted(snapshot ? snapshot.muted : !soundEnabled);
    const src = mediaUrl(variant?.src);
    if (!src) {
      video.removeAttribute("src");
      video.load();
      $("videoError").hidden = false;
      return;
    }
    if (snapshot) {
      pendingRestore = snapshot;
      pendingMetadata = () => {
        if (token !== sourceToken || currentIndex < 0 || !dialog.open) return;
        if (video.readyState < 1 || (video.currentSrc && video.currentSrc !== src)) return;
        video.removeEventListener("loadedmetadata", pendingMetadata);
        pendingMetadata = null;
        const maximum = Number.isFinite(video.duration) ? Math.max(0, video.duration) : snapshot.time;
        try { video.currentTime = Math.min(snapshot.time, maximum); } catch { /* A nonseekable source keeps its native position. */ }
        video.volume = snapshot.volume;
        video.playbackRate = snapshot.playbackRate;
        pendingRestore = null;
        if (snapshot.shouldPlay) playSource(token);
      };
      video.addEventListener("loadedmetadata", pendingMetadata);
    }
    video.src = src;
    video.preload = "metadata";
    video.load();
    // Keep the first play attempt in the card's click gesture on mobile browsers.
    if (!snapshot) playSource(token);
  }

  function loadFilm(index) {
    const film = films[index];
    if (!film) return;
    currentIndex = index;
    $("viewerTitle").textContent = film.title || film.label || "沿途影像";
    $("viewerDate").textContent = film.date || "";
    $("filmPosition").textContent = `${index + 1} / ${films.length}`;
    $("previousFilm").disabled = index === 0;
    $("nextFilm").disabled = index === films.length - 1;
    placeLink.hidden = !film.placeId;
    placeLink.href = film.placeId ? `./#place=${encodeURIComponent(film.placeId)}` : "./";
    loadSource(film);
  }

  function switchOrientation() {
    if (!dialog.open || currentIndex < 0) return;
    const film = films[currentIndex];
    const nextSource = mediaUrl(variantFor(film).variant?.src);
    if (!nextSource || nextSource === video.getAttribute("src")) return;
    const snapshot = pendingRestore ? { ...pendingRestore } : {
      time: Math.max(0, Number(video.currentTime) || 0),
      shouldPlay: !video.paused && !video.ended,
      muted: video.muted,
      volume: video.volume,
      playbackRate: video.playbackRate
    };
    snapshot.muted = video.muted;
    snapshot.volume = video.volume;
    snapshot.playbackRate = video.playbackRate;
    loadSource(film, snapshot);
  }

  if (portraitQuery.addEventListener) portraitQuery.addEventListener("change", switchOrientation);
  else if (portraitQuery.addListener) portraitQuery.addListener(switchOrientation);

  function openFilm(index, trigger) {
    lastTrigger = trigger || lastTrigger;
    if (!dialog.open) dialog.showModal();
    document.body.classList.add("viewer-open");
    loadFilm(index);
    $("closeViewer").focus({ preventScroll: true });
  }

  function closeFilm() {
    video.pause();
    if (dialog.open) dialog.close();
  }

  $("closeViewer").addEventListener("click", closeFilm);
  dialog.addEventListener("click", (event) => {
    if (event.target !== dialog) return;
    const rect = dialog.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) closeFilm();
  });
  dialog.addEventListener("close", () => {
    document.body.classList.remove("viewer-open");
    cancelPendingSource();
    video.pause();
    video.removeAttribute("src");
    video.preload = "none";
    video.load();
    currentIndex = -1;
    if (lastTrigger?.isConnected) lastTrigger.focus({ preventScroll: true });
  });
  musicButton.addEventListener("click", () => {
    soundEnabled = video.muted;
    saveSoundPreference();
    setMuted(!soundEnabled);
    if (soundEnabled && video.paused && currentIndex >= 0) {
      if (pendingRestore) pendingRestore.shouldPlay = true;
      playSource(sourceToken);
    }
  });
  video.addEventListener("volumechange", () => {
    if (currentIndex >= 0 && video.muted !== observedMuted) {
      // Native controls may change mute without using the paper music button.
      observedMuted = video.muted;
      soundEnabled = !video.muted;
      saveSoundPreference();
    }
    syncMusicButton();
  });
  video.addEventListener("error", () => {
    if (currentIndex >= 0 && video.getAttribute("src")) $("videoError").hidden = false;
  });
  $("previousFilm").addEventListener("click", () => {
    if (currentIndex > 0) loadFilm(currentIndex - 1);
  });
  $("nextFilm").addEventListener("click", () => {
    if (currentIndex >= 0 && currentIndex + 1 < films.length) loadFilm(currentIndex + 1);
  });
  $("fullscreenButton").addEventListener("click", async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else if (stage.requestFullscreen) await stage.requestFullscreen();
      else if (video.webkitEnterFullscreen) video.webkitEnterFullscreen();
    } catch { /* Native video controls still provide playback and fullscreen where supported. */ }
  });

  fetch("films.json", { cache: "no-store" })
    .then((response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    })
    .then((data) => {
      films = Array.isArray(data.films) ? data.films.filter((film) => film && typeof film === "object" && (mediaUrl(film.wide?.src) || mediaUrl(film.portrait?.src))) : [];
      if (data.title) {
        $("pageTitle").textContent = data.title;
        document.title = `${data.title} · V3 预览`;
      }
      renderCards();
    })
    .catch(() => {
      status.textContent = "影片清单暂时未能载入，请刷新后再试。";
      grid.replaceChildren();
    });
})();
