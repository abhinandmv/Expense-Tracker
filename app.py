from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime, timedelta, date
import calendar
import sqlite3
import logging
import requests
import base64
import json
import re
from dotenv import load_dotenv
import os

load_dotenv()


logging.basicConfig(level=logging.DEBUG)

# --- Ollama configuration ---
OLLAMA_BASE_URL = "http://localhost:11434"
CHAT_MODEL      = "llama3.2"   # change to any model you have pulled
VISION_MODEL    = "llava"      # for receipt parsing; needs `ollama pull llava`

# --- Flask App Setup ---
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

# --- SQLite Database Setup ---
DATABASE = 'finance_tracker.db'

CATEGORIES = [
    "Entertainment", "Food", "Utilities", "Education",
    "Travel expenses", "Gifts", "Rent", "Subscriptions"
]


def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email    TEXT NOT NULL,
            phone    TEXT NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id        INTEGER NOT NULL,
            amount         REAL    NOT NULL,
            category       TEXT    NOT NULL,
            date           TEXT    NOT NULL,
            description    TEXT,
            payment_method TEXT    NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS recurring_transactions (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id        INTEGER NOT NULL,
            amount         REAL    NOT NULL,
            category       TEXT    NOT NULL,
            description    TEXT,
            payment_method TEXT    NOT NULL,
            frequency      TEXT    NOT NULL,
            next_due_date  TEXT    NOT NULL,
            is_active      INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    conn.commit()
    conn.close()


def _advance_date(d, frequency):
    """Return d advanced by one frequency period."""
    if frequency == 'weekly':
        return d + timedelta(weeks=1)
    elif frequency == 'monthly':
        month = d.month + 1
        year = d.year
        if month > 12:
            month = 1
            year += 1
        max_day = calendar.monthrange(year, month)[1]
        return d.replace(year=year, month=month, day=min(d.day, max_day))
    elif frequency == 'yearly':
        max_day = calendar.monthrange(d.year + 1, d.month)[1]
        return d.replace(year=d.year + 1, day=min(d.day, max_day))
    return d


def process_due_recurring(user_id):
    """Auto-generate transactions for any recurring payments that are due."""
    today = date.today()
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute(
        "SELECT id, amount, category, description, payment_method, frequency, next_due_date "
        "FROM recurring_transactions WHERE user_id = ? AND is_active = 1 AND next_due_date <= ?",
        (user_id, today.strftime('%Y-%m-%d'))
    )
    due = c.fetchall()
    for rec in due:
        rec_id, amount, category, description, payment_method, frequency, next_due_str = rec
        next_due = datetime.strptime(next_due_str, '%Y-%m-%d').date()
        while next_due <= today:
            c.execute(
                "INSERT INTO transactions (user_id, amount, category, date, description, payment_method) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, amount, category, next_due.strftime('%Y-%m-%d'), description, payment_method)
            )
            next_due = _advance_date(next_due, frequency)
        c.execute(
            "UPDATE recurring_transactions SET next_due_date = ? WHERE id = ?",
            (next_due.strftime('%Y-%m-%d'), rec_id)
        )
    conn.commit()
    conn.close()


init_db()

# --- Budget Analyzer System Prompt ---
BUDGET_PROMPT = (
    "You are a friendly Budget Analyzer AI. "
    "Help users analyze spending, answer questions about their expenses, "
    "and give practical, actionable money-saving suggestions based on their transaction data. "
    "Be concise, positive, and focus on financial well-being. "
    "If asked for savings tips, use the top spending categories provided."
)


def get_top_spending_categories(user_id, limit=3):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute(
        "SELECT category, SUM(amount) FROM transactions "
        "WHERE user_id = ? GROUP BY category ORDER BY SUM(amount) DESC LIMIT ?",
        (user_id, limit)
    )
    rows = c.fetchall()
    conn.close()
    return rows


def ollama_chat(prompt: str) -> str:
    """Send a prompt to Ollama chat endpoint and return the response text."""
    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": CHAT_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False
            },
            timeout=60
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]
    except requests.exceptions.ConnectionError:
        return "Ollama is not running. Please start it with `ollama serve`."
    except Exception as e:
        logging.error(f"Ollama chat error: {e}")
        return "Sorry, the AI is unavailable right now."


def ollama_vision(image_b64: str, prompt: str) -> str:
    """Send an image + prompt to Ollama generate endpoint (vision model)."""
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": VISION_MODEL,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False
        },
        timeout=120
    )
    resp.raise_for_status()
    return resp.json()["response"]


