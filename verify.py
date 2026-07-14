import os
import requests

def main():
    token = None
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.strip().split("=", 1)
                    if k.strip() in ("TELEGRAM_BOT_TOKEN", "BOT_TOKEN"):
                        token = v.strip().strip("'\"")

    if not token:
        print("Error: TELEGRAM_BOT_TOKEN not found in .env")
        return

    # Clear/restore default bot description
    code = "🤖 Premium Google AI Pro / Gemini Advanced 18-Month activations. Instant automatic delivery, 100% secure."
    try:
        print(f"Restoring default bot description: {code}")
    except UnicodeEncodeError:
        print(f"Restoring default bot description: {code.encode('ascii', 'ignore').decode('ascii')}")

    r1 = requests.post(f"https://api.telegram.org/bot{token}/setMyDescription", json={"description": code})
    r2 = requests.post(f"https://api.telegram.org/bot{token}/setMyShortDescription", json={"short_description": code})

    print("Set Description Response:", r1.json())
    print("Set Short Description Response:", r2.json())

if __name__ == "__main__":
    main()
