import asyncio as asy
from store.models import Swap, Token, Pool, Transfer
from evme_config import fetcher

from abi.get_abis import ABI_FILES
from store.db import init_db, close_db

async def main():
    await init_db()           # uses DB_URL env or sqlite://events.sqlite3
    a = await Swap.filter()
    print(len(a))
    try:
        await fetcher.run_polling(30, 10_000)
    finally:
        await close_db()


async def main2():

    """await Comp.create(
        spots = 5,
        minimum_buy = 10000,
        name = "Strict Competition Test 1",
        maximum_buy = 5,
        winners = 5,
        prize = 10000,
        strict = True
    )
    f = await Comp.filter()
    a = await f[-1].get_participants()
    print(f[-1].spots, a)
    """
    #f[-1].spots -= 1
    #await f[-1].save()
    await asy.gather(
        fetcher.run_polling(5, 10000),  # Blockchain poller
        
    )
    


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