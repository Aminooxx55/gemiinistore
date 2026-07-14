import time
import hmac
import hashlib
import httpx
import os
import logging
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

# Proxies removed since server is in Germany

def get_binance_keys():
    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.getenv("BINANCE_API_KEY", "")
    secret_key = os.getenv("BINANCE_API_SECRET", "")
    return api_key, secret_key

async def query_binance_pay_api() -> list[dict]:
    """
    Query the Binance Pay transaction history API directly.
    Returns the list of transaction dictionaries.
    """
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

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get("https://api.binance.com/sapi/v1/pay/transactions", headers=headers, params=params)
            if r.status_code == 200:
                return r.json().get("data", [])
            logger.warning('Direct request failed with status %d: %s', r.status_code, r.text)
    except Exception as e:
        logger.exception('Direct request to Binance API failed')

    raise Exception("Unable to establish connection to Binance API.")

async def verify_transaction(entered_ref: str, expected_amount: float, order_id: int) -> bool:
    logger.info('Verifying Binance Pay transaction: ref=%s, expected_amount=%.2f, order_id=%d', entered_ref, expected_amount, order_id)
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
        cur = await db.execute("SELECT id FROM orders WHERE admin_note=? AND status IN ('paid', 'delivered')", (entered_ref,))
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
            is_incoming = amount_val > 0

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

async def query_binance_deposit_api(coin: str = "USDT") -> list[dict]:
    """
    Query the Binance Spot Deposit History API.
    Returns a list of deposit dictionaries.
    """
    api_key, secret_key = get_binance_keys()
    if not api_key or not secret_key:
        raise ValueError("Binance API credentials not set in .env file!")

    params = {
        'coin': coin,
        'status': 1, # 1 = success
        'timestamp': int(time.time() * 1000),
        'recvWindow': 60000,
        'limit': 50
    }
    
    query_string = urlencode(params)
    signature = hmac.new(
        secret_key.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    params['signature'] = signature
    headers = {'X-MBX-APIKEY': api_key}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get("https://api.binance.com/sapi/v1/capital/deposit/hisrec", headers=headers, params=params)
            if r.status_code == 200:
                return r.json()
            logger.warning('Direct request failed with status %d: %s', r.status_code, r.text)
    except Exception as e:
        logger.exception('Direct request to Binance API failed')

    raise Exception("Unable to establish connection to Binance Spot API.")

async def verify_spot_deposit(tx_id: str, expected_amount: float, order_id: int, network: str = "TRX") -> bool:
    logger.info('Verifying Binance Spot Deposit: tx_id=%s, expected_amount=%.2f, order_id=%d', tx_id, expected_amount, order_id)
    from database.db import get_db
    
    async with get_db() as db:
        cur = await db.execute("SELECT id FROM orders WHERE admin_note=? AND status IN ('paid', 'delivered')", (tx_id,))
        existing = await cur.fetchone()
        if existing:
            logger.warning(f"TxID {tx_id} already used for order #{existing[0]}")
            return False

    try:
        deposits = await query_binance_deposit_api(coin="USDT")
    except Exception as e:
        logger.error(f"Error querying deposit API: {e}")
        return False

    entered_clean = tx_id.strip().lower()

    for dep in deposits:
        dep_txid = dep.get("txId", "").strip().lower()
        
        if dep_txid == entered_clean or entered_clean in dep_txid:
            if dep.get("network", "").upper() != network.upper():
                logger.warning(f"Network mismatch: expected {network}, got {dep.get('network')}")
                continue
                
            amount_str = dep.get("amount", "0")
            try:
                actual_amount = float(amount_str)
            except ValueError:
                actual_amount = 0.0
                
            if abs(actual_amount - expected_amount) > 0.05:
                logger.warning(f"Amount mismatch for deposit {tx_id}: expected {expected_amount}, got {actual_amount}")
                continue

            async with get_db() as db:
                await db.execute("UPDATE orders SET admin_note=? WHERE id=?", (tx_id, order_id))
                await db.commit()

            return True

    return False
