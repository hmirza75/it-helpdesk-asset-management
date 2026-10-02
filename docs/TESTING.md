# Verification record

Verified on October 2, 2026 using Python 3.12, Flask 3.1.2, and a local Windows environment.

## Automated integration tests

Command: `python -m unittest discover -s tests -v` inside the project virtual environment.

**Result: 8 tests passed.** Tests run against disposable databases, leaving the demo database intact.

| Test | Evidence checked |
| --- | --- |
| Complete support workflow and counts | Add asset, assign asset, link new ticket, edit ticket, resolve with notes, preserved creation timestamp, updated timestamp, activity entries, exact count transitions |
| Filters and literal search | Every ticket filter, combined filters, formatted ticket ID, description search, literal wildcards, SQL-shaped input, asset filters, empty results |
| Demo counts and pages | Exact seeded totals/status/priority counts, every core GET page, missing record and unknown route responses |
| Resolution validation | Resolved/Closed requires notes, rejected edit preserves original record |
| Assignment dates and duplicates | Required assignment details, invalid dates, reversed dates, invalid status, case-insensitive duplicate tags and serials, multiple blank serials |
| Invalid ticket values and foreign keys | Missing fields, invalid enums/IDs, long input, foreign-key enforcement, prevention of deleting a linked asset |
| Form tokens and escaping | Missing/malformed token rejected, HTML in input escaped on output |
| CLI preservation | Initialization does not wipe records; repeat seeding refuses safely |

## Browser verification

Using local Microsoft Edge through Playwright (development verification only; not an application dependency):

- Loaded dashboard, ticket queue, asset inventory, and ticket detail pages successfully.
- Applied In Progress + High in the visible ticket filter form; confirmed one result.
- Followed the result and opened Edit ticket; confirmed the correct linked asset was selected.
- Captured actual desktop screenshots at 1440 pixels wide.
- Checked the dashboard at 390 pixels wide, with no page-level horizontal overflow. Wide tables scroll inside their containers.
- No JavaScript page errors were reported.
- Visually reviewed desktop and mobile dashboard captures.

The create/update/resolve/assign/link operations are exercised by the automated HTTP integration tests. The browser check covers rendering and navigation, not a separate exhaustive browser suite.

## Issues addressed

- An existing local application occupied port 5000. The app now defaults to 5057, configurable through `PORT`.
- Unknown URL handling now accounts for Flask having no matched route, so the shared navigation can render the error page.
- Malformed non-ASCII form tokens now receive a normal bad-request response instead of causing a string comparison error.

No authentication, authorization, load, concurrency, or production deployment testing is claimed. There is no production deployment in this project.
