#!/usr/bin/env python3
"""
Build an RSS feed of chapters for one Manga One series.

Data source: the site's own (undocumented) viewer_v2 endpoint, which returns a
Protobuf message. We parse it without a schema and pick out the chapter items
(id, title, subtitle, date).

Usage:
  python manga_one_rss.py                  # fetch live, write feed.xml
  python manga_one_rss.py --hex resp.txt   # parse a hex dump of a response (for testing)
  python manga_one_rss.py --bin resp.bin   # parse a saved raw response
"""
import argparse
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from xml.sax.saxutils import escape

TITLE_ID = 1349
SEED_CHAPTER_ID = 359863  # any chapter that exists; the list is requested newest-first
SITE = "https://manga-one.com"
API = (
    SITE + "/api/client?rq=viewer_v2&title_id={t}&chapter_id={c}"
    "&page=1&limit=10&sort_type=desc&list_type=chapter"
    "&free_point=0&event_point=0&paid_point=0"
)
JST = timezone(timedelta(hours=9))
DATE_RE = re.compile(r"^\d{4}/\d{2}/\d{2}$")


# ---------- minimal schema-less protobuf reader ----------
def read_varint(buf, i):
    shift = result = 0
    while True:
        if i >= len(buf):
            raise ValueError("truncated varint")
        b = buf[i]
        i += 1
        result |= (b & 0x7F) << shift
        if not b & 0x80:
            return result, i
        shift += 7
        if shift > 70:
            raise ValueError("varint too long")


def parse(buf):
    """Return [(field_no, wire_type, value)]; raise ValueError if not valid protobuf."""
    i, out = 0, []
    while i < len(buf):
        key, i = read_varint(buf, i)
        field, wt = key >> 3, key & 7
        if field == 0:
            raise ValueError("bad field number")
        if wt == 0:
            v, i = read_varint(buf, i)
        elif wt == 1:
            v, i = buf[i:i + 8], i + 8
        elif wt == 2:
            n, i = read_varint(buf, i)
            v, i = buf[i:i + n], i + n
        elif wt == 5:
            v, i = buf[i:i + 4], i + 4
        else:
            raise ValueError("unsupported wire type")
        if i > len(buf):
            raise ValueError("truncated field")
        out.append((field, wt, v))
    return out


def walk(buf, found, depth=0):
    """Recursively try to parse every length-delimited field as a sub-message."""
    if depth > 12:
        return
    try:
        fields = parse(buf)
    except ValueError:
        return
    found.append(fields)
    for _, wt, v in fields:
        if wt == 2 and len(v) > 2:
            walk(v, found, depth + 1)


def text(v):
    if v is None:
        return None
    try:
        return v.decode("utf-8")
    except UnicodeDecodeError:
        return None


# ---------- extraction ----------
def extract(buf):
    messages = []
    walk(buf, messages)
    series_name, chapters = None, {}
    for fields in messages:
        d = {}
        for f, wt, v in fields:
            d.setdefault((f, wt), v)  # first occurrence of each field
        num = d.get((1, 0))
        name = text(d.get((2, 2)))
        if num is None or not name:
            continue
        if num == TITLE_ID and series_name is None:
            series_name = name
            continue
        date = text(d.get((5, 2)))
        if date and DATE_RE.match(date) and num not in chapters:
            chapters[num] = {
                "id": num,
                "title": name,
                "subtitle": text(d.get((3, 2))) or "",
                "date": date,
            }
    items = sorted(chapters.values(), key=lambda c: c["id"], reverse=True)
    return series_name or f"Manga One {TITLE_ID}", items


# ---------- RSS ----------
def build_feed(series, items):
    link = f"{SITE}/manga/{TITLE_ID}/chapter/{items[0]['id']}" if items else SITE
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0"><channel>',
        f"<title>{escape(series)} - Manga One</title>",
        f"<link>{escape(link)}</link>",
        f"<description>{escape(series)} chapter updates</description>",
        "<language>ja</language>",
    ]
    for c in items:
        y, m, d = map(int, c["date"].split("/"))
        pub = format_datetime(datetime(y, m, d, tzinfo=JST))
        url = f"{SITE}/manga/{TITLE_ID}/chapter/{c['id']}"
        title = c["title"] + (f" {c['subtitle']}" if c["subtitle"] else "")
        out += [
            "<item>",
            f"<title>{escape(title)}</title>",
            f"<link>{escape(url)}</link>",
            f'<guid isPermaLink="true">{escape(url)}</guid>',
            f"<pubDate>{pub}</pubDate>",
            "</item>",
        ]
    out.append("</channel></rss>")
    return "\n".join(out)


def fetch():
    req = urllib.request.Request(
        API.format(t=TITLE_ID, c=SEED_CHAPTER_ID),
        data=b"",
        method="POST",
        headers={
            "User-Agent": "Mozilla/5.0 (personal RSS script)",
            "Referer": f"{SITE}/manga/{TITLE_ID}/chapter/{SEED_CHAPTER_ID}",
            "Origin": SITE,
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hex", help="file containing a hex dump of the response")
    ap.add_argument("--bin", help="file containing the raw response bytes")
    ap.add_argument("-o", "--output", default="feed.xml")
    a = ap.parse_args()

    if a.hex:
        raw = bytes.fromhex("".join(open(a.hex).read().split()))
    elif a.bin:
        raw = open(a.bin, "rb").read()
    else:
        raw = fetch()

    series, items = extract(raw)
    if not items:
        sys.exit("No chapters found - the response format may have changed or the request was refused.")
    with open(a.output, "w", encoding="utf-8") as f:
        f.write(build_feed(series, items))
    print(f"{series}: wrote {len(items)} items to {a.output}")
    for c in items:
        print(c["id"], c["date"], c["title"], c["subtitle"])


if __name__ == "__main__":
    main()
