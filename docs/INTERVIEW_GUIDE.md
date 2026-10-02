# Interview walkthrough

## 30-second project explanation

“This is a Flask and SQLite application for tracking IT support tickets and workplace assets. A technician can prioritize a request, link a device, record troubleshooting details, and document the resolution. I focused on a complete local workflow, clear data validation, useful filtering, and integration tests rather than adding infrastructure the project did not need. All examples are fictional.”

Understand and demonstrate the code before using this explanation. Be candid about the tools and assistance used to build it.

## 1. How Flask routes requests

Decorators associate paths and HTTP methods with functions. `GET /tickets` calls `tickets()`, obtains matching records, and renders `tickets.html`. `GET /tickets/2` converts `2` to an integer and loads that ticket. `POST /tickets/2/edit` validates the form, updates the row, records activity, and redirects to the detail page. Jinja converts the data into HTML; no client-side application is required.

`create_app()` allows tests to supply a temporary database. `get_db()` reuses one connection during each request, and teardown closes it afterward.

## 2. How SQLite stores data

SQLite stores relational tables in one local file: `instance/helpdesk.sqlite`. The schema defines types, primary keys, uniqueness, status checks, and a foreign key. Dates are ISO date strings; timestamps are UTC text. Python executes SQL with bound parameters. Writes use `with db:` so successful work commits and failures roll back.

SQLite makes this portable and easy to inspect, but it is not a claim of large-scale concurrent-write performance. There is no ORM: the SQL is explicit and small enough to understand directly.

## 3. How tickets and assets relate

`tickets.asset_id` references `assets.id` or is `NULL` for requests unrelated to a device. This is a many-to-one relationship: many tickets may reference the same device. The asset detail query uses `WHERE asset_id = ?` to display related tickets. Foreign keys are enabled on each connection; an asset referenced by a ticket cannot be removed through a direct database deletion.

Requester and technician names are text fields, not separate user accounts. Asset employees are also text; the system does not infer permissions or automatically assign a ticket's requester as the asset owner.

## 4. How filtering works

The filter form submits a GET request, for example:

```text
/tickets?status=In+Progress&priority=High&requester=Morgan
```

The server builds an allowlisted SQL condition for each selected field and joins those conditions using `AND`. Name fields use substring matching. Free text searches several columns with `OR`. All values are parameters, and literal wildcard characters are escaped. The filters remain in the URL and in the form, so results are bookmarkable and shareable locally.

## 5. Most important decisions

- **Server-rendered Flask:** fewer moving parts; the browser uses normal links and forms.
- **One direct dependency:** Python supplies SQLite and the test framework.
- **Validation plus database constraints:** readable feedback in forms, with database protection for key invariants.
- **Nullable asset relationship:** account and software tickets need not invent a device.
- **Live SQL counts:** no separately stored counters to become stale.
- **Small activity log:** useful recent changes without claiming a full audit history.
- **Explicit limitations:** no login, public hosting, or integrations; no concurrency conflict detection yet.

## 6. Three technical problems to discuss

### A. Keeping linked data consistent

**Problem:** A ticket can reference a device that does not exist, or an update can save without its activity entry.

**Implementation:** Validate asset IDs, enable `PRAGMA foreign_keys = ON` on every connection, and write records and activity in the same transaction. Tests reject invalid IDs and verify linked assets cannot be deleted. Discuss why SQLite requires foreign-key enforcement per connection and how rollback works.

**Tradeoff:** The activity table stores a polymorphic entity ID without a foreign key. The application has no delete operation, but manual database edits could leave stale activity links. A richer audit system would need stronger modeling.

### B. Search that is flexible without treating input as SQL

**Problem:** Users need multiple filters, but concatenating raw values risks SQL injection, and `%` or `_` can accidentally match everything in a `LIKE` query.

**Implementation:** Allowlist columns, bind values using placeholders, combine selected filters with `AND`, and escape LIKE wildcards with an explicit escape character. Tests use ordinary text, `%`, `_`, and an SQL-shaped string.

**Tradeoff:** Leading-wildcard searches scan rows, suitable for the demo but a reason to consider full-text search and pagination at larger scale.

### C. Testing a workflow instead of only checking page responses

**Problem:** A page can return 200 while assignment rules, foreign keys, or dashboard counts are wrong.

**Implementation:** A test creates an asset, assigns it, creates a linked ticket, moves it through In Progress and Resolved, and verifies persisted fields, relation links, activity count, and exact dashboard transitions. Each test has a new temporary SQLite file. Browser checks separately caught a local port collision; the app moved to configurable port 5057.

**Tradeoff:** The tests do not simulate simultaneous editors. Last-write-wins remains a documented limitation; a version column and conditional UPDATE would be a sensible next step.

## Suggested live demo

Show the linked monitor/dock example, create a new ticket, deliberately try resolving it without notes, then add notes and save. Explain the error handling, database update, and count change. Open `app.py`, `schema.sql`, and `tests/test_app.py` to connect the visible behavior to the implementation.