# ============================================================
# Routes
# ============================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("SELECT id, username FROM users WHERE username = ? AND password = ?",
                  (username, password))
        user = c.fetchone()
        conn.close()
        if user:
            session['user_id']  = user[0]
            session['username'] = user[1]
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        flash('Invalid username or password.', 'error')
    return render_template('login.html')


@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT * FROM transactions WHERE user_id = ?", (user_id,))
    txns = c.fetchall()
    conn.close()
    total_amount = sum(t[2] for t in txns)
    total_upi    = sum(t[2] for t in txns if t[6] == 'UPI')
    total_cash   = sum(t[2] for t in txns if t[6] == 'Cash')
    return render_template('index.html',
                           username=session['username'],
                           total_amount=round(total_amount, 2),
                           total_upi=round(total_upi, 2),
                           total_cash=round(total_cash, 2))


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email    = request.form['email']
        phone    = request.form['phone']
        password = request.form['password']
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE username = ?", (username,))
        if c.fetchone():
            flash('Username already exists.', 'error')
        else:
            c.execute("INSERT INTO users (username, email, phone, password) VALUES (?, ?, ?, ?)",
                      (username, email, phone, password))
            conn.commit()
            flash('Registration successful! Please log in.', 'success')
        conn.close()
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/transactions')
def transactions():
    if 'username' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    process_due_recurring(user_id)
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT * FROM transactions WHERE user_id = ? ORDER BY date DESC", (user_id,))
    txns = c.fetchall()
    c.execute("SELECT * FROM recurring_transactions WHERE user_id = ? ORDER BY next_due_date ASC", (user_id,))
    recurring = c.fetchall()
    conn.close()
    return render_template('transaction.html', transactions=txns, recurring=recurring, username=session['username'])


@app.route('/add_transaction', methods=['POST'])
def add_transaction():
    if 'username' not in session:
        return redirect(url_for('login'))
    user_id        = session['user_id']
    date           = request.form['date']
    category       = request.form['category']
    amount         = float(request.form['amount'])
    payment_method = request.form['payment_method']
    description    = request.form.get('notes', '')

    if amount <= 0:
        flash('Amount must be greater than zero.', 'error')
        return redirect(url_for('transactions'))

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO transactions (user_id, amount, category, date, description, payment_method) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, amount, category, date, description, payment_method)
    )
    conn.commit()
    conn.close()
    return redirect(url_for('transactions'))


@app.route('/delete_transaction/<int:transaction_id>', methods=['POST'])
def delete_transaction(transaction_id):
    if 'username' not in session:
        flash('You must be logged in to do that.', 'error')
        return redirect(url_for('login'))
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
    conn.commit()
    conn.close()
    flash('Transaction deleted.', 'success')
    return redirect(url_for('transactions'))


@app.route('/daily_spending_data')
def daily_spending_data():
    if 'username' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT date, SUM(amount) FROM transactions WHERE user_id = ? "
              "GROUP BY date ORDER BY date", (user_id,))
    data = c.fetchall()
    conn.close()
    return jsonify({'labels': [r[0] for r in data], 'amounts': [r[1] for r in data]})


@app.route('/monthly_spending_data')
def monthly_spending_data():
    if 'username' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT strftime('%Y-%m', date), SUM(amount) FROM transactions "
              "WHERE user_id = ? GROUP BY strftime('%Y-%m', date) ORDER BY 1", (user_id,))
    data = c.fetchall()
    conn.close()
    labels  = [datetime.strptime(r[0], '%Y-%m').strftime('%b %Y') for r in data]
    amounts = [r[1] for r in data]
    return jsonify({'labels': labels, 'amounts': amounts})


@app.route('/statistics')
def statistics():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT SUM(amount) FROM transactions WHERE user_id = ?", (user_id,))
    total_expenses = c.fetchone()[0] or 0

    c.execute("SELECT category, SUM(amount) FROM transactions WHERE user_id = ? "
              "GROUP BY category ORDER BY SUM(amount) DESC", (user_id,))
    expense_by_category = dict(c.fetchall())
    conn.close()

    return render_template('statistics.html',
                           username=session['username'],
                           total_expenses=round(total_expenses, 2),
                           expense_by_category=expense_by_category)


# ============================================================
# AI Chatbot (Ollama)
# ============================================================

