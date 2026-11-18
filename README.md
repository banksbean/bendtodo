# Things to Do in Central Oregon

Public, filterable list of upcoming events in Bend and Central Oregon, served by GitHub Pages.

- `index.html`: the page. Loads `events.json`, filters client-side, offers Google/Android and Apple (.ics) calendar buttons.
- `events.json`: generated weekly. Upcoming events only; no private status, scores or notes.
- `build.py`: turns rows exported from the private database Sheet into `events.json`.
  `python3 build.py rows.json events.json`

Updated every Monday morning by a scheduled Claude task.
