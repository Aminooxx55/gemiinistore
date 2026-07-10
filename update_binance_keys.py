import os

def main():
    env_path = "/root/gemiinistore/.env"
    if not os.path.exists(env_path):
        env_path = os.path.join(os.path.dirname(__file__), ".env")

    if not os.path.exists(env_path):
        print("Error: .env not found")
        return

    # Read .env lines
    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    api_key = "SdYTCQlUP1fZmpwIbdjphFMCud3WeNZk0tEpTSQAT8wjpf1ITPcDgqioeIL6dgKA"
    secret_key = "iU4FFrdr7mvIe9WSsF81XzobQywfa5oUTA7YZFMehYzp3d5esvieftj62HthGIyP"

    # Update or add values
    new_lines = []
    key_found = False
    secret_found = False

    for line in lines:
        if line.strip().startswith("BINANCE_API_KEY="):
            new_lines.append(f"BINANCE_API_KEY={api_key}\n")
            key_found = True
        elif line.strip().startswith("BINANCE_API_SECRET="):
            new_lines.append(f"BINANCE_API_SECRET={secret_key}\n")
            secret_found = True
        else:
            new_lines.append(line)

    if not key_found:
        new_lines.append(f"BINANCE_API_KEY={api_key}\n")
    if not secret_found:
        new_lines.append(f"BINANCE_API_SECRET={secret_key}\n")

    # Write back to .env
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    print("Success: Binance keys updated in .env!")

if __name__ == "__main__":
    main()
