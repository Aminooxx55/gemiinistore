from utils.cryptomus import is_cryptomus_enabled, CRYPTOMUS_MERCHANT_UUID, CRYPTOMUS_API_KEY

def main():
    print("=== Cryptomus Diagnostic ===")
    print("Enabled:", is_cryptomus_enabled())
    print("Merchant UUID:", CRYPTOMUS_MERCHANT_UUID)
    print("API Key Length:", len(CRYPTOMUS_API_KEY) if CRYPTOMUS_API_KEY else 0)

if __name__ == "__main__":
    main()
