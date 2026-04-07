"""
Experiment 12 — Master Test Plan: Test Case Design (Phase 1)
Test suite covering TC-01 through TC-23 for the Personal Finance Expense Tracker.
"""

import io
import json
import os
import sqlite3
from unittest.mock import patch

import pytest
import requests

os.environ.setdefault('SECRET_KEY', 'test-secret-key')

import app as flask_app  # noqa: E402  (import after env setup)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_path(tmp_path):
    """Return a path to a fresh, empty SQLite database file."""
    return str(tmp_path / 'test_finance.db')


@pytest.fixture
def client(db_path, monkeypatch):
    """Flask test client backed by an isolated temporary database."""
    monkeypatch.setattr(flask_app, 'DATABASE', db_path)
    flask_app.app.config['TESTING'] = True
    flask_app.app.config['SECRET_KEY'] = 'test-secret-key'
    flask_app.init_db()
    with flask_app.app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _register(client, username='testuser', email='test@example.com',
              phone='9999999999', password='password123'):
    return client.post('/register', data={
        'username': username,
        'email': email,
        'phone': phone,
        'password': password,
    }, follow_redirects=True)


def _login(client, username='testuser', password='password123'):
    return client.post('/login', data={
        'username': username,
        'password': password,
    }, follow_redirects=True)


def _add_transaction(client, amount='100.00', category='Food',
                     date='2026-04-01', payment_method='UPI', notes='Test'):
    return client.post('/add_transaction', data={
        'amount': amount,
        'category': category,
        'date': date,
        'payment_method': payment_method,
        'notes': notes,
    }, follow_redirects=True)


def _fake_jpeg():
    """Return a minimal JPEG byte-stream for upload tests."""
    return io.BytesIO(b'\xff\xd8\xff\xe0' + b'\x00' * 100)


# ===========================================================================
# TC-01 – TC-06 : Authentication
# ===========================================================================

class TestAuthentication:

    def test_tc01_register_unique_user(self, client, db_path):
        """TC-01: Register with unique credentials → account created, flash 'Registration successful'."""
        resp = _register(client)
        assert resp.status_code == 200
        assert b'Registration successful' in resp.data

        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT username FROM users WHERE username='testuser'").fetchone()
        conn.close()
        assert row is not None, "User row was not inserted into the database."

    def test_tc02_register_duplicate_username(self, client, db_path):
        """TC-02: Register with existing username → flash error, no duplicate row inserted."""
        _register(client)
        count_before = sqlite3.connect(db_path).execute(
            "SELECT COUNT(*) FROM users WHERE username='testuser'"
        ).fetchone()[0]

        resp = client.post('/register', data={
            'username': 'testuser',
            'email': 'other@example.com',
            'phone': '8888888888',
            'password': 'otherpass',
        }, follow_redirects=True)

        assert b'Username already exists' in resp.data
        count_after = sqlite3.connect(db_path).execute(
            "SELECT COUNT(*) FROM users WHERE username='testuser'"
        ).fetchone()[0]
        assert count_after == count_before, "Duplicate user row was inserted."

    def test_tc03_login_correct_credentials(self, client):
        """TC-03: Login with correct credentials → session created, username visible in response."""
        _register(client)
        resp = _login(client)
        assert resp.status_code == 200
        assert b'Login successful' in resp.data
        assert b'testuser' in resp.data

        with client.session_transaction() as sess:
            assert 'user_id' in sess
            assert sess['username'] == 'testuser'

    def test_tc04_login_wrong_password(self, client):
        """TC-04: Login with wrong password → flash error, no session created."""
        _register(client)
        resp = client.post('/login', data={
            'username': 'testuser',
            'password': 'wrongpassword',
        }, follow_redirects=True)

        assert b'Invalid username or password' in resp.data
        with client.session_transaction() as sess:
            assert 'user_id' not in sess

    def test_tc05_access_transactions_without_login(self, client):
        """TC-05: Access /transactions without login → redirect to /login."""
        resp = client.get('/transactions', follow_redirects=False)
        assert resp.status_code == 302
        assert '/login' in resp.headers['Location']

    def test_tc06_logout_clears_session(self, client):
        """TC-06: Logout → session cleared, redirect to /login with success flash."""
        _register(client)
        _login(client)

        resp = client.get('/logout', follow_redirects=True)
        assert b'logged out' in resp.data.lower() or b'You have been logged out' in resp.data

        with client.session_transaction() as sess:
            assert 'user_id' not in sess
            assert 'username' not in sess


# ===========================================================================
# TC-07 – TC-10 : Transaction Management
# ===========================================================================

