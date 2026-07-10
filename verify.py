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
                    if k.strip() == "TELEGRAM_BOT_TOKEN":
                        token = v.strip().strip("'\"")

    if not token:
        print("Error: TELEGRAM_BOT_TOKEN not found in .env")
        return

    # Check for verification code in verify_code.txt or direct input
    code = "9e723c36"
    print(f"Setting bot description and about text to: {code}")

    r1 = requests.post(f"https://api.telegram.org/bot{token}/setMyDescription", json={"description": code})
    r2 = requests.post(f"https://api.telegram.org/bot{token}/setMyAboutText", json={"about": code})

    print("Set Description Response:", r1.json())
    print("Set About Response:", r2.json())

if __name__ == "__main__":
    main()
