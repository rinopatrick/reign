# Sovereign Ledger — Specification

## Overview
Local-first personal finance dashboard. Self-hosted, zero subscription, AI-assisted.

## Core Value Prop
1. Upload bank CSV → auto-categorize transactions
2. Dashboard: net worth, cashflow, budgets, trends
3. PDF report export (monthly/year-end)
4. 100% offline — SQLite file, no cloud

## Tech Stack
- **Backend:** Python 3.13, FastAPI, SQLAlchemy 2.0 (async), SQLite, Pydantic
- **Frontend:** Next.js 14 (App Router), Tailwind, shadcn/ui, Recharts
- **PDF:** ReportLab (institutional style)
- **Task runner:** uv

## MVP Scope (v1.0)
### Must Have
- [ ] CSV import for BCA, Mandiri, BRI, BNI, Jenius, Blu, Jago
- [ ] Auto-categorization engine (rules + keyword matching)
- [ ] CRUD accounts, categories, transactions
- [ ] Dashboard: net worth, monthly cashflow, top categories, trend
- [ ] Budgeting: set limits, track progress, overspend alerts
- [ ] PDF monthly report (ReportLab, clean minimal style)
- [ ] Multi-currency: IDR, USD, AUD

### Out of Scope (v1.0)
- Bank API integration (too complex, privacy risk)
- Mobile app
- LLM categorization fallback (rules-only for MVP)
- Recurring transactions
- Investment tracking

## Acceptance Criteria
1. User can upload BCA/Mandiri CSV and see categorized transactions within 3 seconds
2. Dashboard loads in <1s for 1000 transactions
3. PDF report renders A4 with cover, summary, category breakdown
4. All data stored in single SQLite file (`sovereign-ledger.db`)
5. Zero external API calls required for core functionality
