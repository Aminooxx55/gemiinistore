import time
import hmac
import hashlib
import httpx
import asyncio
import json
from urllib.parse import urlencode

BINANCE_API_KEY = "SdYTCQlUP1fZmpwIbdjphFMCud3WeNZk0tEpTSQAT8wjpf1ITPcDgqioeIL6dgKA"
BINANCE_API_SECRET = "iU4FFrdr7mvIe9WSsF81XzobQywfa5oUTA7YZFMehYzp3d5esvieftj62HthGIyP"

async def main():
    params = {
        'timestamp': int(time.time() * 1000),
        'recvWindow': 60000,
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
    
    print("=== Testing Binance SAPI Directly ===")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                "https://api.binance.com/sapi/v1/pay/transactions",
                headers=headers,
                params=params
            )
            print(f"Status Code: {r.status_code}")
            print(f"Response: {r.text[:200]}")
            if r.status_code == 200:
                print(f"SUCCESS! Direct connection worked!")
                data = r.json().get("data", [])
                if data:
                    print("First Tx Full Details:", json.dumps(data[0], indent=2))
                else:
                    print("No transactions found.")
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    asyncio.run(main())
