"""FastAPI application factory."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from sovereign_ledger.adapters.database import AsyncSessionLocal, init_db
from sovereign_ledger.api.routes.accounts import router as accounts_router
from sovereign_ledger.api.routes.backup import router as backup_router
from sovereign_ledger.api.routes.budgets import router as budgets_router
from sovereign_ledger.api.routes.categories import router as categories_router
from sovereign_ledger.api.routes.dashboard import router as dashboard_router
from sovereign_ledger.api.routes.forecast import router as forecast_router
from sovereign_ledger.api.routes.goals import router as goals_router
from sovereign_ledger.api.routes.recurring import router as recurring_router
from sovereign_ledger.api.routes.reports import router as reports_router
from sovereign_ledger.api.routes.transactions import router as transactions_router
from sovereign_ledger.logging import setup_logging
from sovereign_ledger.utils.seed import seed_categories, seed_demo_account


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging()
    await init_db()
    async with AsyncSessionLocal() as session:
        await seed_categories(session)
        await seed_demo_account(session)
    yield


app = FastAPI(
    title="Sovereign Ledger",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(accounts_router, prefix="/api/accounts", tags=["accounts"])
app.include_router(categories_router, prefix="/api/categories", tags=["categories"])
app.include_router(transactions_router, prefix="/api/transactions", tags=["transactions"])
app.include_router(budgets_router, prefix="/api/budgets", tags=["budgets"])
app.include_router(dashboard_router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(goals_router, prefix="/api/goals", tags=["goals"])
app.include_router(forecast_router, prefix="/api/forecast", tags=["forecast"])
app.include_router(backup_router, prefix="/api", tags=["backup"])
app.include_router(reports_router, prefix="/api/reports", tags=["reports"])
app.include_router(recurring_router, prefix="/api/recurring", tags=["recurring"])

app.mount("/static", StaticFiles(directory="src/sovereign_ledger/static"), name="static")


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/")
async def root():
    return FileResponse("src/sovereign_ledger/static/index.html")
