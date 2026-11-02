"""Market price service — Yahoo Finance chart API (public, no auth).

Symbol mapping: bare 4-letter IDX tickers (BBCA) -> BBCA.JK. Symbols already
containing a dot or exchange suffix pass through unchanged. Non-IDR results
are returned as-is; the caller decides currency handling.
"""

import logging
from decimal import Decimal, InvalidOperation

import httpx

logger = logging.getLogger("reign.market")

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
BARE_TICKER_LEN = 4
REQUEST_TIMEOUT_S = 8.0


def resolve_yahoo_symbol(symbol: str) -> str:
    """Map a user symbol to a Yahoo Finance symbol."""
    s = (symbol or "").strip().upper()
    if not s:
        return s
    if "." in s:
        return s
    if len(s) == BARE_TICKER_LEN and s.isalpha():
        return f"{s}.JK"
    return s


async def fetch_price(symbol: str, client: httpx.AsyncClient | None = None) -> Decimal | None:
    """Return the latest regular-market price, or None when unavailable."""
    yahoo_symbol = resolve_yahoo_symbol(symbol)
    if not yahoo_symbol:
        return None
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S)
    try:
        r = await client.get(
            YAHOO_CHART_URL.format(symbol=yahoo_symbol),
            params={"interval": "1d", "range": "1d"},
        )
        r.raise_for_status()
        payload = r.json()
        meta = (payload.get("chart", {}).get("result") or [{}])[0].get("meta", {})
        price = meta.get("regularMarketPrice")
        if price is None:
            closes = (
                (payload.get("chart", {}).get("result") or [{}])[0]
                .get("indicators", {})
                .get("quote", [{}])[0]
                .get("close", [])
            )
            closes = [c for c in closes if c is not None]
            price = closes[-1] if closes else None
        if price is None:
            return None
        return Decimal(str(price))
    except (httpx.HTTPError, InvalidOperation, ValueError, KeyError, IndexError) as e:
        logger.debug("Market price unavailable for %s: %s", yahoo_symbol, e)
        return None
    finally:
        if own_client:
            await client.aclose()
