import asyncio as asy
from store.models import Swap, Token, Pool, Transfer
from evme_config import fetcher

from abi.get_abis import ABI_FILES
from store.db import init_db, close_db

def format_amount(raw: str, decimals: int = 18) -> str:
    """
    Convert raw uint256 string into a human-readable number with commas.
    Example: "1000000000000000000" -> "1.0"
             "900000000000000000000000000" -> "900,000,000.0"
    """
    value = int(raw)
    human = value / (10 ** decimals)
    # Use , for commas and . for decimals
    return f"{human:,.1f}"


async def summarize_transfers_from(address: str):
    transfers = (
        await Transfer.filter(from_addr=address)
        .prefetch_related("token")
        .order_by("block_number", "log_index")
    )

    if not transfers:
        print(f"No transfers found from {address}")
        return

    print(f"Transfers from {address}:")
    for t in transfers:
        if t.to_addr in ["0x000000000000000000000000000000000000dEaD"]:
            continue
        token_symbol = getattr(t.token, "symbol", "?")
        decimals = getattr(t.token, "decimals", 18)  # default to 18
        formatted_value = format_amount(t.value_raw, decimals)
        print(
            f" • Sent {formatted_value} {token_symbol} → {t.to_addr} "
            f"(tx: {t.tx_hash})"
        )



async def main():
    await init_db()           # uses DB_URL env or sqlite://events.sqlite3
    await summarize_transfers_from("0x8FB8a35f99A9e7fF87cd4E0e6fB1A87b72F88954")
    
    
    #try:
    #    await fetcher.run_polling(5, 10_000)
    #finally:
    await close_db()





if __name__ == '__main__':
    #while True:
    #try:
    asy.run(main())
    #except KeyboardInterrupt:
    #    logger.info("Bot shutdown via KeyboardInterrupt.")
    #    #break
    #except Exception as e:
    #    # Log unexpected exceptions from TG API or any other part of main.py
    #    logger.exception("Unhandled exception in main: {}", e)
    #    # Optionally wait a few seconds before restarting to prevent a rapid crash loop
    #    import time
    #    time.sleep(5)