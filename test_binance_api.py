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
    
    # Fetch European proxies from ProxyScrape
    proxies = []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get("https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=DE,FR,NL,GB,IT,ES&ssl=yes&anonymity=anonymous")
            if r.status_code == 200:
                raw_proxies = r.text.strip().split("\r\n")
                # Clean empty lines
                proxies = [p.strip() for p in raw_proxies if p.strip()]
                print(f"Fetched {len(proxies)} proxies from Proxyscrape.")
    except Exception as e:
        print("Failed to fetch proxies:", e)

    if not proxies:
        # Fallback to a few public proxy lists if empty
        proxies = ["51.15.242.202:3128", "163.172.31.235:80", "51.158.154.173:3128"]

    # Try each proxy
    for proxy in proxies[:15]:  # limit to first 15 for speed
        proxy_url = f"http://{proxy}"
        print(f"Testing Proxy: {proxy_url}")
        try:
            # Create httpx client with proxy
            async with httpx.AsyncClient(proxies={"http://": proxy_url, "https://": proxy_url}, timeout=8.0) as client:
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
            print(f"Proxy {proxy} failed with error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
