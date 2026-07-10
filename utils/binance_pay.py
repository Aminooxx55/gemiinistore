import time
import hmac
import hashlib
import httpx
import os
import logging
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

# Global cache for the working proxy to make future requests instant
WORKING_PROXY = None

def get_binance_keys():
    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.getenv("BINANCE_API_KEY", "")
    secret_key = os.getenv("BINANCE_API_SECRET", "")
    return api_key, secret_key

async def fetch_proxies() -> list[str]:
    """Fetch HTTP proxies from European countries (DE, FR, NL) to bypass US IP block."""
    proxies = []
    countries = ["de", "fr", "nl"]
    async with httpx.AsyncClient(timeout=8.0) as client:
        for country in countries:
            url = f"https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/{country}/http.txt"
            try:
                r = await client.get(url)
                if r.status_code == 200:
                    raw_proxies = r.text.strip().split("\n")
                    cleaned = [p.strip() for p in raw_proxies if p.strip()]
                    proxies.extend(cleaned)
            except Exception as e:
                logger.warning(f"Failed to fetch {country.upper()} proxies: {e}")
    return proxies

async def query_binance_pay_api() -> list[dict]:
    """
    Query the Binance Pay transaction history API using working proxies.
    Returns the list of transaction dictionaries.
    """
    global WORKING_PROXY
    api_key, secret_key = get_binance_keys()
    if not api_key or not secret_key:
        raise ValueError("Binance API credentials not set in .env file!")

    params = {
        'timestamp': int(time.time() * 1000),
        'recvWindow': 60000,
        'limit': 100
    }
    
    query_string = urlencode(params)
    signature = hmac.new(
        secret_key.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    params['signature'] = signature
    headers = {'X-MBX-APIKEY': api_key}

    # 1. Try the cached working proxy first for instant response
    if WORKING_PROXY:
        try:
            async with httpx.AsyncClient(proxies={"http://": WORKING_PROXY, "https://": WORKING_PROXY}, timeout=6.0) as client:
                r = await client.get("https://api.binance.com/sapi/v1/pay/transactions", headers=headers, params=params)
                if r.status_code == 200:
                    return r.json().get("data", [])
                else:
                    logger.warning(f"Cached proxy {WORKING_PROXY} returned status {r.status_code}. Resetting cache.")
                    WORKING_PROXY = None
        except Exception as e:
            logger.warning(f"Cached proxy {WORKING_PROXY} failed: {e}. Resetting cache.")
            WORKING_PROXY = None

    # 2. Fetch fresh proxies and find a working one
    proxies = await fetch_proxies()
    if not proxies:
        # Fallback to direct request (might fail if server is in restricted region)
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get("https://api.binance.com/sapi/v1/pay/transactions", headers=headers, params=params)
            if r.status_code == 200:
                return r.json().get("data", [])
            raise Exception(f"Direct request failed: {r.text}")

    # Limit proxy search space to first 25 for performance
    for proxy in proxies[:25]:
        proxy_url = f"http://{proxy}"
        try:
            async with httpx.AsyncClient(proxies={"http://": proxy_url, "https://": proxy_url}, timeout=5.0) as client:
                r = await client.get("https://api.binance.com/sapi/v1/pay/transactions", headers=headers, params=params)
                if r.status_code == 200:
                    # Save working proxy
                    WORKING_PROXY = proxy_url
                    logger.info(f"Successfully connected to Binance SAPI using proxy: {proxy_url}")
                    return r.json().get("data", [])
        except Exception:
            pass

    raise Exception("Unable to establish connection to Binance API after trying available proxies.")

async def verify_transaction(entered_ref: str, expected_amount: float, order_id: int) -> bool:
    """
    Search personal Binance Pay history for a matching transaction.
    Checks:
    1. Case-insensitive transactionId or orderId match.
    2. Positive incoming amount (fundsFlowType/amount > 0).
    3. Matching amount value (absolute value).
    4. Ensures the transaction wasn't already marked for another order in the database.
    """
    from database.db import get_db
    
    # Check if this reference has already been used in another order
    async with get_db() as db:
        cur = await db.execute("SELECT id FROM orders WHERE admin_note=? AND status='completed'", (entered_ref,))
        existing = await cur.fetchone()
        if existing:
            logger.warning(f"Reference ID {entered_ref} has already been used for order #{existing[0]}")
            return False

    txs = await query_binance_pay_api()
    entered_clean = entered_ref.strip().lower()

    for tx in txs:
        tx_id = tx.get("transactionId", "").strip().lower()
        order_id_bin = tx.get("orderId", "").strip().lower()

        if entered_clean == tx_id or entered_clean == order_id_bin:
            # Check funds flow (must be received funds)
            # Incoming payments have positive amount values in fundsDetail or positive amount string
            amount_str = tx.get("amount", "0")
            try:
                amount_val = float(amount_str)
            except ValueError:
                amount_val = 0.0

            # If amount is negative in transaction summary, it is a payment sent. 
            # However, check fundsDetail which lists positive received amounts.
            # Let's support both standard positive amount field and checking fundsDetail.
            is_incoming = amount_val > 0
            if not is_incoming:
                # Check fundsDetail
                funds = tx.get("fundsDetail", [])
                if funds:
                    try:
                        is_incoming = float(funds[0].get("amount", "0")) > 0
                    except ValueError:
                        pass

            if not is_incoming:
                logger.warning(f"Transaction ID {entered_ref} is a outgoing payment (withdrawal/sent), not incoming!")
                continue

            # Get received amount
            actual_amount = 0.0
            funds = tx.get("fundsDetail", [])
            if funds:
                try:
                    actual_amount = float(funds[0].get("amount", "0"))
                except ValueError:
                    pass
            else:
                try:
                    actual_amount = abs(float(amount_str))
                except ValueError:
                    pass

            # Validate amount matches (allow small rounding tolerance, e.g., 0.01)
            if abs(actual_amount - expected_amount) > 0.02:
                logger.warning(f"Amount mismatch for transaction {entered_ref}: expected {expected_amount}, got {actual_amount}")
                continue

            # Update order admin_note with transaction ID to mark as used
            async with get_db() as db:
                await db.execute("UPDATE orders SET admin_note=? WHERE id=?", (entered_ref, order_id))
                await db.commit()

            return True

    return False
