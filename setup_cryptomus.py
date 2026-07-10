import os

def main():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_path):
        print("Error: .env not found")
        return

    # Read .env lines
    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Define variables to set
    keys_to_set = {
        "CRYPTOMUS_MERCHANT_UUID": "9e723c36-e0bb-4e90-bf4d-5406f93342f5",
        "CRYPTOMUS_API_KEY": "fxQ4uUe4dmnVJRmbpLZME8rFDXmgk671c98HKEkKQofeA7PiNS71Z3aaD49pKysbXjflFueuI3XaF7QM9YksXuvsVaUey1D2pf0gywYiUhSEWOHJAvZ4YvM68hR7NfUS"
    }

    # Update or add values
    new_lines = []
    keys_found = set()
    for line in lines:
        matched = False
        for k, v in keys_to_set.items():
            if line.strip().startswith(f"{k}="):
                new_lines.append(f"{k}={v}\n")
                keys_found.add(k)
                matched = True
                break
        if not matched:
            new_lines.append(line)

    for k, v in keys_to_set.items():
        if k not in keys_found:
            new_lines.append(f"{k}={v}\n")

    # Write back to .env
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    print("Success: Cryptomus keys updated in .env!")

if __name__ == "__main__":
    main()
