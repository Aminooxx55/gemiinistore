import json
import base64
import hashlib
import httpx
import asyncio

# Keys from remote env
CRYPTOMUS_MERCHANT_UUID = "9e723c36-e0bb-4e90-bf4d-5406f93342f5"
CRYPTOMUS_API_KEY = "fxQ4uUe4dmnVJRmbpLZME8rFDXmgk671c98HKEkKQofeA7PiNS71Z3aaD49pKysbXjflFueuI3XaF7QM9YksXuvsVaUey1D2pf0gywYiUhSEWOHJAvZ4YvM68hR7NfUS"

def generate_signature(payload: dict, api_key: str) -> str:
    payload_str = json.dumps(payload, separators=(',', ':'))
    encoded_payload = base64.b64encode(payload_str.encode('utf-8')).decode('utf-8')
    sign = hashlib.md5((encoded_payload + api_key).encode('utf-8')).hexdigest()
    return sign

async def test_invoice(use_callback: bool):
    payload = {
        "amount": "1.49",
        "currency": "USD",
        "order_id": "test_order_12345",
        "lifetime": 3600
    }
    if use_callback:
        payload["url_callback"] = "https://example.com/callback"

    sign = generate_signature(payload, CRYPTOMUS_API_KEY)
    headers = {
        "merchant": CRYPTOMUS_MERCHANT_UUID,
        "sign": sign,
        "Content-Type": "application/json"
    }

    print(f"\nTesting invoice creation (use_callback={use_callback}):")
    print("Payload:", payload)
    print("Sign:", sign)

    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post("https://api.cryptomus.com/v1/payment", json=payload, headers=headers)
        print("Status Code:", r.status_code)
        print("Response:", r.text)

async def main():
    await test_invoice(use_callback=True)
    await test_invoice(use_callback=False)

if __name__ == "__main__":
    asyncio.run(main())