class TestTransactions:

    def test_tc07_add_valid_transaction(self, client, db_path):
        """TC-07: Add transaction with valid data → row inserted into DB."""
        _register(client)
        _login(client)
        _add_transaction(client, amount='250.00', category='Food',
                         date='2026-04-01', payment_method='UPI', notes='Lunch')

        row = sqlite3.connect(db_path).execute(
            "SELECT amount, category FROM transactions WHERE category='Food'"
        ).fetchone()
        assert row is not None
        assert row[0] == 250.0

    def test_tc08_add_transaction_zero_amount(self, client, db_path):
        """TC-08: Add transaction with amount=0 → flash error, no row inserted."""
        _register(client)
        _login(client)
        resp = _add_transaction(client, amount='0')

        assert b'Amount must be greater than zero' in resp.data
        count = sqlite3.connect(db_path).execute(
            "SELECT COUNT(*) FROM transactions"
        ).fetchone()[0]
        assert count == 0, "Transaction was inserted despite zero amount."

    def test_tc09_delete_transaction(self, client, db_path):
        """TC-09: Delete a transaction → row removed from DB, flash 'Transaction deleted'."""
        _register(client)
        _login(client)
        _add_transaction(client, amount='100.00')

        txn_id = sqlite3.connect(db_path).execute(
            "SELECT id FROM transactions LIMIT 1"
        ).fetchone()[0]

        resp = client.post(f'/delete_transaction/{txn_id}', follow_redirects=True)
        assert b'Transaction deleted' in resp.data

        row = sqlite3.connect(db_path).execute(
            "SELECT id FROM transactions WHERE id=?", (txn_id,)
        ).fetchone()
        assert row is None, "Transaction row was not deleted."

    def test_tc10_empty_transactions_message(self, client):
        """TC-10: View transactions with no data → 'No transactions yet' message displayed."""
        _register(client)
        _login(client)
        resp = client.get('/transactions')
        assert resp.status_code == 200
        assert b'No transactions yet' in resp.data


# ===========================================================================
# TC-11 – TC-12 : Dashboard
# ===========================================================================

class TestDashboard:

    def test_tc11_upi_cash_totals(self, client):
        """TC-11: Dashboard stat cards show correct UPI and Cash totals."""
        _register(client)
        _login(client)
        _add_transaction(client, amount='500.00', payment_method='UPI')
        _add_transaction(client, amount='300.00', payment_method='UPI')
        _add_transaction(client, amount='200.00', payment_method='Cash')

        resp = client.get('/')
        assert resp.status_code == 200
        # UPI total = 800, Cash total = 200
        assert b'800' in resp.data
        assert b'200' in resp.data

    def test_tc12_chart_endpoints_json_structure(self, client):
        """TC-12: /daily_spending_data and /monthly_spending_data return {labels, amounts} JSON."""
        _register(client)
        _login(client)
        _add_transaction(client, amount='100.00', date='2026-04-01')
        _add_transaction(client, amount='200.00', date='2026-04-05')

        for endpoint in ['/daily_spending_data', '/monthly_spending_data']:
            resp = client.get(endpoint)
            assert resp.status_code == 200, f"{endpoint} returned {resp.status_code}"
            data = json.loads(resp.data)
            assert 'labels' in data, f"'labels' key missing from {endpoint}"
            assert 'amounts' in data, f"'amounts' key missing from {endpoint}"
            assert isinstance(data['labels'], list)
            assert isinstance(data['amounts'], list)
            assert len(data['labels']) == len(data['amounts']), \
                "labels and amounts lists have different lengths"


# ===========================================================================
# TC-13 – TC-14 : Statistics
# ===========================================================================

class TestStatistics:

    def test_tc13_statistics_renders_multiple_categories(self, client):
        """TC-13: Statistics page renders correctly with 3+ expense categories."""
        _register(client)
        _login(client)
        for cat in ['Food', 'Travel expenses', 'Entertainment']:
            _add_transaction(client, amount='100.00', category=cat)

        resp = client.get('/statistics')
        assert resp.status_code == 200
        assert b'Food' in resp.data
        assert b'Travel expenses' in resp.data
        assert b'Entertainment' in resp.data

    def test_tc14_total_expenses_matches_db_sum(self, client, db_path):
        """TC-14: Total expenses shown on statistics page equals SUM(amount) from DB."""
        _register(client)
        _login(client)
        _add_transaction(client, amount='150.00', category='Food')
        _add_transaction(client, amount='250.00', category='Travel expenses')

        db_total = sqlite3.connect(db_path).execute(
            "SELECT SUM(amount) FROM transactions"
        ).fetchone()[0]

        resp = client.get('/statistics')
        assert resp.status_code == 200
        # The rendered page must contain the exact total (400.0 or 400)
        assert str(int(db_total)).encode() in resp.data or \
               f'{db_total:.2f}'.encode() in resp.data, \
               f"Expected total {db_total} not found in statistics page."


