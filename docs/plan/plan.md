# Plan — Reign v1.0

**Status:** [ ] Not Started
**Track:** reign

---

## Phase 1: Scaffold & Database
- [ ] Task 1.1: Init uv project, src layout, configure ruff + pytest
- [ ] Task 1.2: Design schema (accounts, categories, transactions, budgets)
- [ ] Task 1.3: Implement SQLAlchemy models + Alembic setup
- [ ] Task 1.4: Create repository layer (CRUD + search)
- [ ] Task 1.5: Seed default categories + currencies

## Phase 2: Backend API
- [ ] Task 2.1: FastAPI app factory + config + logging
- [ ] Task 2.2: Accounts API (CRUD)
- [ ] Task 2.3: Categories API (CRUD)
- [ ] Task 2.4: Transactions API (CRUD, filter, pagination)
- [ ] Task 2.5: CSV upload endpoint + parser framework
- [ ] Task 2.6: Auto-categorization engine (keyword rules)
- [ ] Task 2.7: Dashboard metrics aggregation endpoints
- [ ] Task 2.8: Budget API (CRUD + progress)

## Phase 3: Frontend
- [ ] Task 3.1: Next.js init + Tailwind + shadcn/ui
- [ ] Task 3.2: Layout + navigation shell
- [ ] Task 3.3: Accounts page
- [ ] Task 3.4: Transactions page (table + import)
- [ ] Task 3.5: Dashboard page (charts + KPIs)
- [ ] Task 3.6: Budgets page
- [ ] Task 3.7: Categories settings page

## Phase 4: PDF & Polish
- [ ] Task 4.1: ReportLab monthly report generator
- [ ] Task 4.2: PDF export endpoint
- [ ] Task 4.3: CSV parser for 3 bank formats (BCA, Mandiri, Jenius)
- [ ] Task 4.4: Integration tests (end-to-end CSV → dashboard → PDF)
- [ ] Task 4.5: README + .env.example

## Verification
- [ ] All pytest tests pass (>80% coverage)
- [ ] Ruff lint/format clean
- [ ] Manual test: upload CSV → dashboard → PDF
