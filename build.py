#!/usr/bin/env python3
"""Build the public events.json from rows of the private Sheet.

Input: a JSON file holding a list of rows from the Sheet's "Unfiltered" tab,
columns A:L in this order:
  Date, Event, Category, Town, Price, Status, Fit, When, Venue, Source, Link, Notes
Date may be "YYYY-MM-DD" or {"date": "YYYY-MM-DD"}.

Output: events.json with upcoming, public-safe events only. Status, Fit and
Notes are never written out.

Optional third input: a JSON file of rows from the Sheet's "Recurring" tab,
columns A:H = Event, Schedule, Venue, Town, Category, Price, Source, Link.
Items with a parseable schedule are expanded into dated entries for the next
RECUR_WEEKS weeks; the rest go into "ongoing". Every event gets a
"recurring" flag, recomputed on each build.

Usage: python3 build.py rows.json events.json [recurring.json]
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
RECUR_WEEKS = 4
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


# ---------- recurring ----------
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
ORD = {"first": 1, "second": 2, "third": 3, "fourth": 4, "last": -1}
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
REC_WHEN = re.compile(r"\b(first|second|third|fourth|last)\s+(mon|tue|wed|thu|fri|sat|sun)"
                      r"|\b(mondays|tuesdays|wednesdays|thursdays|fridays|saturdays|sundays|weekly|monthly|daily|every)\b", re.I)


def norm(t):
    t = re.sub(r"\(.*?\)", "", (t or "").lower())
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def day_idx(word):
    w = word.lower()[:3]
    return DAYS.index(w) if w in DAYS else None


def parse_schedule(text):
    """Return list of (rule, time_text) where rule is ("weekly", {days}) or ("nth", n, day) or ("daily",).
    Empty list means not parseable."""
    t = (text or "").strip()
    low = t.lower()
    if not t or "ongoing" in low or "varies" in low:
        return []
    out = []
    for seg in [x.strip() for x in t.split(",") if x.strip()]:
        sl = seg.lower()
        if sl in ("monthly",):
            continue
        m = re.search(r"\b(first|second|third|fourth|last)\s+(mon|tue|wed|thu|fri|sat|sun)\w*", sl)
        if m:
            out.append((("nth", ORD[m.group(1)], day_idx(m.group(2))), seg))
            continue
        if "monthly" in low:  # monthly with no ordinal: date unknown
            return []
        if re.search(r"\bdaily\b", sl):
            out.append((("daily",), seg))
            continue
        m = re.search(r"\b(mon|tue|wed|thu|fri|sat|sun)\w*\s*-\s*(mon|tue|wed|thu|fri|sat|sun)\w*", sl)
        if m:
            a, b = day_idx(m.group(1)), day_idx(m.group(2))
            days = {(a + i) % 7 for i in range(((b - a) % 7) + 1)}
            out.append((("weekly", days), seg))
            continue
        days = {day_idx(w) for w in re.findall(r"\b(mon|tue|wed|thu|fri|sat|sun)[a-z]*\b", sl)}
        days.discard(None)
        if days:
            out.append((("weekly", days), seg))
            continue
        return []
    return out


def until_date(text, today):
    m = re.search(r"through\s+([a-z]{3})[a-z]*\.?\s+(\d{1,2})", (text or "").lower())
    if not m or m.group(1) not in MONTHS:
        return None
    mo, d = MONTHS.index(m.group(1)) + 1, int(m.group(2))
    y = today.year if (mo, d) >= (today.month, today.day) else today.year + 1
    try:
        return datetime(y, mo, d).date()
    except ValueError:
        return None


def occurs(rule, day):
    kind = rule[0]
    if kind == "daily":
        return True
    if kind == "weekly":
        return day.weekday() in rule[1]
    n, wd = rule[1], rule[2]
    if day.weekday() != wd:
        return False
    if n == -1:
        return (day + timedelta(days=7)).month != day.month
    return (day.day - 1) // 7 + 1 == n


def expand_recurring(rec_rows, today_iso):
    today = datetime.fromisoformat(today_iso).date()
    end = today + timedelta(weeks=RECUR_WEEKS)
    dated, ongoing = [], []
    for row in rec_rows:
        row = (list(row) + [None] * 8)[:8]
        title, sched, venue, town, cat, price, source, link = [cell(x) for x in row]
        if not title or title == "Event":
            continue
        blob = f"{title} {venue} {source}".lower()
        if any(x in blob for x in EXCLUDED_ORGANIZERS):
            continue
        base = {"title": title, "category": cat, "group": group_for(cat), "town": town, "price": price,
                "venue": venue, "source": source, "link": link, "recurring": True}
        rules = parse_schedule(sched)
        if not rules:
            ongoing.append({k: v for k, v in dict(base, when=sched).items() if v not in (None, "")})
            continue
        stop = min(end, until_date(sched, today) or end)
        day = today
        while day <= stop:
            for rule, seg in rules:
                if occurs(rule, day):
                    start, fin, nxt = parse_times(seg)
                    ev = dict(base, date=day.isoformat(), when=seg)
                    if start:
                        ev["start"], ev["end"] = start, fin
                        if nxt:
                            ev["endsNextDay"] = True
                    dated.append({k: v for k, v in ev.items() if v not in (None, "")})
                    break
            day += timedelta(days=1)
    return dated, ongoing


def mark_recurring(events, rec_titles):
    dates = {}
    def add(k, d):
        dates.setdefault(k, set()).add(d)
    for e in events:
        t = norm(e["title"])
        add("t|" + t, e["date"])
        add("tv|" + t + "|" + norm(e.get("venue")), e["date"])
        link = e.get("link") or ""
        if link and not re.search(r"/whats-on/events/?$", link):
            add("l|" + link, e["date"])
    for e in events:
        t = norm(e["title"])
        link = e.get("link") or ""
        rec = (e.get("recurring") or t in rec_titles or bool(REC_WHEN.search(e.get("when") or ""))
               or len(dates["t|" + t]) >= 3
               or len(dates["tv|" + t + "|" + norm(e.get("venue"))]) >= 2
               or (link and "l|" + link in dates and len(dates["l|" + link]) >= 2))
        e["recurring"] = bool(rec)


def main():
    src, dst = sys.argv[1], sys.argv[2]
    with open(src) as f:
        rows = json.load(f)
    rec_rows = []
    if len(sys.argv) > 3:
        with open(sys.argv[3]) as f:
            rec_rows = json.load(f)
    today = datetime.now(TZ).date().isoformat()
    events = build(rows, today)
    dated, ongoing = expand_recurring(rec_rows, today)
    by_date = {}
    for e in events:
        by_date.setdefault(e["date"], []).append(norm(e["title"]))
    def dup(e):
        t = norm(e["title"])
        return any(x == t or x.startswith(t + " ") or t.startswith(x + " ") for x in by_date.get(e["date"], []))
    events += [e for e in dated if not dup(e)]
    events.sort(key=lambda e: (e["date"], e.get("start", "99"), e["title"]))
    mark_recurring(events, {norm(r[0]) for r in rec_rows if r and isinstance(r[0], str)})
    data = {"updated": datetime.now(TZ).isoformat(timespec="minutes"), "count": len(events),
            "events": events, "ongoing": ongoing}
    with open(dst, "w") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    print(f"Wrote {len(events)} events to {dst}")


if __name__ == "__main__":
    main()
