# Things to Do in Central Oregon

Public, filterable list of upcoming events in Bend and Central Oregon, served by GitHub Pages.

- `index.html`: the page. Loads `events.json`, filters client-side, offers Google/Android and Apple (.ics) calendar buttons.
- `events.json`: generated weekly. Upcoming events only; no private status, scores or notes.
- `build.py`: turns rows exported from the private database Sheet into `events.json`.
  `python3 build.py rows.json events.json`

Updated every Monday morning by a scheduled Claude task.

Saved events: visitors can tap Save on any event. Saved events, notes and reminder lead times live only in that browser (localStorage). The page shows a reminder banner before a saved event, flags saved events that moved to a new date or dropped off the list (possibly cancelled), exports all saved events to one .ics with alarms, and shares a saved list by link.
