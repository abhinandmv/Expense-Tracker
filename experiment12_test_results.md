# EXPERIMENT 12
## Aim: Master Test Plan, Test Case Design (Phase 1)

---

## Master Test Plan (MTP)

**Introduction:**
- **Purpose:** To verify all functional and non-functional requirements of the Personal Finance Expense Tracker across all modules.
- **Scope:** Covers authentication, transaction CRUD, recurring payments, receipt OCR, chatbot, dashboard charts, statistics, and CSV export.

**Objectives:**
- Ensure every Flask route returns the correct response for valid and invalid inputs.
- Validate session-based user isolation — users must not access each other's data.
- Verify AI-dependent features degrade gracefully when Ollama is unavailable.
- Confirm responsive rendering on desktop, tablet, and mobile viewports.

**Component Specification**

| Component       | Specification                                    |
|-----------------|--------------------------------------------------|
| Operating System | Windows 11 / Ubuntu 22.04 / MacOS               |
| Python Version  | 3.13.5                                           |
| Flask Version   | 3.x                                              |
| Database        | SQLite3 (local file finance_tracker.db)          |
| AI Backend      | Ollama v0.3+ running on localhost:11434          |
| Browsers Tested | Google Chrome 124, Mozilla Firefox 125           |
| Testing Tools   | pytest 9.0.2, unittest.mock (Ollama), Flask test client |

---

## Test Case Design (Phase 1)

| TC ID | Module      | Test Scenario                                                              | Expected Result                                                                 | Status |
|-------|-------------|----------------------------------------------------------------------------|---------------------------------------------------------------------------------|--------|
| TC-01 | Auth        | Register with unique username/email/phone/password                         | Account created, flash 'Registration successful', redirect to login             | Pass   |
| TC-02 | Auth        | Register with existing username                                            | Flash 'Username already exists', no new row in users table                      | Pass   |
| TC-03 | Auth        | Login with correct credentials                                             | Session created, redirect to dashboard, username in navbar                      | Pass   |
| TC-04 | Auth        | Login with wrong password                                                  | Flash 'Invalid username or password', no session created                        | Pass   |
| TC-05 | Auth        | Access /transactions without login                                         | Redirect to /login                                                              | Pass   |
| TC-06 | Auth        | Logout                                                                     | Session cleared, redirect to /login with success flash                          | Pass   |
| TC-07 | Transaction | Add transaction with valid data                                            | New row in transactions table, appears in table on page                         | Pass   |
| TC-08 | Transaction | Add transaction with amount = 0                                            | Flash 'Amount must be greater than zero', no INSERT                             | Pass   |
| TC-09 | Transaction | Delete a transaction                                                       | Row removed from table, flash 'Transaction deleted'                             | Pass   |
| TC-10 | Transaction | View empty transactions state                                              | Inbox icon and 'No transactions yet' message displayed                          | Pass   |
| TC-11 | Dashboard   | View UPI/Cash totals after adding transactions                             | Correct sums shown in stat cards by payment method                              | Pass   |
| TC-12 | Dashboard   | Chart endpoints return correct JSON structure                              | `{'labels': [...], 'amounts': [...]}` with matching counts                      | Pass   |
| TC-13 | Statistics  | View pie chart with 3+ categories                                          | Pie chart renders with correct palette and legend                               | Pass   |
| TC-14 | Statistics  | Total expenses matches sum of all transactions                             | Displayed total equals SUM(amount) from DB                                      | Pass   |
| TC-15 | Recurring   | Add monthly recurring payment                                              | New row in recurring_transactions, appears in recurring table                   | Pass   |
| TC-16 | Recurring   | Recurring payment generates transaction on next visit                      | Auto-transaction inserted, next_due_date advanced                               | Pass   |
| TC-17 | Recurring   | Pause a recurring payment                                                  | Status shows 'Paused', row opacity reduced, no new transactions generated       | Pass   |
| TC-18 | Receipt OCR | Upload clear receipt image (Ollama running)                                | Add Transaction form pre-filled with extracted values                           | Pass   |
| TC-19 | Receipt OCR | Upload image when Ollama is offline                                        | Error message: 'Ollama is not running. Start it with ollama serve.'             | Pass   |
| TC-20 | Chatbot     | Ask 'How much did I spend on Food?' with transactions present              | Bot replies with category-specific amount from context                          | Pass   |
| TC-21 | Chatbot     | Chat when Ollama is offline                                                | Message: 'Ollama is not running. Please start it with ollama serve.'            | Pass   |
| TC-22 | CSV Export  | Click Export CSV with transactions                                         | Browser downloads transactions.csv with correct headers and data                | **Fail** |
| TC-23 | Security    | Attempt to delete another user's transaction by ID                        | DELETE query scoped to session user_id — no effect on other user's data         | **Fail** |

---

## Test Execution Results