# ===========================================================================
# TC-15 – TC-17 : Recurring Payments
# ===========================================================================

class TestRecurringPayments:

    def test_tc15_add_monthly_recurring(self, client, db_path):
        """TC-15: Add monthly recurring payment → row in recurring_transactions table."""
        _register(client)
        _login(client)
        resp = client.post('/add_recurring', data={
            'description': 'Netflix',
            'category': 'Subscriptions',
            'amount': '649',
            'payment_method': 'UPI',
            'frequency': 'monthly',
            'start_date': '2026-05-01',
        }, follow_redirects=True)
        assert resp.status_code == 200

        row = sqlite3.connect(db_path).execute(
            "SELECT description, amount FROM recurring_transactions WHERE description='Netflix'"
        ).fetchone()
        assert row is not None, "Recurring payment row not found in database."
        assert row[1] == 649.0

    def test_tc16_recurring_auto_generates_transaction_on_due_date(self, client, db_path):
        """TC-16: Visiting /transactions when next_due_date ≤ today auto-inserts transaction."""
        _register(client)
        _login(client)
        # Use a past start_date so it is immediately due
        client.post('/add_recurring', data={
            'description': 'Rent',
            'category': 'Rent',
            'amount': '5000',
            'payment_method': 'UPI',
            'frequency': 'monthly',
            'start_date': '2026-01-01',
        }, follow_redirects=True)

        # Visiting /transactions triggers process_due_recurring
        resp = client.get('/transactions')
        assert resp.status_code == 200

        conn = sqlite3.connect(db_path)
        count = conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE description='Rent'"
        ).fetchone()[0]
        new_due = conn.execute(
            "SELECT next_due_date FROM recurring_transactions WHERE description='Rent'"
        ).fetchone()[0]
        conn.close()

        assert count > 0, "Auto-transaction was not generated for overdue recurring payment."
        assert new_due > '2026-01-01', "next_due_date was not advanced after auto-generation."

    def test_tc17_pause_recurring_stops_transaction_generation(self, client, db_path):
        """TC-17: Pausing a recurring payment sets is_active=0; no new transactions generated."""
        _register(client)
        _login(client)
        # Future date so no auto-generation yet
        client.post('/add_recurring', data={
            'description': 'Spotify',
            'category': 'Subscriptions',
            'amount': '119',
            'payment_method': 'UPI',
            'frequency': 'monthly',
            'start_date': '2027-01-01',
        }, follow_redirects=True)

        rec_id = sqlite3.connect(db_path).execute(
            "SELECT id FROM recurring_transactions WHERE description='Spotify'"
        ).fetchone()[0]

        # Toggle (pause)
        client.post(f'/toggle_recurring/{rec_id}', follow_redirects=True)

        is_active = sqlite3.connect(db_path).execute(
            "SELECT is_active FROM recurring_transactions WHERE id=?", (rec_id,)
        ).fetchone()[0]
        assert is_active == 0, "Recurring payment is_active was not set to 0 after pause."

        # Visiting /transactions must not generate transactions for a paused entry
        client.get('/transactions')
        count = sqlite3.connect(db_path).execute(
            "SELECT COUNT(*) FROM transactions WHERE description='Spotify'"
        ).fetchone()[0]
        assert count == 0, "Paused recurring payment still generated a transaction."


# ===========================================================================
# TC-18 – TC-19 : Receipt OCR
# ===========================================================================

class TestReceiptOCR:

    def test_tc18_upload_receipt_ollama_running(self, client):
        """TC-18: Upload receipt (Ollama running) → returns parsed JSON with transaction fields."""
        _register(client)
        _login(client)

        mock_response = json.dumps({
            'amount': 450.00,
            'date': '2026-04-01',
            'category': 'Food',
            'description': 'Lunch at restaurant',
            'payment_method': 'UPI',
        })

        with patch('app.ollama_vision', return_value=mock_response):
            resp = client.post('/upload_receipt', data={
                'receipt': (_fake_jpeg(), 'receipt.jpg', 'image/jpeg'),
            }, content_type='multipart/form-data')

        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data.get('amount') == 450.0
        assert data.get('category') == 'Food'
        assert data.get('payment_method') == 'UPI'

    def test_tc19_upload_receipt_ollama_offline(self, client):
        """TC-19: Upload receipt when Ollama is offline → 503 with error about 'ollama serve'."""
        _register(client)
        _login(client)

        with patch('app.ollama_vision',
                   side_effect=requests.exceptions.ConnectionError("Connection refused")):
            resp = client.post('/upload_receipt', data={
                'receipt': (_fake_jpeg(), 'receipt.jpg', 'image/jpeg'),
            }, content_type='multipart/form-data')

        assert resp.status_code == 503
        data = json.loads(resp.data)
        assert 'Ollama is not running' in data['error']
        assert 'ollama serve' in data['error']


