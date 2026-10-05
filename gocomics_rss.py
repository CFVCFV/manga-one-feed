#!/usr/bin/env python3
"""
Link-only RSS feed for a daily GoComics strip.

Each item links to https://www.gocomics.com/<slug>/YYYY/MM/DD for the last N days.
No scraping and no images: the feed just tells your reader that a new day's page exists.

Usage:
  python gocomics_rss.py nancy                      # writes nancy.xml
  python gocomics_rss.py nancy --days 14 -o out.xml
  python gocomics_rss.py calvinandhobbes --name "Calvin and Hobbes"
"""
import argparse
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from xml.sax.saxutils import escape

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("America/New_York")  # GoComics strips roll over on US Eastern time
except Exception:  # tzdata missing (common on Windows): fall back to a fixed offset
    TZ = timezone(timedelta(hours=-5))

SITE = "https://www.gocomics.com"


def build_feed(slug, name, days):
    today = datetime.now(TZ).date()
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0"><channel>',
        f"<title>{escape(name)} - GoComics</title>",
        f"<link>{SITE}/{escape(slug)}</link>",
        f"<description>Daily {escape(name)} strip links (unofficial feed)</description>",
        "<language>en</language>",
    ]
    for n in range(days):
        d = today - timedelta(days=n)
        url = f"{SITE}/{slug}/{d:%Y/%m/%d}"
        pub = format_datetime(datetime(d.year, d.month, d.day, tzinfo=TZ))
        out += [
            "<item>",
            f"<title>{escape(name)} - {d:%Y-%m-%d}</title>",
            f"<link>{url}</link>",
            f'<guid isPermaLink="true">{url}</guid>',
            f"<pubDate>{pub}</pubDate>",
            f"<description>{escape(name)} strip for {d:%Y-%m-%d}</description>",
            "</item>",
        ]
    out.append("</channel></rss>")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", help="the comic's URL name, e.g. nancy")
    ap.add_argument("--name", help="display name (default: slug capitalised)")
    ap.add_argument("--days", type=int, default=10)
    ap.add_argument("-o", "--output")
    a = ap.parse_args()
    name = a.name or a.slug.replace("-", " ").title()
    path = a.output or f"{a.slug}.xml"
    with open(path, "w", encoding="utf-8") as f:
        f.write(build_feed(a.slug, name, a.days))
    print(f"wrote {a.days} items to {path}")


if __name__ == "__main__":
    main()