**Test Run:** `pytest test_app.py -v --tb=short`
**Platform:** darwin | Python 3.13.5 | pytest 9.0.2

```
============================= test session starts ==============================
platform darwin -- Python 3.13.5, pytest-9.0.2, pluggy-1.6.0
rootdir: /Users/abhinand/projects/Expense Tracker
collected 23 items

test_app.py::TestAuthentication::test_tc01_register_unique_user PASSED          [  4%]
test_app.py::TestAuthentication::test_tc02_register_duplicate_username PASSED   [  8%]
test_app.py::TestAuthentication::test_tc03_login_correct_credentials PASSED     [ 13%]
test_app.py::TestAuthentication::test_tc04_login_wrong_password PASSED          [ 17%]
test_app.py::TestAuthentication::test_tc05_access_transactions_without_login PASSED [ 21%]
test_app.py::TestAuthentication::test_tc06_logout_clears_session PASSED         [ 26%]
test_app.py::TestTransactions::test_tc07_add_valid_transaction PASSED           [ 30%]
test_app.py::TestTransactions::test_tc08_add_transaction_zero_amount PASSED     [ 34%]
test_app.py::TestTransactions::test_tc09_delete_transaction PASSED              [ 39%]
test_app.py::TestTransactions::test_tc10_empty_transactions_message PASSED      [ 43%]
test_app.py::TestDashboard::test_tc11_upi_cash_totals PASSED                    [ 47%]
test_app.py::TestDashboard::test_tc12_chart_endpoints_json_structure PASSED     [ 52%]
test_app.py::TestStatistics::test_tc13_statistics_renders_multiple_categories PASSED [ 56%]
test_app.py::TestStatistics::test_tc14_total_expenses_matches_db_sum PASSED     [ 60%]
test_app.py::TestRecurringPayments::test_tc15_add_monthly_recurring PASSED      [ 65%]
test_app.py::TestRecurringPayments::test_tc16_recurring_auto_generates_transaction_on_due_date PASSED [ 69%]
test_app.py::TestRecurringPayments::test_tc17_pause_recurring_stops_transaction_generation PASSED [ 73%]
test_app.py::TestReceiptOCR::test_tc18_upload_receipt_ollama_running PASSED     [ 78%]
test_app.py::TestReceiptOCR::test_tc19_upload_receipt_ollama_offline PASSED     [ 82%]
test_app.py::TestChatbot::test_tc20_chatbot_replies_with_spending_context PASSED [ 86%]
test_app.py::TestChatbot::test_tc21_chatbot_ollama_offline PASSED               [ 91%]
test_app.py::TestCSVExport::test_tc22_export_csv_downloads_correct_file FAILED  [ 95%]
test_app.py::TestSecurity::test_tc23_cannot_delete_another_users_transaction FAILED [100%]

================================== FAILURES ===================================
__________ TestCSVExport::test_tc22_export_csv_downloads_correct_file __________

test_app.py:486: in test_tc22_export_csv_downloads_correct_file
    assert resp.status_code == 200
AssertionError: GET /export_csv returned non-200.
The /export_csv route may not be implemented yet.
assert 404 == 200

________ TestSecurity::test_tc23_cannot_delete_another_users_transaction ________

test_app.py:533: in test_tc23_cannot_delete_another_users_transaction
    assert row is not None
AssertionError: SECURITY BREACH — TC-23 FAILED: user2 was able to delete user1's
transaction. The DELETE query in delete_transaction() must be scoped with
'AND user_id = <session user_id>'.

========================= short test summary info =============================
FAILED test_app.py::TestCSVExport::test_tc22_export_csv_downloads_correct_file
FAILED test_app.py::TestSecurity::test_tc23_cannot_delete_another_users_transaction
========================= 2 failed, 21 passed in 0.41s ========================
```

| Metric       | Result |
|--------------|--------|
| Total Tests  | 23     |
| Passed       | 21     |
| Failed       | 2      |
| Duration     | 0.41 s |

---

## Defects Found During Automated Testing

| ID     | Description                                                                                                        | Severity | Resolution                                                                                                                                              |
|--------|--------------------------------------------------------------------------------------------------------------------|----------|---------------------------------------------------------------------------------------------------------------------------------------------------------|
| D-TC22 | `GET /export_csv` returns HTTP 404. The `/export_csv` route does not exist in `app.py`. CSV export is currently front-end only (DOM scraping), making it untestable via HTTP. | Medium   | Add a server-side `/export_csv` Flask route that queries the transactions table for the logged-in user and returns a `text/csv` response with headers: Date, Category, Amount, Payment Method, Notes. |
| D-TC23 | `delete_transaction()` at `app.py:309` runs `DELETE FROM transactions WHERE id = ?` without a `user_id` filter, allowing any authenticated user to delete another user's transaction by guessing the integer ID. | Critical | Change the query to `DELETE FROM transactions WHERE id = ? AND user_id = ?` to scope deletes to the session owner.                                      |
