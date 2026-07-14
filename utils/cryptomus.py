# -*- coding: utf-8 -*-
"""Cryptomus payment gateway integration."""
import json
import base64
import hashlib
import logging
import httpx
import os

logger = logging.getLogger(__name__)

from dotenv import load_dotenv
load_dotenv()

# Load keys from environment
CRYPTOMUS_MERCHANT_UUID = os.getenv("CRYPTOMUS_MERCHANT_UUID", "")
CRYPTOMUS_API_KEY = os.getenv("CRYPTOMUS_API_KEY", "")


def is_cryptomus_enabled() -> bool:
    return bool(CRYPTOMUS_MERCHANT_UUID and CRYPTOMUS_API_KEY)


def generate_signature(payload: dict, api_key: str) -> str:
    """Generate MD5 signature for Cryptomus API."""
    payload_str = json.dumps(payload)
    encoded_payload = base64.b64encode(payload_str.encode('utf-8')).decode('utf-8')
    sign = hashlib.md5((encoded_payload + api_key).encode('utf-8')).hexdigest()
    return sign


async def create_cryptomus_invoice(amount: float, order_id: str) -> tuple[str, str]:
    """
    Create a payment invoice on Cryptomus.
    Returns (payment_url, payment_uuid).
    """
    if not is_cryptomus_enabled():
        raise ValueError("Cryptomus is not configured in .env file!")

    payload = {
        "amount": f"{amount:.2f}",
        "currency": "USD",
        "order_id": order_id,
        "url_callback": "https://example.com/callback",  # Dummy, we use status polling
        "lifetime": 3600  # 1 hour validity
    }

    sign = generate_signature(payload, CRYPTOMUS_API_KEY)
    headers = {
        "merchant": CRYPTOMUS_MERCHANT_UUID,
        "sign": sign,
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            r = await client.post(
                "https://api.cryptomus.com/v1/payment",
                json=payload,
                headers=headers
            )
            res = r.json()
            if res.get("state") == 0 or res.get("status") == 200:
                result = res["result"]
                logger.info('Cryptomus invoice created successfully: uuid=%s, order_id=%s, amount=%.2f', result["uuid"], order_id, amount)
                return result["url"], result["uuid"]
            else:
                logger.error(f"Cryptomus API error response: {res}")
                raise Exception(res.get("message", "Failed to create invoice"))
        except Exception as e:
            logger.error(f"Error creating Cryptomus invoice: {e}")
            raise


async def check_cryptomus_status(uuid: str) -> str:
    """
    Check the status of a Cryptomus invoice.
    Returns status: 'pending', 'paid', 'expired', or 'failed'.
    """
    if not is_cryptomus_enabled():
        return "failed"

    payload = {"uuid": uuid}
    sign = generate_signature(payload, CRYPTOMUS_API_KEY)
    headers = {
        "merchant": CRYPTOMUS_MERCHANT_UUID,
        "sign": sign,
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            r = await client.post(
                "https://api.cryptomus.com/v1/payment/info",
                json=payload,
                headers=headers
            )
            res = r.json()
            if res.get("state") == 0 or res.get("status") == 200:
                c_status = res["result"].get("status", "").lower()
                logger.info('Cryptomus payment status check: uuid=%s, raw_status=%s', uuid, c_status)
                # Status classification
                if c_status in ["paid", "paid_over"]:
                    return "paid"
                elif c_status in ["active", "waiting", "process", "confirm_check"]:
                    return "pending"
                elif c_status in ["expired"]:
                    return "expired"
                else:
                    return "failed"
            else:
                logger.error(f"Cryptomus status check error: {res}")
                return "pending"
        except Exception as e:
            logger.error(f"Error checking Cryptomus status: {e}")
            return "pending"
