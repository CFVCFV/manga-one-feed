#!/usr/bin/env python3
"""
RSS feed for a comicブースト (comic-boost.com) series.

Reads the chapter list straight from the series page HTML
(<a class="book-product-list-item" data-id=... data-title=...> plus
<p class="update-date">YYYY/MM/DD</p>) and writes an RSS 2.0 file.

Usage:
  python comic_boost_rss.py 01650001                 # fetch live, write 01650001.xml
  python comic_boost_rss.py 01650001 -o feed.xml
  python comic_boost_rss.py 01650001 --html page.html   # parse a saved page (testing)
"""
import argparse
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from html.parser import HTMLParser
from xml.sax.saxutils import escape

SITE = "https://comic-boost.com"
JST = timezone(timedelta(hours=9))
DATE_RE = re.compile(r"^\d{4}/\d{2}/\d{2}$")


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items = []
        self.og_title = None
        self._cur = None
        self._in_date = False
        self._in_coin = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = (a.get("class") or "").split()
        if tag == "meta" and a.get("property") == "og:title":
            self.og_title = a.get("content")
        if tag == "a" and "book-product-list-item" in cls and a.get("data-id"):
            href = a.get("href") or ""
            self._cur = {
                "id": a["data-id"],
                "title": a.get("data-title", "").strip(),
                "sub": a.get("data-sub", "").strip(),
                "coin": a.get("data-coin", "0"),
                # only free chapters have a real href; paid ones use javascript:void(0)
                "href": href if href.startswith("/product/") else None,
                "date": None,
                "free": False,
            }
        elif self._cur is not None:
            if tag == "p" and "update-date" in cls:
                self._in_date = True
            elif tag == "div" and "free" in cls:
                self._cur["free"] = True

    def handle_data(self, data):
        if self._cur is not None and self._in_date:
            t = data.strip()
            if t:
                self._cur["date"] = t

    def handle_endtag(self, tag):
        if tag == "p":
            self._in_date = False
        elif tag == "a" and self._cur is not None:
            self.items.append(self._cur)
            self._cur = None


def extract(html):
    p = Page()
    p.feed(html)
    series = (p.og_title or "").split("｜")[0].strip()
    items = [i for i in p.items if i["date"] and DATE_RE.match(i["date"])]
    seen, out = set(), []
    for i in sorted(items, key=lambda x: x["id"], reverse=True):
        if i["id"] not in seen:
            seen.add(i["id"])
            out.append(i)
    return series, out


def build_feed(content_id, series, items):
    page = f"{SITE}/content/{content_id}"
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0"><channel>',
        f"<title>{escape(series)} - comicブースト</title>",
        f"<link>{page}</link>",
        f"<description>{escape(series)} の更新(非公式フィード)</description>",
        "<language>ja</language>",
    ]
    for c in items:
        y, m, d = map(int, c["date"].split("/"))
        pub = format_datetime(datetime(y, m, d, 12, 0, tzinfo=JST))  # site updates at noon JST
        link = SITE + c["href"] if c["href"] else page
        price = "無料" if c["free"] else f"{c['coin']}コイン"
        out += [
            "<item>",
            f"<title>{escape(series)} {escape(c['title'])} ({price})</title>",
            f"<link>{escape(link)}</link>",
            f'<guid isPermaLink="false">{SITE}/product/{c["id"]}</guid>',
            f"<pubDate>{pub}</pubDate>",
            f"<description>{escape(c['title'])} / {price} / {escape(c['sub'])}</description>",
            "</item>",
        ]
    out.append("</channel></rss>")
    return "\n".join(out)


def fetch(content_id):
    req = urllib.request.Request(
        f"{SITE}/content/{content_id}",
        headers={"User-Agent": "Mozilla/5.0 (personal RSS script)", "Accept-Language": "ja"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("content_id", help="e.g. 01650001 (from comic-boost.com/content/<id>)")
    ap.add_argument("--html", help="parse a saved page instead of fetching")
    ap.add_argument("-o", "--output")
    a = ap.parse_args()

    html = open(a.html, encoding="utf-8").read() if a.html else fetch(a.content_id)
    series, items = extract(html)
    if not items:
        sys.exit("No chapters found - the page layout may have changed or the request was refused.")
    path = a.output or f"{a.content_id}.xml"
    with open(path, "w", encoding="utf-8") as f:
        f.write(build_feed(a.content_id, series or a.content_id, items))
    print(f"{series}: wrote {len(items)} items to {path}")
    for c in items:
        print(c["id"], c["date"], c["title"], "free" if c["free"] else f"{c['coin']} coin")


if __name__ == "__main__":
    main()
