# Sovereign Ledger

**Local-first personal finance tracker.** No cloud, no subscriptions, no data leaks. Your money, your machine, your rules.

![Version](https://img.shields.io/badge/version-0.2.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Stack](https://img.shields.io/badge/stack-FastAPI%20%2B%20Vanilla%20JS-orange)

---

## Philosophy

Sovereign Ledger was built for one purpose: give you complete control over your financial data. Everything runs locally on your machine using a single SQLite file. No accounts to create, no API keys to manage, no vendor lock-in.

---

## Features

### Core
- **Multi-account management** — Track checking, savings, cash, investment accounts
- **Categories with auto-categorization** — Keyword-based transaction categorization
- **Multi-currency support** — IDR, USD, AUD (easily extensible)
- **Dark mode** — Full dark/light theme toggle

### Productivity
| # | Feature | Shortcut |
|---|---------|----------|
| 1 | **Keyboard Shortcuts** | `Ctrl+N` Add, `Ctrl+S` Save, `/` Search, `Esc` Close, `C` Calendar |
| 2 | **Transaction Templates** | Save frequent transactions to localStorage |
| 3 | **Quick Add** | Floating + button on every page |
| 4 | **Bulk Edit** | Select multiple rows → edit category/date at once |
| 5 | **CSV Import + Preview** | Preview first 10 rows before confirming import |
| 6 | **Multi-format Export** | CSV + JSON export buttons |

### Intelligence
| # | Feature | Details |
|---|---------|---------|
| 7 | **Recurring Transactions** | Full CRUD for monthly recurring entries |
| 8 | **Dashboard Activity Summary** | Stats + upcoming recurring list |
| 9 | **Transaction Notes & Tags** | Expandable notes, tag badges, tag-filtered search |
| 10 | **Budget Alerts** | Color-coded progress bars + dashboard banner when >90% spent |
| 11 | **Calendar Heatmap** | Monthly calendar with income/expense dots, click day for details |
| 12 | **Multi-Account Transfers** | Create linked debit/credit transfers excluded from summaries |

### Reporting
- **Monthly trend charts** — Income vs expense line chart
- **Category breakdown** — Doughnut chart of spending by category
- **3-month cash flow forecast** — Projection based on recurring transactions
- **PDF report generation** — One-click monthly PDF export
- **Backup & Restore** — Full JSON backup/restore of entire database

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI + async SQLAlchemy |
| Database | SQLite (local file) |
| Frontend | Vanilla JavaScript + Tailwind CSS + Chart.js |
| Package Manager | `uv` |

---

## Installation

### Prerequisites

Only one tool required: [**uv**](https://docs.astral.sh/uv/getting-started/installation/)

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | more"
```

### Run from Source

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/sovereign-ledger.git
cd sovereign-ledger

# 2. Run (uv automatically creates venv + installs deps)
uv run python -m sovereign_ledger

# 3. Open browser
# http://localhost:8000
```

That's it. No `pip install`, no `requirements.txt` manual setup. `uv` handles everything.

### Install as Tool

```bash
uv tool install git+https://github.com/yourusername/sovereign-ledger.git

# Then run anytime:
sovereign-ledger
```

---

## Data Storage

Your data lives in a single SQLite file in the project directory:

```
sovereign-ledger/
├── sovereign-ledger.db   <-- Your data is here
├── src/
└── ...
```

- **Backup:** Click "Backup Data" in the sidebar → downloads `sovereign_ledger_backup_YYYY-MM-DD.json`
- **Restore:** Click "Restore Data" → select JSON backup file
- **Migrate:** The app auto-creates tables on first run. For schema upgrades, run:
  ```bash
  uv run python migrate.py
  ```

The database file is 100% portable. Copy it between devices, back it up to your cloud of choice, or version it with Git.

---

## Development

```bash
# Run tests
uv run pytest

# Type checking
uv run mypy src/sovereign_ledger

# Lint
uv run ruff check src/
```

---

## Architecture

```
sovereign-ledger/
├── src/sovereign_ledger/
│   ├── api/
│   │   ├── app.py              # FastAPI factory
│   │   ├── schemas.py          # Pydantic models
│   │   └── routes/             # Transaction, Budget, Dashboard, etc.
│   ├── adapters/
│   │   ├── database.py         # SQLAlchemy engine & session
│   │   └── repository.py       # Async repository layer
│   ├── domain/
│   │   └── models.py           # SQLAlchemy ORM models
│   ├── services/
│   │   ├── csv_parser.py       # Bank CSV auto-detection
│   │   ├── categorizer.py      # Keyword-based auto-categorization
│   │   └── pdf_generator.py    # Monthly report PDFs
│   └── static/
│       ├── index.html          # Single-page app shell
│       └── app.js              # All frontend logic (~1100 lines)
└── tests/
```

---

## Screenshots

*(Add screenshots here)*

| Dashboard | Transactions | Calendar |
|-----------|-------------|----------|
| ![Dashboard]() | ![Transactions]() | ![Calendar]() |

---

## Roadmap

- [ ] Bank statement import (OFX/QFX)
- [ ] Reconciliation with bank statements
- [ ] Multi-user support (local profiles)
- [ ] Scheduled backups
- [ ] Mobile PWA support
- [ ] Investment/Stock tracking
- [ ] Split transactions

---

## License

MIT License. Your data, your rules.

---

## Credits

Built with:
- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy](https://www.sqlalchemy.org/)
- [Tailwind CSS](https://tailwindcss.com/)
- [Chart.js](https://www.chartjs.org/)
- [uv](https://docs.astral.sh/uv/)

---

**Sovereign Ledger** — *Finance without surveillance.*