@app.route("/chatbot", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message", "").strip()
    if not user_message:
        return jsonify({"response": "Please type a message."})

    user_id = session.get('user_id')
    context = ""
    if user_id:
        top = get_top_spending_categories(user_id)
        if top:
            context = "User's top spending categories: " + \
                      ", ".join(f"{cat} ₹{amt:.2f}" for cat, amt in top) + ". "
        else:
            context = "User has no transactions yet. "

    prompt = f"{BUDGET_PROMPT}\n\n{context}\nUser: {user_message}"
    reply  = ollama_chat(prompt)
    return jsonify({"response": reply})


# ============================================================
# Receipt Upload & AI Parsing (Ollama Vision)
# ============================================================

RECEIPT_PROMPT = """You are an expense extractor. Analyze the receipt image and return ONLY a JSON object with these fields:
- amount: number (total amount paid, e.g. 450.00)
- date: string (in YYYY-MM-DD format, use today if not visible)
- category: string (one of: Entertainment, Food, Utilities, Education, Travel expenses, Gifts, Rent, Subscriptions)
- description: string (short description of what was purchased, max 60 chars)
- payment_method: string (UPI or Cash; default to UPI if unknown)

Example: {"amount": 250.00, "date": "2026-03-26", "category": "Food", "description": "Lunch at restaurant", "payment_method": "UPI"}

Return ONLY the JSON, no explanation."""


@app.route('/upload_receipt', methods=['POST'])
def upload_receipt():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    if 'receipt' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['receipt']
    if not file or file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    allowed = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
    if file.mimetype not in allowed:
        return jsonify({'error': 'Please upload a JPG, PNG, or WebP image'}), 400

    image_bytes  = file.read()
    image_b64    = base64.b64encode(image_bytes).decode('utf-8')

    try:
        raw = ollama_vision(image_b64, RECEIPT_PROMPT)
        logging.debug(f"Ollama vision raw: {raw}")
    except requests.exceptions.ConnectionError:
        return jsonify({'error': 'Ollama is not running. Start it with `ollama serve`.'}), 503
    except Exception as e:
        logging.error(f"Vision error: {e}")
        return jsonify({'error': 'AI processing failed. Make sure the llava model is installed.'}), 500

    # Extract JSON from response (model may wrap it in markdown code blocks)
    json_match = re.search(r'\{[^{}]+\}', raw, re.DOTALL)
    if not json_match:
        return jsonify({'error': 'Could not parse receipt. Try a clearer image.'}), 422

    try:
        parsed = json.loads(json_match.group())
    except json.JSONDecodeError:
        return jsonify({'error': 'Malformed JSON from AI. Try again.'}), 422

    # Sanitize / validate
    try:
        parsed['amount'] = round(float(parsed.get('amount', 0)), 2)
    except (ValueError, TypeError):
        parsed['amount'] = 0.0

    if parsed.get('category') not in CATEGORIES:
        parsed['category'] = 'Food'

    if parsed.get('payment_method') not in ('UPI', 'Cash'):
        parsed['payment_method'] = 'UPI'

    # Validate date format
    try:
        datetime.strptime(parsed.get('date', ''), '%Y-%m-%d')
    except ValueError:
        parsed['date'] = datetime.today().strftime('%Y-%m-%d')

    parsed['description'] = str(parsed.get('description', ''))[:100]

    return jsonify(parsed)


@app.route('/add_recurring', methods=['POST'])
def add_recurring():
    if 'username' not in session:
        return redirect(url_for('login'))
    user_id        = session['user_id']
    amount         = float(request.form['amount'])
    category       = request.form['category']
    description    = request.form.get('description', '')
    payment_method = request.form['payment_method']
    frequency      = request.form['frequency']
    start_date     = request.form['start_date']

    if amount <= 0:
        flash('Amount must be greater than zero.', 'error')
        return redirect(url_for('transactions'))
    if frequency not in ('weekly', 'monthly', 'yearly'):
        flash('Invalid frequency.', 'error')
        return redirect(url_for('transactions'))

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO recurring_transactions "
        "(user_id, amount, category, description, payment_method, frequency, next_due_date, is_active) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
        (user_id, amount, category, description, payment_method, frequency, start_date)
    )
    conn.commit()
    conn.close()
    flash('Recurring payment added.', 'success')
    return redirect(url_for('transactions'))


@app.route('/delete_recurring/<int:rec_id>', methods=['POST'])
def delete_recurring(rec_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("DELETE FROM recurring_transactions WHERE id = ? AND user_id = ?", (rec_id, user_id))
    conn.commit()
    conn.close()
    flash('Recurring payment deleted.', 'success')
    return redirect(url_for('transactions'))


@app.route('/toggle_recurring/<int:rec_id>', methods=['POST'])
def toggle_recurring(rec_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT is_active FROM recurring_transactions WHERE id = ? AND user_id = ?", (rec_id, user_id))
    row = c.fetchone()
    if row:
        new_status = 0 if row[0] == 1 else 1
        c.execute("UPDATE recurring_transactions SET is_active = ? WHERE id = ?", (new_status, rec_id))
        conn.commit()
    conn.close()
    return redirect(url_for('transactions'))


if __name__ == '__main__':
    app.run(debug=True)
