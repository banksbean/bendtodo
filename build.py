#!/usr/bin/env python3
"""Build the public events.json from rows of the private Sheet.

Input: a JSON file holding a list of rows from the Sheet's "Unfiltered" tab,
columns A:L in this order:
  Date, Event, Category, Town, Price, Status, Fit, When, Venue, Source, Link, Notes
Date may be "YYYY-MM-DD" or {"date": "YYYY-MM-DD"}.

Output: events.json with upcoming, public-safe events only. Status, Fit and
Notes are never written out.

Usage: python3 build.py rows.json events.json
"""
import json
import re
import sys
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("America/Los_Angeles")
except Exception:  # pragma: no cover
    TZ = timezone(timedelta(hours=-8))

EXCLUDED_ORGANIZERS = ["wanderlust", "diycave"]
HIDDEN_STATUSES = {"declined", "cancelled"}

GROUPS = [
    ("Music", ["music", "dj", "concert"]),
    ("Outdoors & Snow", ["outdoor", "ski", "snow", "astronomy", "climbing", "hike", "nature"]),
    ("Talks & Learning", ["lecture", "talk", "science", "history", "words", "museum", "conservation", "civic"]),
    ("Making & Arts", ["making", "fabrication", "craft", "art", "diy"]),
    ("Film & Stage", ["film", "theater", "comedy", "dance", "variety"]),
    ("Food & Drink", ["food", "drink"]),
    ("Markets & Seasonal", ["market", "seasonal", "nye"]),
    ("Wellness & Fitness", ["wellness", "fitness", "health", "sport", "race", "yoga", "meditation"]),
    ("Social & Networking", ["social", "networking", "business", "nightlife", "games", "tech", "fundraiser", "volunteer"]),
]


def group_for(category):
    c = (category or "").lower()
    for name, keys in GROUPS:
        if any(k in c for k in keys):
            return name
    return "Other"


def cell(v):
    if isinstance(v, dict):
        for k in ("date", "value", "number", "markdown"):
            if k in v:
                return cell(v[k])
        return None
    if isinstance(v, str):
        v = v.strip()
        if v.startswith("'"):
            v = v[1:]
        return v or None
    return v


T = r"(\d{1,2})(?::(\d{2}))?"
M = r"\s*(a\.?m\.?|p\.?m\.?|noon)"
RANGE = re.compile(T + r"(?:" + M + r")?\s*-\s*" + T + M, re.I)
SINGLE = re.compile(T + M, re.I)


def to24(h, m, mer):
    h, m = int(h), int(m or 0)
    mer = (mer or "").lower().replace(".", "")
    if mer == "noon":
        return 12, m
    if mer == "pm" and h != 12:
        h += 12
    if mer == "am" and h == 12:
        h = 0
    return h, m


def parse_times(when):
    """Return (start "HH:MM", end "HH:MM", ends_next_day) or (None, None, False)."""
    if not when:
        return None, None, False
    r = RANGE.search(when)
    if r:
        sh, sm, smer, eh, em, emer = r.groups()
        e = to24(eh, em, emer)
        if smer:
            s = to24(sh, sm, smer)
        else:
            s = to24(sh, sm, emer)
            if s[0] * 60 + s[1] > e[0] * 60 + e[1]:  # "10-1 p.m." means 10 a.m.
                alt = to24(sh, sm, "am")
                if alt[0] * 60 + alt[1] < e[0] * 60 + e[1]:
                    s = alt
        nxt = e[0] * 60 + e[1] <= s[0] * 60 + s[1]
        return f"{s[0]:02d}:{s[1]:02d}", f"{e[0]:02d}:{e[1]:02d}", nxt
    s1 = SINGLE.search(when)
    if s1:
        s = to24(*s1.groups())
        end = datetime(2000, 1, 1, *s) + timedelta(hours=2)
        return f"{s[0]:02d}:{s[1]:02d}", f"{end.hour:02d}:{end.minute:02d}", end.day == 2
    return None, None, False


def build(rows, today):
    out, seen = [], set()
    for row in rows:
        row = (list(row) + [None] * 12)[:12]
        date, title, cat, town, price, status, _fit, when, venue, source, link, _notes = [cell(x) for x in row]
        if not date or not title or date == "Date":
            continue
        if (status or "").lower() in HIDDEN_STATUSES:
            continue
        blob = f"{title} {venue} {source}".lower()
        if any(x in blob for x in EXCLUDED_ORGANIZERS):
            continue
        if "(students)" in title.lower():
            continue
        if date < today:
            continue
        key = (date, title.lower())
        if key in seen:
            continue
        seen.add(key)
        start, end, nxt = parse_times(when)
        ev = {
            "date": date,
            "title": title,
            "category": cat,
            "group": group_for(cat),
            "town": town,
            "price": price,
            "when": when,
            "venue": venue,
            "source": source,
            "link": link,
        }
        if start:
            ev["start"], ev["end"] = start, end
            if nxt:
                ev["endsNextDay"] = True
        out.append({k: v for k, v in ev.items() if v not in (None, "")})
    out.sort(key=lambda e: (e["date"], e.get("start", "99"), e["title"]))
    return out


def main():
    src, dst = sys.argv[1], sys.argv[2]
    with open(src) as f:
        rows = json.load(f)
    today = datetime.now(TZ).date().isoformat()
    events = build(rows, today)
    data = {"updated": datetime.now(TZ).isoformat(timespec="minutes"), "count": len(events), "events": events}
    with open(dst, "w") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    print(f"Wrote {len(events)} events to {dst}")


if __name__ == "__main__":
    main()
