"""Small, server-rendered IT operations portfolio application."""
import os
import secrets
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
import click
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from db import close_db, get_db, init_db

CATEGORIES = ('Account Access', 'Hardware', 'Software', 'Network', 'Security', 'Other')
PRIORITIES = ('Low', 'Medium', 'High', 'Critical')
TICKET_STATUSES = ('Open', 'In Progress', 'Waiting', 'Resolved', 'Closed')
ASSET_STATUSES = ('Available', 'Assigned', 'Repair', 'Retired')


def now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(SECRET_KEY=os.environ.get('SECRET_KEY') or secrets.token_hex(32),
                            DATABASE=str(Path(app.instance_path) / 'helpdesk.sqlite'),
                            MAX_CONTENT_LENGTH=64 * 1024,
                            SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')
    if test_config:
        app.config.update(test_config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    app.teardown_appcontext(close_db)

    @app.before_request
    def csrf_protection():
        if 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_hex(32)
        if request.method == 'POST' and not secrets.compare_digest(
                session['csrf_token'].encode(), request.form.get('csrf_token', '').encode()):
            abort(400, 'The form expired. Reload the page and try again.')

    @app.context_processor
    def options():
        return dict(categories=CATEGORIES, priorities=PRIORITIES,
                    ticket_statuses=TICKET_STATUSES, asset_statuses=ASSET_STATUSES)

    @app.cli.command('init-db')
    def initialize():
        init_db()
        click.echo('Database initialized (existing records preserved).')

    @app.cli.command('seed-demo')
    def seed():
        from seed import seed_demo
        init_db()
        seed_demo()
        click.echo('Fictional demo data ready.')

    def record(table, record_id):
        # Table names are internal constants, never request parameters.
        result = get_db().execute(f'SELECT * FROM {table} WHERE id = ?', (record_id,)).fetchone()
        if result is None:
            abort(404)
        return result

    @app.route('/')
    def dashboard():
        db = get_db()
        tickets = dict(db.execute('SELECT status, COUNT(*) FROM tickets GROUP BY status').fetchall())
        assets = dict(db.execute('SELECT status, COUNT(*) FROM assets GROUP BY status').fetchall())
        priority = dict(db.execute('SELECT priority, COUNT(*) FROM tickets GROUP BY priority').fetchall())
        return render_template('dashboard.html', ticket_counts=tickets, asset_counts=assets,
                               priority_counts=priority, total_tickets=sum(tickets.values()),
                               total_assets=sum(assets.values()),
                               recent=db.execute('SELECT * FROM tickets ORDER BY id DESC LIMIT 5').fetchall(),
                               activity=db.execute('SELECT * FROM activity ORDER BY id DESC LIMIT 8').fetchall())

    def filtered_records(kind):
        is_ticket = kind == 'tickets'
        fields = ('status', 'priority', 'category', 'requester', 'technician') if is_ticket else ('status', 'device_type', 'assigned_employee')
        clauses, params = [], []
        for field in fields:
            value = request.args.get(field, '').strip()
            if value:
                if field in ('requester', 'technician', 'assigned_employee'):
                    clauses.append(f'{field} LIKE ? ESCAPE CHAR(92)')
                    params.append(like_pattern(value))
                else:
                    clauses.append(f'{field} = ?')
                    params.append(value)
        q = request.args.get('q', '').strip()
        if q:
            searchable = ('title', 'requester', 'description', 'technician', "printf('HD-%04d', id)") if is_ticket else ('asset_tag', 'manufacturer', 'model', 'serial_number', 'assigned_employee', 'notes')
            clauses.append('(' + ' OR '.join(f'{field} LIKE ? ESCAPE CHAR(92)' for field in searchable) + ')')
            params.extend([like_pattern(q)] * len(searchable))
        where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
        return get_db().execute(f'SELECT * FROM {kind}{where} ORDER BY id DESC', params).fetchall()

    @app.route('/tickets')
    def tickets():
        return render_template('tickets.html', tickets=filtered_records('tickets'))

    @app.route('/assets')
    def assets():
        types = get_db().execute('SELECT DISTINCT device_type FROM assets ORDER BY device_type').fetchall()
        return render_template('assets.html', assets=filtered_records('assets'), device_types=[row[0] for row in types])

    @app.route('/tickets/<int:record_id>')
    def ticket_detail(record_id):
        ticket = record('tickets', record_id)
        asset = record('assets', ticket['asset_id']) if ticket['asset_id'] else None
        return render_template('ticket_detail.html', ticket=ticket, asset=asset)

    @app.route('/assets/<int:record_id>')
    def asset_detail(record_id):
        asset = record('assets', record_id)
        related = get_db().execute('SELECT * FROM tickets WHERE asset_id = ? ORDER BY id DESC', (record_id,)).fetchall()
        return render_template('asset_detail.html', asset=asset, tickets=related)

    def save(kind, record_id=None):
        is_ticket = kind == 'tickets'
        singular = 'ticket' if is_ticket else 'asset'
        existing = dict(record(kind, record_id)) if record_id else {}
        values = existing.copy()
        errors = []
        if request.method == 'POST':
            fields = ('title', 'requester', 'category', 'priority', 'description', 'status', 'technician', 'resolution_notes', 'asset_id') if is_ticket else ('asset_tag', 'device_type', 'manufacturer', 'model', 'serial_number', 'assigned_employee', 'status', 'purchase_date', 'assignment_date', 'notes')
            values = {field: request.form.get(field, '').strip() for field in fields}
            required = ('title', 'requester', 'description') if is_ticket else ('asset_tag', 'device_type', 'manufacturer', 'model')
            for field in required:
                if not values[field]:
                    errors.append(f'{field.replace("_", " ").capitalize()} is required.')
            for field, value in values.items():
                limit = 5000 if field in ('description', 'notes', 'resolution_notes') else 150
                if len(value) > limit:
                    errors.append(f'{field.replace("_", " ").capitalize()} must be at most {limit} characters.')
            choices = dict(status=TICKET_STATUSES if is_ticket else ASSET_STATUSES)
            if is_ticket:
                choices.update(category=CATEGORIES, priority=PRIORITIES)
            for field, allowed in choices.items():
                if values[field] not in allowed:
                    errors.append(f'Choose a valid {field}.')
            if is_ticket:
                if values['status'] in ('Resolved', 'Closed') and not values['resolution_notes']:
                    errors.append('Resolution notes are required for resolved or closed tickets.')
                asset_id = values['asset_id']
                if asset_id and (not asset_id.isdecimal() or len(asset_id) > 10 or not get_db().execute('SELECT id FROM assets WHERE id = ?', (asset_id,)).fetchone()):
                    errors.append('Choose an existing asset.')
                values['asset_id'] = asset_id or None
            else:
                values['serial_number'] = values['serial_number'] or None
                for field in ('purchase_date', 'assignment_date'):
                    if values[field]:
                        try:
                            date.fromisoformat(values[field])
                        except ValueError:
                            errors.append(f'{field.replace("_", " ").capitalize()} must be a valid date.')
                if values['status'] == 'Assigned' and (not values['assigned_employee'] or not values['assignment_date']):
                    errors.append('Assigned assets need an employee and assignment date.')
                if values['status'] in ('Available', 'Retired') and (values['assigned_employee'] or values['assignment_date']):
                    errors.append('Clear the employee and assignment date for available or retired assets.')
                if values['purchase_date'] and values['assignment_date'] and values['assignment_date'] < values['purchase_date']:
                    errors.append('Assignment date cannot be before purchase date.')
            if not errors:
                db = get_db()
                try:
                    with db:
                        values['updated_at'] = now()
                        if record_id:
                            assignments = ', '.join(f'{field} = ?' for field in values)
                            db.execute(f'UPDATE {kind} SET {assignments} WHERE id = ?', [*values.values(), record_id])
                        else:
                            values['created_at'] = values['updated_at']
                            columns = ', '.join(values)
                            markers = ', '.join('?' for _ in values)
                            record_id = db.execute(f'INSERT INTO {kind} ({columns}) VALUES ({markers})', list(values.values())).lastrowid
                        label = f'HD-{record_id:04d}' if is_ticket else values['asset_tag']
                        action = 'Updated' if existing else 'Created'
                        message = f'{action} {label} · {values["status"]}'
                        if existing and existing['status'] != values['status']:
                            message = f'{label}: {existing["status"]} → {values["status"]}'
                        db.execute('INSERT INTO activity (entity_type, entity_id, message, created_at) VALUES (?, ?, ?, ?)', (singular, record_id, message, now()))
                except sqlite3.IntegrityError:
                    errors.append('Asset tag or serial number already exists, or a related record is invalid.')
                else:
                    flash(f'{singular.capitalize()} saved.', 'success')
                    return redirect(url_for(f'{singular}_detail', record_id=record_id))
        asset_options = get_db().execute('SELECT id, asset_tag, model FROM assets ORDER BY asset_tag').fetchall() if is_ticket else []
        return render_template(f'{singular}_form.html', values=values, errors=errors, editing=bool(existing), asset_options=asset_options), 422 if errors else 200

    @app.route('/tickets/new', methods=['GET', 'POST'])
    def ticket_new():
        return save('tickets')

    @app.route('/tickets/<int:record_id>/edit', methods=['GET', 'POST'])
    def ticket_edit(record_id):
        return save('tickets', record_id)

    @app.route('/assets/new', methods=['GET', 'POST'])
    def asset_new():
        return save('assets')

    @app.route('/assets/<int:record_id>/edit', methods=['GET', 'POST'])
    def asset_edit(record_id):
        return save('assets', record_id)

    @app.errorhandler(404)
    @app.errorhandler(400)
    @app.errorhandler(413)
    def friendly_error(error):
        return render_template('error.html', error=error), error.code

    return app


def like_pattern(value):
    """Make LIKE a literal substring search, even for percent and underscore."""
    return '%' + value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'


app = create_app()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.environ.get('PORT', '5057')), debug=False)
