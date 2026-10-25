"""Package the place-specific V3 preview without changing the published roadbook.

Input: preview/v3/films.json, either a list of films or {"films": [...]}.
Each film supplies placeIds (or placeId), id/date/title/label, and media or
wide/portrait objects. An explicit empty placeIds list is gallery-only.
Video and poster URLs stay relative to preview/v3; media files are not copied.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "preview/v3"
INPUT = OUTPUT / "films.json"
ASSIGNMENT = re.compile(r"\s*window\.ROADBOOK_THEATER\s*=\s*(\{.*\})\s*;?\s*", re.S)
LOCAL_ABSOLUTE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]|file:/{2}", re.I)
CLIP_KEYS = {"type", "src", "portraitSrc", "poster", "portraitPoster", "start", "end",
             "duration", "caption", "fit", "hasMusic"}


def public_strings(value, location="films"):
    """Reject private PC paths even in extra input metadata published alongside the page."""
    if isinstance(value, str) and LOCAL_ABSOLUTE.search(value):
        raise ValueError(f"PC absolute path found in {location}; remove private metadata before packaging")
    if isinstance(value, dict):
        for key, item in value.items():
            public_strings(item, f"{location}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            public_strings(item, f"{location}[{index}]")


def validate_media_url(value, field, check_file=True):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing {field}")
    parsed = urlsplit(value)
    if parsed.scheme in {"http", "https"}:
        return
    if parsed.scheme or parsed.netloc or value.startswith(("/", "\\")):
        raise ValueError(f"{field} must be a relative media URL or HTTPS/HTTP URL")
    target = (OUTPUT / unquote(parsed.path)).resolve()
    if not target.is_relative_to(ROOT):
        raise ValueError(f"{field} resolves outside this project")
    if check_file and not target.is_file():
        raise ValueError(f"Missing relative media file for {field}: {parsed.path}")


def read_films(check_files=True):
    if not INPUT.is_file():
        raise ValueError("Missing input: preview/v3/films.json; no preview files were written")
    raw = INPUT.read_text(encoding="utf-8-sig")
    document = json.loads(raw)
    public_strings(document)
    entries = document.get("films") if isinstance(document, dict) else document
    if not isinstance(entries, list) or not entries:
        raise ValueError("films.json must contain a nonempty film list")
    films, place_films, seen = [], {}, set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"Film {index + 1} must be an object")
        film_id = entry.get("id") or f"v3-{index + 1:03d}"
        if not isinstance(film_id, str) or film_id in seen:
            raise ValueError(f"Film {index + 1} needs a unique string id")
        seen.add(film_id)
        # An explicit [] intentionally keeps a film in the gallery only, even
        # when an old singular placeId also happens to be present.
        places = entry.get("placeIds") if "placeIds" in entry else entry.get("placeId")
        if places is None:
            places = []
        if isinstance(places, str):
            places = [places]
        if not isinstance(places, list) or any(not isinstance(p, str) or not p for p in places):
            raise ValueError(f"Film {film_id} placeIds must be a list of strings")
        media = entry.get("media")
        if media is None and isinstance(entry.get("wide"), dict):
            wide, portrait = entry["wide"], entry.get("portrait") or {}
            if not isinstance(portrait, dict):
                raise ValueError(f"Film {film_id} portrait must be an object")
            media = [{"type": "video", "src": wide.get("src"), "poster": wide.get("poster"),
                      "portraitSrc": portrait.get("src"), "portraitPoster": portrait.get("poster"),
                      "hasMusic": True}]
        if media is None and entry.get("src"):
            media = [{key: value for key, value in entry.items() if key in CLIP_KEYS}]
            media[0].setdefault("type", "video")
        if not isinstance(media, list) or not media:
            raise ValueError(f"Film {film_id} needs nonempty media")
        clean_media = []
        for clip_index, clip in enumerate(media):
            if not isinstance(clip, dict) or clip.get("type") not in {"video", "photo"}:
                raise ValueError(f"Invalid media in film {film_id}")
            clean = {key: value for key, value in clip.items() if key in CLIP_KEYS}
            for key in ["src", "portraitSrc", "poster", "portraitPoster"]:
                if key == "src" or clean.get(key):
                    validate_media_url(clean.get(key), f"{film_id}.media[{clip_index}].{key}", check_files)
            clean_media.append(clean)
        film = {key: entry.get(key, "") for key in ["date", "title", "label"]}
        if any(not isinstance(value, str) for value in film.values()):
            raise ValueError(f"Film {film_id} date/title/label must be strings")
        film.update(id=film_id, media=clean_media)
        films.append(film)
        for place in dict.fromkeys(places):
            place_films.setdefault(place, []).append(film)
    return raw, films, place_films


def read_root_config():
    match = ASSIGNMENT.fullmatch((ROOT / "scripts/theater-data.js").read_text(encoding="utf-8"))
    if not match:
        raise ValueError("Root theater-data.js is not the expected JSON assignment")
    return json.loads(match.group(1))


def disable_preview_worker(source):
    pattern = re.compile(r'\n  if \("serviceWorker" in navigator[^\n]*\) \{.*?\n  \}\n(?=\}\)\(\);\s*$)', re.S)
    result, count = pattern.subn("\n  // V3 preview intentionally uses the network without registering a worker.\n", source)
    if count != 1 or "navigator.serviceWorker.register(" in result:
        raise ValueError("Could not safely disable the copied atlas.js worker registration")
    return result


def collect_dependencies(page, manifest):
    """Include static page imports plus assets used dynamically by its scripts."""
    required = set()

    def add(url, base=ROOT):
        parsed = urlsplit(html.unescape(url.strip().strip("\"'")))
        if parsed.scheme or parsed.netloc or not parsed.path:
            return
        source = (base / unquote(parsed.path)).resolve()
        if not source.is_relative_to(ROOT) or source.relative_to(ROOT).parts[0] not in {"assets", "scripts"}:
            return
        if not source.is_file():
            raise ValueError(f"Missing page dependency: {source.relative_to(ROOT).as_posix()}")
        required.add(source.relative_to(ROOT))

    for url in re.findall(r'(?:src|href)=["\']([^"\']+)', page):
        add(url)
    for icon in manifest.get("icons", []):
        add(icon["src"])
    scanned = set()
    while pending := required - scanned:
        for relative in pending:
            scanned.add(relative)
            if relative == Path("scripts/theater-data.js"):
                continue  # This file is generated, with the new place map only.
            source = ROOT / relative
            if source.suffix not in {".js", ".css", ".svg"}:
                continue
            text = source.read_text(encoding="utf-8")
            for url in re.findall(r'["\'`](assets/[^"\'`\s<>]+)', text):
                add(url)
            if source.suffix == ".css":
                for url in re.findall(r"url\(([^)]+)\)", text):
                    add(url, source.parent)
    return required


def film_gallery(films):
    escape = lambda value: html.escape(str(value), quote=True)
    sections = []
    for film in films:
        media = []
        for clip in film["media"]:
            attrs = f'src="{escape(clip["src"])}"'
            for key, attribute in [("poster", "poster"), ("portraitSrc", "data-portrait-src"),
                                   ("portraitPoster", "data-portrait-poster")]:
                if clip.get(key):
                    attrs += f' {attribute}="{escape(clip[key])}"'
            if clip["type"] == "video":
                media.append(f'<video {attrs} controls playsinline preload="none" aria-label="{escape(film["date"] + " · " + film["title"])}"></video>')
            else:
                media.append(f'<img {attrs} alt="{escape(film["title"])}" loading="lazy" />')
        sections.append(f'<article id="{escape(film["id"])}"><p class="date">{escape(film["date"])}</p><h2>{escape(film["title"] or film["label"])}</h2>{"".join(media)}</article>')
    return '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#eee7db"><title>沿途片段 · V3 预览</title>
<style>*{box-sizing:border-box}body{margin:0;background:#eee7db;color:#514b3f;font-family:system-ui,"Microsoft YaHei",sans-serif}header,main{width:min(1040px,100%);margin:auto;padding:22px}header{display:flex;align-items:center;justify-content:space-between;gap:16px}a{color:#946044;text-decoration:none}header span,.date{font-size:12px;color:#8c7e68}h1{margin:22px 0;font-size:27px;font-weight:500}article{margin:0 0 28px;padding:20px;background:#faf4e7;box-shadow:3px 5px 0 #d8c9af;border:1px solid #fff7}h2{font-size:19px;font-weight:500;margin:5px 0 17px}.date{margin:0}video,img{display:block;width:100%;max-height:75svh;object-fit:contain;margin:12px auto 0;background:#25241e}video.portrait,img.portrait{width:auto;max-width:100%;height:70svh}footer{padding:10px 0 30px;color:#8c7e68;font-size:12px}@media(max-width:600px){header,main{padding:18px}article{padding:14px}h1{font-size:24px}}</style>
<header><a href="./">← 回到沙盘</a><span>V3 预览</span></header><main><h1>沿途片段</h1>''' + "".join(sections) + '''<footer><a href="./">回到行程沙盘</a></footer></main>
<script>const tall=matchMedia('(max-width:600px) and (orientation:portrait)');function orient(){document.querySelectorAll('video,img').forEach(el=>{if(!el.dataset.wideSrc){el.dataset.wideSrc=el.getAttribute('src');el.dataset.widePoster=el.getAttribute('poster')||'';}const portrait=tall.matches&&el.dataset.portraitSrc;const src=portrait?el.dataset.portraitSrc:el.dataset.wideSrc;if(el.getAttribute('src')!==src){if(el.tagName==='VIDEO')el.pause();el.setAttribute('src',src);}if(el.tagName==='VIDEO')el.poster=(portrait?el.dataset.portraitPoster:'')||el.dataset.widePoster;el.classList.toggle('portrait',Boolean(portrait));});}tall.addEventListener('change',orient);orient();document.addEventListener('play',event=>{document.querySelectorAll('video').forEach(video=>{if(video!==event.target)video.pause();});},true);</script></html>'''


def build(dry_run=False):
    raw, films, place_films = read_films()
    config = read_root_config()
    config.pop("dailyFilms", None)
    config["placeFilms"] = place_films
    page = (ROOT / "index.html").read_text(encoding="utf-8")
    page, count = re.subn(r'(<span class="brand-sub">).*?(</span>)', r'\g<1>V3 预览\2', page, count=1)
    if count != 1:
        raise ValueError("Could not find preview brand subtitle")
    page, count = re.subn(r'(?=<button type="button" id="openLibrary")', '<a href="films.html">逐段看影片</a>', page, count=1)
    if count != 1:
        raise ValueError("Could not find the header menu insertion point")
    page = re.sub(r'<title>.*?</title>', '<title>青甘银川 · V3 预览</title>', page, count=1)
    version = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    page = re.sub(r'scripts/theater-data\.js(?:\?[^"\']*)?', f'scripts/theater-data.js?v=v3-{version}', page)
    manifest = json.loads((ROOT / "manifest.webmanifest").read_text(encoding="utf-8"))
    manifest.update(name="青甘银川 · V3 预览", short_name="V3 预览", id="./", start_url="./", scope="./")
    dependencies = collect_dependencies(page, manifest)
    copied_atlas = disable_preview_worker((ROOT / "scripts/atlas.js").read_text(encoding="utf-8"))
    generated = {"index.html": page, "manifest.webmanifest": json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                 "scripts/theater-data.js": "window.ROADBOOK_THEATER = " + json.dumps(config, ensure_ascii=False, indent=2) + ";\n",
                 "scripts/atlas.js": copied_atlas}
    # The reviewed gallery has its own design and scripts. Never overwrite it.
    if not (OUTPUT / "films.html").is_file():
        generated["films.html"] = film_gallery(films)
    for name, content in generated.items():
        if LOCAL_ABSOLUTE.search(content):
            raise ValueError(f"PC absolute path in generated {name}")
    if not dry_run:
        for relative in sorted(dependencies):
            if relative.as_posix() in generated:
                continue
            destination = OUTPUT / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if relative.suffix == ".svg":
                source = (ROOT / relative).read_text(encoding="utf-8")
                destination.write_text("\n".join(line.rstrip() for line in source.splitlines()) + "\n", encoding="utf-8")
            else:
                shutil.copyfile(ROOT / relative, destination)
        for relative, content in generated.items():
            destination = OUTPUT / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8")
    print(json.dumps({"dryRun": dry_run, "output": "preview/v3/", "films": len(films), "mappedPlaces": len(place_films),
                      "copiedFiles": len(dependencies - {Path(p) for p in generated}),
                      "generatedFiles": sorted(generated), "copiedMediaFiles": 0}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Validate input and report packaging without writing files")
    args = parser.parse_args()
    try:
        build(args.dry_run)
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(f"V3 preview: {error}", file=sys.stderr)
        raise SystemExit(2)
