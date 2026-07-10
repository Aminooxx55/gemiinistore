import time
import hmac
import hashlib
import httpx
import asyncio
from urllib.parse import urlencode

BINANCE_API_KEY = "SdYTCQlUP1fZmpwIbdjphFMCud3WeNZk0tEpTSQAT8wjpf1ITPcDgqioeIL6dgKA"
BINANCE_API_SECRET = "iU4FFrdr7mvIe9WSsF81XzobQywfa5oUTA7YZFMehYzp3d5esvieftj62HthGIyP"

async def main():
    params = {
        'timestamp': int(time.time() * 1000),
        'limit': 10
    }
    
    query_string = urlencode(params)
    signature = hmac.new(
        BINANCE_API_SECRET.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    params['signature'] = signature
    headers = {'X-MBX-APIKEY': BINANCE_API_KEY}
    
    print("=== Testing Binance SAPI domains ===")
    domains = [
        "https://api.binance.com",
        "https://api1.binance.com",
        "https://api2.binance.com",
        "https://api3.binance.com",
        "https://api-gcp.binance.com"
    ]
    async with httpx.AsyncClient(timeout=15.0) as client:
        for domain in domains:
            url = f"{domain}/sapi/v1/pay/transactions"
            print(f"Testing: {url}")
            try:
                r = await client.get(url, headers=headers, params=params)
                print(f"[{domain}] Status Code: {r.status_code}")
                print(f"[{domain}] Response: {r.text[:200]}")
            except Exception as e:
                print(f"[{domain}] Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
