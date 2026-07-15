import sqlite3

links = [
    "https://serviceactivation.google.com/subscription/new/AQCpiIFOJTeLbb5XIA3FL0J56_UqsORVa35dzpTzR3qbtvUMf5cB_77J_EGS3rN_IhsOrEUFXhSI_dKY7Ny0ndb6ZYrum7W36pvT_6zURM9_ZrBddwJcF3hnEshFX4JHpUnQPWh-J3M2CtW690EB-Ju-gJmrOAhtNvbRysQzs_qcotrUR6mIvF44ke-vMicfTevbD9NzFRZBxezrUMoWHieO49XkjFxgR-xtTHX0QVxK5_fqJqc2O18jqcNVoniZYqZpih-E6NCpVxwzuA==",
    "https://serviceactivation.google.com/subscription/new/AQCpiIFs9DWGK9JCJsgi_6F-0gzFT0iWUmSf4tv3029eOC8Kz5CcubGBz_SrkiXWq_HKePg1ZNR58NQVqqQnB6dl_d9DzA67bJN3LyChbryNcY-V2WVpAfu2p_sm-Q4iMyIQbQroAlrT8FAet1oupUZx_4SQtbzLQCioblC6lYCvTZdLaqjJgUWf7OWPvq5i-TMB7pFI4SIKgyFtEqr0vJFkxtQEaOGznil4N_ULLwjYNo6F4Am4mw467QEM5GA4HhUFrnJ84KlW_w2HmA==",
    "https://serviceactivation.google.com/subscription/new/AQCpiIEpzBZpQNzoqbPIPkziW62uBzGQmU85uzFjy_cWBGguvGKXIDlhF5djvjiiW3r2c7jr1A0Mx-M1C9iOIv9IPQeUetf8F-AGgpLrATS_HWO2Fpz3BuSw-YE9ORIS0dgqhISZ2TYPj2pYl9xKFDDYsy3OV91L8C9JBEqslhx8Unf5qVr5k0VlklLNOeH2Cs7hDSH--fE030uTcMPPP6ewpq3JIvWWR4x4m60Vfo5SiAfrtFADR6egyay2wVj3tNp0OWVZXAGzXh9IOg=="
]

conn = sqlite3.connect('/root/telegram_shop_bot/shop.db')
cursor = conn.cursor()

deleted_count = 0
for link in links:
    cursor.execute("DELETE FROM product_stock WHERE data=?", (link,))
    deleted_count += cursor.rowcount

conn.commit()
conn.close()

print(f"Deleted {deleted_count} items from the stock table.")
