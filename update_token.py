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

    # Define variables to set
    new_token = "8827455049:AAGe7kqUxv6N_pmHzprDdGHgZpn8W4cqHpA"

    # Update or add values
    new_lines = []
    token_found = False
    for line in lines:
        if line.strip().startswith("BOT_TOKEN="):
            new_lines.append(f"BOT_TOKEN={new_token}\n")
            token_found = True
        else:
            new_lines.append(line)

    if not token_found:
        new_lines.append(f"BOT_TOKEN={new_token}\n")

    # Write back to .env
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    print("Success: BOT_TOKEN updated in .env!")

if __name__ == "__main__":
    main()
