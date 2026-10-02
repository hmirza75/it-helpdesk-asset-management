CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY,
    asset_tag TEXT NOT NULL UNIQUE COLLATE NOCASE,
    device_type TEXT NOT NULL,
    manufacturer TEXT NOT NULL,
    model TEXT NOT NULL,
    serial_number TEXT UNIQUE COLLATE NOCASE,
    assigned_employee TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL CHECK(status IN ('Available','Assigned','Repair','Retired')),
    purchase_date TEXT NOT NULL DEFAULT '',
    assignment_date TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK(status != 'Assigned' OR (assigned_employee != '' AND assignment_date != ''))
);
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    requester TEXT NOT NULL,
    category TEXT NOT NULL CHECK(category IN ('Account Access','Hardware','Software','Network','Security','Other')),
    priority TEXT NOT NULL CHECK(priority IN ('Low','Medium','High','Critical')),
    description TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('Open','In Progress','Waiting','Resolved','Closed')),
    technician TEXT NOT NULL DEFAULT '',
    resolution_notes TEXT NOT NULL DEFAULT '',
    asset_id INTEGER REFERENCES assets(id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK(status NOT IN ('Resolved','Closed') OR resolution_notes != '')
);
CREATE TABLE IF NOT EXISTS activity (
    id INTEGER PRIMARY KEY,
    entity_type TEXT NOT NULL CHECK(entity_type IN ('ticket','asset')),
    entity_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_asset ON tickets(asset_id);
CREATE INDEX IF NOT EXISTS idx_assets_status ON assets(status);
