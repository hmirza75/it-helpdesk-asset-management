import re
import sqlite3
import tempfile
import unittest
from pathlib import Path
from app import create_app
from db import get_db, init_db
from seed import seed_demo


class HelpdeskTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app({'TESTING': True, 'SECRET_KEY': 'test-only', 'DATABASE': str(Path(self.temp.name) / 'test.sqlite')})
        self.client = self.app.test_client()
        with self.app.app_context():
            init_db()
        self.client.get('/')
        with self.client.session_transaction() as session:
            self.token = session['csrf_token']

    def tearDown(self):
        self.temp.cleanup()

    def post(self, url, data):
        return self.client.post(url, data={**data, 'csrf_token': self.token})

    def ticket(self, **changes):
        return dict(title='VPN login error', requester='Test Requester', category='Network', priority='High', description='Connection fails after reconnect.', status='Open', technician='Test Technician', resolution_notes='', asset_id='', **{}) | changes

    def asset(self, **changes):
        return dict(asset_tag='TEST-LT-001', device_type='Laptop', manufacturer='Dell', model='Test model', serial_number='TEST-SN-1', assigned_employee='', status='Available', purchase_date='2026-01-01', assignment_date='', notes='Test-only asset') | changes

    def row(self, table, record_id=1):
        with self.app.app_context():
            return dict(get_db().execute(f'SELECT * FROM {table} WHERE id=?', (record_id,)).fetchone())

    def metrics(self):
        html = self.client.get('/').get_data(as_text=True)
        return {key: int(value) for key, value in re.findall(r'data-metric="([^"]+)">(\d+)', html)}

    def test_complete_support_workflow_and_counts(self):
        self.assertEqual(self.post('/assets/new', self.asset()).status_code, 302)
        self.assertEqual(self.metrics()['assets-Available'], 1)
        assigned = self.asset(status='Assigned', assigned_employee='Test Requester', assignment_date='2026-02-01')
        self.assertEqual(self.post('/assets/1/edit', assigned).status_code, 302)
        self.assertEqual(self.row('assets')['assigned_employee'], 'Test Requester')
        self.assertEqual(self.metrics()['assets-Assigned'], 1)
        self.assertEqual(self.metrics()['assets-Available'], 0)
        ticket = self.ticket(asset_id='1')
        self.assertEqual(self.post('/tickets/new', ticket).status_code, 302)
        self.assertEqual(self.row('tickets')['asset_id'], 1)
        self.assertIn(b'TEST-LT-001', self.client.get('/tickets/1').data)
        self.assertIn(b'VPN login error', self.client.get('/assets/1').data)
        self.assertEqual(self.metrics()['tickets-Open'], 1)
        created = self.row('tickets')['created_at']
        ticket.update(status='In Progress', description='Reproduced; checking client settings.')
        self.assertEqual(self.post('/tickets/1/edit', ticket).status_code, 302)
        self.assertEqual(self.metrics()['tickets-In Progress'], 1)
        self.assertEqual(self.metrics()['tickets-Open'], 0)
        ticket.update(status='Resolved', resolution_notes='Corrected the test VPN profile and verified reconnect.')
        self.assertEqual(self.post('/tickets/1/edit', ticket).status_code, 302)
        saved = self.row('tickets')
        self.assertEqual(saved['created_at'], created)
        self.assertGreaterEqual(saved['updated_at'], created)
        self.assertEqual(self.metrics()['tickets-Resolved'], 1)
        self.assertEqual(self.metrics()['tickets-In Progress'], 0)
        self.assertEqual(self.metrics()['tickets-total'], 1)
        self.assertEqual(self.metrics()['assets-total'], 1)
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT COUNT(*) FROM activity').fetchone()[0], 5)

    def test_filters_and_literal_search(self):
        with self.app.app_context():
            seed_demo()
        for field, value in [('status','In Progress'),('priority','High'),('category','Hardware'),('requester','Morgan'),('technician','Alex')]:
            response = self.client.get('/tickets', query_string={field: value})
            self.assertIn(b'External monitor disconnects', response.data)
            self.assertNotIn(b'How to request software access', response.data)
        response = self.client.get('/tickets', query_string=dict(status='In Progress',priority='High',category='Hardware',requester='Morgan',technician='Alex'))
        self.assertIn(b'1 results', response.data)
        self.assertIn(b'External monitor disconnects', response.data)
        for query in ['HD-0002','monitor disconnects','assigned USB-C']:
            self.assertIn(b'External monitor disconnects', self.client.get('/tickets', query_string={'q':query}).data)
        for query in ['%', '_', "' OR 1=1 --"]:
            self.assertIn(b'0 results', self.client.get('/tickets', query_string={'q':query}).data)
        for filters in [dict(status='Repair'),dict(device_type='Dock'),dict(assigned_employee='Morgan',status='Repair'),dict(q='DEMO-SN-104')]:
            self.assertIn(b'DEMO-DK-104', self.client.get('/assets', query_string=filters).data)
        self.assertIn(b'No assets found', self.client.get('/assets?q=not-a-record').data)

    def test_demo_counts_and_pages(self):
        with self.app.app_context():
            seed_demo()
        self.assertEqual(self.metrics(), {'tickets-total':8,'tickets-Open':2,'tickets-In Progress':2,'tickets-Resolved':2,'assets-total':6,'assets-Assigned':2,'assets-Available':2,'assets-Repair':1})
        with self.app.app_context():
            counts = dict(get_db().execute('SELECT priority,COUNT(*) FROM tickets GROUP BY priority'))
            self.assertEqual(counts, {'Critical':1,'High':3,'Low':2,'Medium':2})
        for url in ['/','/tickets','/assets','/tickets/1','/tickets/1/edit','/assets/1','/assets/1/edit','/tickets/new','/assets/new']:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertEqual(self.client.get('/tickets/999').status_code,404)
        self.assertEqual(self.client.get('/assets/999/edit').status_code,404)

    def test_resolution_validation_preserves_data(self):
        self.post('/tickets/new', self.ticket())
        response = self.post('/tickets/1/edit', self.ticket(status='Resolved'))
        self.assertEqual(response.status_code,422)
        self.assertIn(b'Resolution notes are required',response.data)
        self.assertEqual(self.row('tickets')['status'],'Open')
        self.assertEqual(self.post('/tickets/new',self.ticket(status='Closed')).status_code,422)

    def test_assignment_dates_and_duplicates(self):
        for changes in [dict(status='Assigned'),dict(purchase_date='bad'),dict(assignment_date='2025-01-01',assigned_employee='Someone',status='Assigned'),dict(assigned_employee='Someone'),dict(status='Unknown')]:
            self.assertEqual(self.post('/assets/new',self.asset(**changes)).status_code,422)
        self.assertEqual(self.post('/assets/new',self.asset()).status_code,302)
        self.assertEqual(self.post('/assets/new',self.asset(asset_tag='test-lt-001',serial_number='OTHER')).status_code,422)
        self.assertEqual(self.post('/assets/new',self.asset(asset_tag='OTHER')).status_code,422)
        for tag in ['BLANK-1','BLANK-2']:
            self.assertEqual(self.post('/assets/new',self.asset(asset_tag=tag,serial_number='')).status_code,302)

    def test_invalid_ticket_values_and_foreign_keys(self):
        for changes in [dict(title=' '),dict(priority='Urgent'),dict(category='Invalid'),dict(asset_id='999'),dict(asset_id='abc'),dict(asset_id='9'*100),dict(title='x'*151)]:
            self.assertEqual(self.post('/tickets/new', self.ticket(**changes)).status_code,422)
        with self.app.app_context():
            db = get_db()
            self.assertEqual(db.execute('PRAGMA foreign_keys').fetchone()[0],1)
        self.post('/assets/new',self.asset())
        self.post('/tickets/new',self.ticket(asset_id='1'))
        with self.app.app_context():
            with self.assertRaises(sqlite3.IntegrityError):
                get_db().execute('DELETE FROM assets WHERE id=1')

    def test_csrf_and_output_escaping(self):
        self.assertEqual(self.client.post('/tickets/new',data=self.ticket()).status_code,400)
        self.assertEqual(self.post('/tickets/new',self.ticket(title='<script>alert(1)</script>')).status_code,302)
        html = self.client.get('/tickets/1').data
        self.assertIn(b'&lt;script&gt;',html)
        self.assertNotIn(b'<script>alert',html)

    def test_cli_preserves_existing_data(self):
        runner = self.app.test_cli_runner()
        self.assertEqual(runner.invoke(args=['init-db']).exit_code,0)
        self.assertEqual(runner.invoke(args=['seed-demo']).exit_code,0)
        self.assertNotEqual(runner.invoke(args=['seed-demo']).exit_code,0)
        self.assertEqual(runner.invoke(args=['init-db']).exit_code,0)
        self.assertEqual(self.metrics()['tickets-total'],8)


if __name__ == '__main__':
    unittest.main()
