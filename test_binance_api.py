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
    
    print("=== Testing Binance SAPI /sapi/v1/pay/transactions ===")
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(
            "https://api.binance.com/sapi/v1/pay/transactions",
            headers=headers,
            params=params
        )
        print("Status Code:", r.status_code)
        try:
            print("Response:", r.json())
        except Exception:
            print("Raw Response:", r.text)

if __name__ == "__main__":
    asyncio.run(main())
