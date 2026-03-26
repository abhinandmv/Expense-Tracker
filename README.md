# Expense Tracker

A Flask web app for tracking personal finances — log income and expenses, set up recurring transactions, get AI-powered insights, and parse receipts using a local Ollama model.

## Features

- **User Auth** — Register, log in, and maintain separate transaction histories per user
- **Transaction Management** — Add, view, and delete expense/income entries with category and payment method
- **Recurring Transactions** — Schedule weekly, monthly, or yearly recurring payments that auto-generate on due dates
- **Statistics** — Visual breakdown of spending by category and payment method
- **AI Chat (Ollama)** — Ask questions about your finances using a local LLM (`llama3.2` by default)
- **Receipt Parsing** — Upload a receipt image and extract transaction details automatically via `llava` vision model

## Tech Stack

- **Backend**: Python, Flask, SQLite
- **AI**: [Ollama](https://ollama.com) (local LLM — `llama3.2` for chat, `llava` for vision)
- **Frontend**: Jinja2 templates, custom CSS

## Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com) installed and running locally
- Required Ollama models pulled:
  ```bash
  ollama pull llama3.2
  ollama pull llava
  ```

## Setup

1. **Clone the repo**
   ```bash
   git clone https://github.com/abhinandmv/Expense-Tracker.git
   cd expense-tracker
   ```

2. **Create a virtual environment and install dependencies**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Initialize the database**
   ```bash
   python init_db.py
   ```

4. **Set a secret key**

   In `.env`, set your secret key:                                                                                                                                  ```
    SECRET_KEY=your_secret_key_here                                                                                                                             
   ```

5. **Start Ollama** (in a separate terminal)
   ```bash
   ollama serve
   ```

6. **Run the app**
   ```bash
   flask run
   ```
   Or with Gunicorn:
   ```bash
   gunicorn app:app
   ```

   Open `http://localhost:5000` in your browser.

## Project Structure

```
.
├── app.py               # Main Flask application
├── init_db.py           # Database initialization script
├── requirements.txt     # Python dependencies
├── static/              # CSS, images, videos
└── templates/           # Jinja2 HTML templates
    ├── base.html
    ├── index.html
    ├── login.html
    ├── register.html
    ├── statistics.html
    └── transaction.html
```

## Configuration

| Variable | Location | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | `.env` | — | Flask session secret key |   
| `OLLAMA_BASE_URL` | `app.py` | `http://localhost:11434` | Ollama API endpoint |
| `CHAT_MODEL` | `app.py` | `llama3.2` | LLM used for finance chat |
| `VISION_MODEL` | `app.py` | `llava` | Model used for receipt parsing |
| `DATABASE` | `app.py` | `finance_tracker.db` | SQLite database file path |
