"""Entirely fictional examples; never imported from an employer."""
import click
from db import get_db


def seed_demo():
    db = get_db()
    if db.execute('SELECT COUNT(*) FROM tickets').fetchone()[0] or db.execute('SELECT COUNT(*) FROM assets').fetchone()[0]:
        raise click.ClickException('Demo seeding requires empty tickets and assets; existing data was preserved.')
    stamp = '2026-10-02 14:00:00 UTC'
    asset_rows = [
        ('DEMO-LT-101', 'Laptop', 'Lenovo', 'ThinkPad T14', 'DEMO-SN-101', 'Morgan Reed', 'Assigned', '2026-06-01', '2026-06-05', 'Fictional engineering laptop.'),
        ('DEMO-LT-102', 'Laptop', 'Dell', 'Latitude 5450', 'DEMO-SN-102', '', 'Available', '2026-07-10', '', 'Ready for a fictional new hire.'),
        ('DEMO-MN-103', 'Monitor', 'Dell', 'P2425H', 'DEMO-SN-103', 'Jordan Lee', 'Assigned', '2026-05-12', '2026-05-15', 'Fictional office monitor.'),
        ('DEMO-DK-104', 'Dock', 'Lenovo', 'USB-C Dock', 'DEMO-SN-104', 'Morgan Reed', 'Repair', '2026-06-01', '2026-06-05', 'Intermittent display connection; replacement cable under evaluation.'),
        ('DEMO-LT-105', 'Laptop', 'HP', 'EliteBook 840', 'DEMO-SN-105', '', 'Retired', '2021-03-01', '', 'Fictional end-of-life record; no disposal certification implied.'),
        ('DEMO-PH-106', 'Phone', 'Apple', 'iPhone 14', 'DEMO-SN-106', '', 'Available', '2026-08-01', '', 'Spare demonstration device.')]
    ticket_rows = [
        ('Unable to access shared workspace', 'Jordan Lee', 'Account Access', 'High', 'Demo user receives an access denied message for a shared project folder.', 'Open', 'Alex Rivera', '', None),
        ('External monitor disconnects', 'Morgan Reed', 'Hardware', 'High', 'Display drops after the laptop wakes. Reproduced with the assigned USB-C dock.', 'In Progress', 'Alex Rivera', '', 4),
        ('Salesforce report export issue', 'Casey Brooks', 'Software', 'Medium', 'Fictional user needs help exporting a sample report; no actual Salesforce connection is used.', 'Waiting', 'Taylor Quinn', '', None),
        ('Intermittent conference room Wi-Fi', 'Sam Parker', 'Network', 'Critical', 'Demo conference room connection drops during test calls.', 'Open', 'Taylor Quinn', '', None),
        ('Review suspicious sample email', 'Riley Chen', 'Security', 'High', 'Fictional training message reported by a demo user.', 'Resolved', 'Alex Rivera', 'Reviewed the fictional message and documented reporting steps.', None),
        ('Prepare spare laptop for onboarding', 'Avery Stone', 'Hardware', 'Medium', 'Check the spare laptop before assignment to a fictional new employee.', 'In Progress', 'Taylor Quinn', '', 2),
        ('Monitor input source help', 'Jordan Lee', 'Hardware', 'Low', 'Display was set to the wrong input source.', 'Closed', 'Alex Rivera', 'Selected the correct input and confirmed the display worked.', 3),
        ('How to request software access', 'Casey Brooks', 'Other', 'Low', 'Demo user asks where to request a new tool.', 'Resolved', 'Taylor Quinn', 'Explained the fictional approval workflow and request requirements.', None)]
    with db:
        ids = []
        for row in asset_rows:
            ids.append(db.execute('INSERT INTO assets (asset_tag,device_type,manufacturer,model,serial_number,assigned_employee,status,purchase_date,assignment_date,notes,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', (*row, stamp, stamp)).lastrowid)
        for row in ticket_rows:
            row = (*row[:-1], ids[row[-1]-1] if row[-1] else None)
            ticket_id = db.execute('INSERT INTO tickets (title,requester,category,priority,description,status,technician,resolution_notes,asset_id,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)', (*row, stamp, stamp)).lastrowid
            db.execute('INSERT INTO activity (entity_type,entity_id,message,created_at) VALUES (?,?,?,?)', ('ticket', ticket_id, f'Loaded fictional demo HD-{ticket_id:04d} · {row[5]}', stamp))
