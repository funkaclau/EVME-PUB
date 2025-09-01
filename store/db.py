# store/db.py
import os
from typing import Optional
from tortoise import Tortoise, run_async

DEFAULT_DB_URL = os.environ.get("DB_URL", "sqlite://events.sqlite3")
# Examples:
#   SQLite file:  DB_URL="sqlite://events.sqlite3"
#   In-memory:    DB_URL="sqlite://:memory:"
#   Postgres:     DB_URL="postgres://user:pass@localhost:5432/yourdb"

MODELS_MODULES = {"models": ["store.models"]}

async def init_db(db_url: Optional[str] = None, generate_schemas: bool = True) -> None:
    """
    Init Tortoise and (optionally) create tables.
    """
    url = db_url or DEFAULT_DB_URL
    await Tortoise.init(db_url=url, modules=MODELS_MODULES)
    if generate_schemas:
        await Tortoise.generate_schemas(safe=True)
    # Optional: print connection info
    print(f"[db] Connected: {url}")

async def close_db() -> None:
    await Tortoise.close_connections()

# Tiny CLI to create the schema quickly:  python -m store.db
if __name__ == "__main__":
    async def _main():
        await init_db()
        print("[db] Schema ready.")
        await close_db()
    run_async(_main())
