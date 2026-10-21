#!/usr/bin/env python3
"""
RSS feed of selected NHK WORLD-JAPAN episodes (default: Time and Tide "YOKAI" episodes).

Source: NHK's public shows API (the same JSON the show page loads):
  https://api.nhkworld.jp/showsapi/v1/en/video_programs/<program>/video_episodes

Usage:
  python nhk_yokai_rss.py                          # fetch live, write nhk_yokai.xml
  python nhk_yokai_rss.py --json episodes.json     # parse a saved response (testing)
  python nhk_yokai_rss.py --match "SAMURAI CASTLES" --name "Samurai Castles" -o castles.xml
"""
import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone
from email.utils import format_datetime
from xml.sax.saxutils import escape

API = "https://api.nhkworld.jp/showsapi/v1/en/video_programs/{p}/video_episodes?limit=100&offset={o}"
SITE = "https://www3.nhk.or.jp"


def fetch_all(program):
    items, offset = [], 0
    while True:
        req = urllib.request.Request(
            API.format(p=program, o=offset),
            headers={"User-Agent": "Mozilla/5.0 (personal RSS script)", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r)
        items += d.get("items", [])
        if not d.get("pagination", {}).get("next"):
            return items
        offset += len(d.get("items", [])) or 100


def parse_dt(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def pick(items, match):
    """Keep episodes whose title starts with `match` (case-insensitive). Dashes vary in titles, so
    only the prefix is compared."""
    m = match.upper()
    out = []
    for e in items:
        title = (e.get("title") or "").strip()
        if title.upper().startswith(m):
            video = e.get("video") or {}
            when = parse_dt(video.get("published_at")) or parse_dt(e.get("first_broadcasted_at"))
            out.append({
                "id": e["id"],
                "title": title,
                "desc": (e.get("description") or "").strip(),
                "url": SITE + e["url"],
                "date": when,
                "expires": parse_dt(video.get("expired_at")),
            })
    out.sort(key=lambda x: x["date"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return out


def build_feed(name, program_url, eps):
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0"><channel>',
        f"<title>{escape(name)}</title>",
        f"<link>{escape(program_url)}</link>",
        f"<description>{escape(name)} (unofficial feed)</description>",
        "<language>en</language>",
    ]
    for e in eps:
        desc = e["desc"]
        if e["expires"]:
            desc += f" (Available until {e['expires']:%Y-%m-%d})"
        out += [
            "<item>",
            f"<title>{escape(e['title'])}</title>",
            f"<link>{escape(e['url'])}</link>",
            f'<guid isPermaLink="false">nhkworld-episode-{e["id"]}</guid>',
        ]
        if e["date"]:
            out.append(f"<pubDate>{format_datetime(e['date'])}</pubDate>")
        out += [f"<description>{escape(desc)}</description>", "</item>"]
    out.append("</channel></rss>")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--program", default="timetide")
    ap.add_argument("--match", default="YOKAI", help="keep episodes whose title starts with this")
    ap.add_argument("--name", default="Time and Tide - YOKAI episodes (NHK WORLD-JAPAN)")
    ap.add_argument("--json", help="parse a saved API response instead of fetching")
    ap.add_argument("-o", "--output", default="nhk_yokai.xml")
    a = ap.parse_args()

    items = json.load(open(a.json, encoding="utf-8"))["items"] if a.json else fetch_all(a.program)
    eps = pick(items, a.match)
    if not eps:
        sys.exit(f"No episodes starting with {a.match!r} among {len(items)} - the API format may have changed.")
    with open(a.output, "w", encoding="utf-8") as f:
        f.write(build_feed(a.name, f"{SITE}/nhkworld/en/shows/{a.program}/", eps))
    print(f"wrote {len(eps)} of {len(items)} episodes to {a.output}")
    for e in eps:
        print(e["id"], f"{e['date']:%Y-%m-%d}" if e["date"] else "-", e["title"])


if __name__ == "__main__":
    main()
