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
    
    print("=== Testing Binance SAPI with Proxies ===")
    
    # Fetch HTTP proxies from TheSpeedX GitHub list
    proxies = []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get("https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt")
            if r.status_code == 200:
                raw_proxies = r.text.strip().split("\n")
                proxies = [p.strip() for p in raw_proxies if p.strip()]
                print(f"Fetched {len(proxies)} proxies from GitHub SOCKS-List.")
    except Exception as e:
        print("Failed to fetch proxies:", e)

    # Try each proxy
    for proxy in proxies[:30]:  # limit to first 30 for speed
        proxy_url = f"http://{proxy}"
        print(f"Testing Proxy: {proxy_url}")
        try:
            # Create httpx client with proxy
            async with httpx.AsyncClient(proxies={"http://": proxy_url, "https://": proxy_url}, timeout=5.0) as client:
                r = await client.get(
                    "https://api.binance.com/sapi/v1/pay/transactions",
                    headers=headers,
                    params=params
                )
                print(f"Proxy {proxy} -> Status Code: {r.status_code}")
                print(f"Proxy {proxy} -> Response: {r.text[:200]}")
                if r.status_code in [200, 400]:
                    print(f"🎉 SUCCESS! Proxy {proxy} worked!")
                    break
        except Exception as e:
            pass

if __name__ == "__main__":
    asyncio.run(main())