# ===========================================================================
# TC-20 – TC-21 : AI Chatbot
# ===========================================================================

class TestChatbot:

    def test_tc20_chatbot_replies_with_spending_context(self, client):
        """TC-20: Chatbot with transactions present replies with category-specific amount."""
        _register(client)
        _login(client)
        _add_transaction(client, amount='500.00', category='Food')

        mock_reply = 'You spent ₹500.00 on Food this month.'
        with patch('app.ollama_chat', return_value=mock_reply):
            resp = client.post('/chatbot',
                               data=json.dumps({'message': 'How much did I spend on Food?'}),
                               content_type='application/json')

        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert 'response' in data
        assert data['response'] == mock_reply

    def test_tc21_chatbot_ollama_offline(self, client):
        """TC-21: Chatbot when Ollama is offline → response contains 'Ollama is not running'."""
        _register(client)
        _login(client)

        with patch('app.requests.post',
                   side_effect=requests.exceptions.ConnectionError("Connection refused")):
            resp = client.post('/chatbot',
                               data=json.dumps({'message': 'Hello'}),
                               content_type='application/json')

        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert 'Ollama is not running' in data['response']
        assert 'ollama serve' in data['response']


# ===========================================================================
# TC-22 : CSV Export
# ===========================================================================

class TestCSVExport:

    def test_tc22_export_csv_downloads_correct_file(self, client):
        """TC-22: GET /export_csv → downloads transactions.csv with correct headers and rows."""
        _register(client)
        _login(client)
        for i in range(3):
            _add_transaction(client, amount=str(100 * (i + 1)),
                             category='Food', date=f'2026-04-0{i + 1}',
                             payment_method='UPI', notes=f'Item {i}')

        resp = client.get('/export_csv')
        assert resp.status_code == 200, (
            "GET /export_csv returned non-200. "
            "The /export_csv route may not be implemented yet."
        )

        content_type = resp.content_type.lower()
        disposition = resp.headers.get('Content-Disposition', '')
        assert 'text/csv' in content_type or 'attachment' in disposition, \
            "Response is not a CSV file attachment."

        content = resp.data.decode('utf-8')
        for header in ('Date', 'Category', 'Amount', 'Payment Method', 'Notes'):
            assert header.lower() in content.lower(), \
                f"Expected CSV header '{header}' not found in export."
        assert content.count('\n') >= 4, "CSV should contain at least 3 data rows + header."


# ===========================================================================
# TC-23 : Security — Cross-User Data Isolation
# ===========================================================================

class TestSecurity:

    def test_tc23_cannot_delete_another_users_transaction(self, client, db_path):
        """TC-23: User2 cannot delete User1's transaction — DELETE must be scoped to session user_id."""
        # Register and add a transaction as user1
        _register(client, username='user1', email='u1@example.com',
                  phone='1111111111', password='pass1')
        _login(client, username='user1', password='pass1')
        _add_transaction(client, amount='999.00', category='Rent')

        user1_txn_id = sqlite3.connect(db_path).execute(
            "SELECT id FROM transactions WHERE amount=999.0 LIMIT 1"
        ).fetchone()[0]

        # Switch to user2
        client.get('/logout', follow_redirects=True)
        _register(client, username='user2', email='u2@example.com',
                  phone='2222222222', password='pass2')
        _login(client, username='user2', password='pass2')

        # Attempt to delete user1's transaction as user2
        client.post(f'/delete_transaction/{user1_txn_id}', follow_redirects=True)

        row = sqlite3.connect(db_path).execute(
            "SELECT id FROM transactions WHERE id=?", (user1_txn_id,)
        ).fetchone()
        assert row is not None, (
            "SECURITY BREACH — TC-23 FAILED: user2 was able to delete user1's transaction. "
            "The DELETE query in delete_transaction() must be scoped with "
            "'AND user_id = <session user_id>'."
        )
