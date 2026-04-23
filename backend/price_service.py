"""Smart price update service.
- Mutual Funds: AMFI NAV daily feed
- Stocks: yfinance (free)
- Caching in MongoDB 'price_cache' collection
- Stale threshold: 6 hours for on-demand
- Daily cron refreshes all distinct symbols
"""
import logging
import math
import requests
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List


def _is_valid_num(x) -> bool:
    try:
        f = float(x)
        return math.isfinite(f)
    except (TypeError, ValueError):
        return False

logger = logging.getLogger(__name__)

STALE_HOURS = 6
AMFI_URL = "https://www.amfiindia.com/spages/NAVAll.txt"

# In-memory AMFI cache (refreshed daily)
_amfi_cache: Dict[str, Dict[str, Any]] = {}
_amfi_loaded_at: Optional[datetime] = None


def _parse_amfi_text(text: str) -> Dict[str, Dict[str, Any]]:
    """Parse AMFI NAVAll.txt. Format:
       Scheme Code;ISIN Div Payout;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date
    """
    data = {}
    for line in text.splitlines():
        parts = line.split(";")
        if len(parts) < 6:
            continue
        scheme_code = parts[0].strip()
        if not scheme_code.isdigit():
            continue
        try:
            nav = float(parts[4].strip())
            data[scheme_code] = {
                "scheme_code": scheme_code,
                "scheme_name": parts[3].strip(),
                "nav": nav,
                "date": parts[5].strip(),
            }
        except (ValueError, IndexError):
            continue
    return data


def refresh_amfi_cache() -> int:
    """Download the full AMFI NAV file and cache by scheme_code."""
    global _amfi_cache, _amfi_loaded_at
    try:
        r = requests.get(AMFI_URL, timeout=30)
        r.raise_for_status()
        _amfi_cache = _parse_amfi_text(r.text)
        _amfi_loaded_at = datetime.now(timezone.utc)
        logger.info(f"AMFI cache refreshed: {len(_amfi_cache)} schemes")
        return len(_amfi_cache)
    except Exception as e:
        logger.exception(f"AMFI refresh failed: {e}")
        return 0


def get_mf_nav(scheme_code: str) -> Optional[Dict[str, Any]]:
    """Get MF NAV by AMFI scheme code. Refreshes cache if stale."""
    global _amfi_loaded_at
    if not _amfi_cache or not _amfi_loaded_at or (datetime.now(timezone.utc) - _amfi_loaded_at) > timedelta(hours=12):
        refresh_amfi_cache()
    return _amfi_cache.get(str(scheme_code).strip())


def search_mf(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    if not _amfi_cache:
        refresh_amfi_cache()
    q = query.lower().strip()
    if not q:
        return []
    results = []
    for code, data in _amfi_cache.items():
        if q in data["scheme_name"].lower():
            results.append(data)
            if len(results) >= limit:
                break
    return results


def get_stock_price(symbol: str) -> Optional[Dict[str, Any]]:
    """Fetch stock price using yfinance. For NSE stocks append .NS suffix if missing."""
    try:
        import yfinance as yf
        sym = symbol.strip().upper()
        # Heuristic: if no suffix and looks like NSE ticker, append .NS
        if "." not in sym:
            sym_try = sym + ".NS"
        else:
            sym_try = sym
        tkr = yf.Ticker(sym_try)
        hist = tkr.history(period="2d")
        if hist.empty and sym_try.endswith(".NS"):
            # Try BSE
            sym_try = sym + ".BO"
            tkr = yf.Ticker(sym_try)
            hist = tkr.history(period="2d")
        if hist.empty:
            return None
        last_close_raw = hist["Close"].iloc[-1]
        prev_close_raw = hist["Close"].iloc[0] if len(hist) > 1 else last_close_raw
        if not _is_valid_num(last_close_raw):
            logger.warning(f"yfinance returned NaN/invalid close for {sym_try}")
            return None
        last_close = float(last_close_raw)
        prev_close = float(prev_close_raw) if _is_valid_num(prev_close_raw) else last_close
        change_pct = ((last_close - prev_close) / prev_close * 100) if prev_close else 0
        return {
            "symbol": sym,
            "yf_symbol": sym_try,
            "price": round(last_close, 2),
            "prev_close": round(prev_close, 2),
            "change_pct": round(change_pct, 2),
        }
    except Exception as e:
        logger.warning(f"Stock price fetch failed for {symbol}: {e}")
        return None


async def get_cached_price(db, asset_type: str, symbol: str, force: bool = False) -> Optional[Dict[str, Any]]:
    """Get price from cache; refresh if stale or forced. Returns dict with price, last_updated."""
    coll = db.price_cache
    key = f"{asset_type}:{symbol}"
    cached = await coll.find_one({"_id": key})
    now = datetime.now(timezone.utc)
    # Treat NaN-cached entries as invalid
    if cached and not _is_valid_num(cached.get("price")):
        cached = None
        try:
            await coll.delete_one({"_id": key})
        except Exception:
            pass
    if cached and not force:
        last = datetime.fromisoformat(cached["last_updated"])
        if now - last < timedelta(hours=STALE_HOURS):
            return {k: v for k, v in cached.items() if k != "_id"}

    # Refresh
    fresh = None
    if asset_type == "stock":
        p = get_stock_price(symbol)
        if p:
            fresh = {
                "asset_type": "stock",
                "symbol": symbol,
                "price": p["price"],
                "change_pct": p["change_pct"],
                "last_updated": now.isoformat(),
            }
    elif asset_type == "mf":
        p = get_mf_nav(symbol)
        if p:
            fresh = {
                "asset_type": "mf",
                "symbol": symbol,
                "scheme_name": p["scheme_name"],
                "price": p["nav"],
                "nav_date": p["date"],
                "last_updated": now.isoformat(),
            }

    if fresh:
        await coll.update_one({"_id": key}, {"$set": fresh}, upsert=True)
        return fresh
    # Fall back to stale cache
    if cached:
        return {k: v for k, v in cached.items() if k != "_id"}
    return None


async def refresh_all_portfolio_prices(db) -> Dict[str, int]:
    """Cron job: fetch all distinct symbols from portfolios and refresh prices."""
    logger.info("Starting daily price refresh...")
    refresh_amfi_cache()
    holdings = await db.portfolio.find({}, {"_id": 0, "asset_type": 1, "symbol": 1}).to_list(10000)
    unique = {(h["asset_type"], h["symbol"]) for h in holdings}
    updated = 0
    failed = 0
    for asset_type, symbol in unique:
        r = await get_cached_price(db, asset_type, symbol, force=True)
        if r:
            updated += 1
        else:
            failed += 1
    logger.info(f"Price refresh done: {updated} updated, {failed} failed")
    return {"updated": updated, "failed": failed, "total": len(unique)}
