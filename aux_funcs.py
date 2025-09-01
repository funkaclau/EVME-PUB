from __future__ import annotations
import os
from decimal import Decimal, getcontext
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from web3 import Web3
from tortoise.exceptions import IntegrityError

from store.models import Token, Pool, Swap, Transfer  # your Tortoise models

getcontext().prec = 60

# ---------------------------------------------------------------------
# Web3 singleton
# ---------------------------------------------------------------------
_W3: Optional[Web3] = None

def get_w3() -> Web3:
    """
    Return a cached Web3. Tries ENV RPC_URLS (comma-separated) first,
    then sane defaults.
    """
    global _W3
    if _W3 is not None:
        return _W3

    urls = os.environ.get("RPC_URLS", "").strip()
    candidates = [u.strip() for u in urls.split(",") if u.strip()] if urls else [
        "https://evm.shidoscan.net/",
        "https://rpc-nodes.shidoscan.com",
    ]
    for url in candidates:
        w3 = Web3(Web3.HTTPProvider(url))
        try:
            if w3.is_connected():
                _W3 = w3
                break
        except Exception:
            pass
    if _W3 is None:
        raise RuntimeError("No RPC reachable. Set RPC_URLS or fix defaults.")
    return _W3

# ---------------------------------------------------------------------
# Minimal ABIs / caches
# ---------------------------------------------------------------------
ERC20_ABI = [
    {"name": "symbol",   "outputs":[{"type":"string"}], "inputs":[], "stateMutability":"view", "type":"function"},
    {"name": "decimals", "outputs":[{"type":"uint8"}],  "inputs":[], "stateMutability":"view", "type":"function"},
]

POOL_ABI = [
    {"name":"token0","outputs":[{"type":"address"}],"inputs":[],"stateMutability":"view","type":"function"},
    {"name":"token1","outputs":[{"type":"address"}],"inputs":[],"stateMutability":"view","type":"function"},
    {"name":"fee",   "outputs":[{"type":"uint24"}],    "inputs":[],"stateMutability":"view","type":"function"},
]

_TOKEN_META: Dict[str, Tuple[str,int]] = {}   # token -> (symbol, decimals)
_POOL_TOKENS: Dict[str, Tuple[str,str,Optional[int]]] = {}  # pool -> (t0, t1, fee or None)
_BLOCK_TS: Dict[int, datetime] = {}           # blockNumber -> aware datetime

def _short(x: str, n=6) -> str:
    x = x.lower()
    return f"{x[:2+n]}…{x[-n:]}"

def _block_ts(w3: Web3, block_number: int) -> datetime:
    ts = _BLOCK_TS.get(block_number)
    if ts is None:
        b = w3.eth.get_block(block_number)
        ts = datetime.fromtimestamp(int(b.timestamp), timezone.utc)
        _BLOCK_TS[block_number] = ts
        # keep cache bounded
        if len(_BLOCK_TS) > 4096:
            _BLOCK_TS.clear()
    return ts

def _erc20_meta(w3: Web3, addr: str) -> Tuple[str, int]:
    addr = Web3.to_checksum_address(addr)
    if addr in _TOKEN_META:
        return _TOKEN_META[addr]
    c = w3.eth.contract(address=addr, abi=ERC20_ABI)
    sym = c.functions.symbol().call()
    # handle weird bytes32 symbols if any
    if isinstance(sym, (bytes, bytearray)):
        try:
            sym = sym.decode("utf-8").rstrip("\x00")
        except Exception:
            sym = sym.hex()
    dec = int(c.functions.decimals().call())
    _TOKEN_META[addr] = (sym, dec)
    return sym, dec

def _pool_meta(w3: Web3, pool: str) -> Tuple[str, str, Optional[int]]:
    pool = Web3.to_checksum_address(pool)
    if pool in _POOL_TOKENS:
        return _POOL_TOKENS[pool]
    c = w3.eth.contract(address=pool, abi=POOL_ABI)
    t0 = Web3.to_checksum_address(c.functions.token0().call())
    t1 = Web3.to_checksum_address(c.functions.token1().call())
    fee: Optional[int] = None
    try:
        fee = int(c.functions.fee().call())
    except Exception:
        fee = None
    _POOL_TOKENS[pool] = (t0, t1, fee)
    return t0, t1, fee

# ---------------------------------------------------------------------
# DB upserters (async)
# ---------------------------------------------------------------------
async def _get_or_create_token(w3: Web3, addr: str) -> Token:
    addr = Web3.to_checksum_address(addr)
    tok = await Token.get_or_none(address=addr)
    if tok:
        # backfill meta if missing
        if tok.symbol is None or tok.decimals is None:
            sym, dec = _erc20_meta(w3, addr)
            tok.symbol, tok.decimals = sym, dec
            await tok.save()
        return tok
    sym, dec = _erc20_meta(w3, addr)
    tok = await Token.create(address=addr, symbol=sym, decimals=dec)
    return tok

async def _get_or_create_pool(w3: Web3, pool_addr: str) -> Pool:
    pool_addr = Web3.to_checksum_address(pool_addr)

    # get_or_none returns instance or None; use fetch_related on instance
    p = await Pool.get_or_none(address=pool_addr)
    if p:
        await p.fetch_related("token0", "token1")
        return p

    t0_addr, t1_addr, fee = _pool_meta(w3, pool_addr)
    t0 = await _get_or_create_token(w3, t0_addr)
    t1 = await _get_or_create_token(w3, t1_addr)
    p = await Pool.create(address=pool_addr, token0=t0, token1=t1, fee=fee)
    return p

def _evt_get(e: Any, key: str, default=None):
    """
    Access helper that works with AttributeDict or dict.
    """
    try:
        return e[key]
    except Exception:
        return getattr(e, key, default)

def _args_get(e: Any, key: str, default=None):
    a = _evt_get(e, "args", {})
    if isinstance(a, dict):
        return a.get(key, default)
    # AttributeDict-like .args
    return getattr(a, key, default)

# ---------------------------------------------------------------------
# ASYNC HANDLERS (wire these in your CONTRACT_EVENT_MAP)
# ---------------------------------------------------------------------
async def my_func(evt: Any, **kwargs) -> None:
    """
    Uniswap V3 Swap event handler (async).
    Saves into DB (Pool/Token upserted automatically).
    """
    w3 = get_w3()

    pool_addr   = Web3.to_checksum_address(_evt_get(evt, "address"))
    block_num   = int(_evt_get(evt, "blockNumber"))
    log_index   = int(_evt_get(evt, "logIndex"))
    tx_hash_hex = _evt_get(evt, "transactionHash")
    if hasattr(tx_hash_hex, "hex"):
        tx_hash_hex = tx_hash_hex.hex()

    sender    = _args_get(evt, "sender")
    recipient = _args_get(evt, "recipient")
    amount0   = _args_get(evt, "amount0")
    amount1   = _args_get(evt, "amount1")
    amount0_i = int(amount0)
    amount1_i = int(amount1)

    amount0_str = str(amount0_i)
    amount1_str = str(amount1_i)
    sqrtP     = _args_get(evt, "sqrtPriceX96")
    liq       = _args_get(evt, "liquidity")
    tick      = _args_get(evt, "tick")

    # ensure pool + tokens exist
    pool = await _get_or_create_pool(w3, pool_addr)

    # block timestamp
    ts = _block_ts(w3, block_num)

    # insert (idempotent by unique (tx_hash, log_index))
    try:
        await Swap.create(
            pool=pool,
            block_number=block_num,
            tx_hash=tx_hash_hex,
            log_index=log_index,
            sender=Web3.to_checksum_address(sender) if sender else None,
            recipient=Web3.to_checksum_address(recipient) if recipient else None,
            amount0_raw=amount0_str,
            amount1_raw=amount1_str,
            sqrt_price_x96=str(int(sqrtP)) if sqrtP is not None else "0",
            liquidity=str(int(liq)) if liq is not None else "0",
            tick=int(tick) if tick is not None else None,
            ts=ts,
        )
    except IntegrityError:
        # already inserted; you could update fields if you want
        pass
    except Exception as e:
        print(
            f"[Swap][ERROR] blk {block_num} tx {tx_hash_hex} log {log_index} "
            f"pool {pool_addr} err={type(e).__name__}: {e}"
        )

    # tiny console breadcrumb (optional)
    dir_str = "t0→t1" if (amount0_i > 0 and amount1_i < 0) else ("t1→t0" if (amount1_i > 0 and amount0_i < 0) else "?")
    print(f"[Swap] blk {block_num} | pool {_short(pool_addr)} | {dir_str} | a0={amount0_str} a1={amount1_str}")

async def handle_transfer(evt: Any, **kwargs) -> None:
    """
    ERC-20 Transfer event handler (async).
    Saves into DB (Token upserted automatically).
    """
    w3 = get_w3()

    token_addr = Web3.to_checksum_address(_evt_get(evt, "address"))
    block_num  = int(_evt_get(evt, "blockNumber"))
    log_index  = int(_evt_get(evt, "logIndex"))
    tx_hash_hex = _evt_get(evt, "transactionHash")
    if hasattr(tx_hash_hex, "hex"):
        tx_hash_hex = tx_hash_hex.hex()

    from_addr = _args_get(evt, "from")
    to_addr   = _args_get(evt, "to")
    value_raw = _args_get(evt, "value")
    # normalize to int -> then to str to avoid bigint overflow in DB
    value_str = str(int(value_raw))

    token = await _get_or_create_token(w3, token_addr)
    ts = _block_ts(w3, block_num)

    try:
        await Transfer.create(
            token=token,
            block_number=block_num,
            tx_hash=tx_hash_hex,
            log_index=log_index,
            from_addr=Web3.to_checksum_address(from_addr),
            to_addr=Web3.to_checksum_address(to_addr),
            value_raw=value_str,
            ts=ts,
        )
    except IntegrityError:
        pass
    except Exception as e:
        print(
            f"[Transfer][ERROR] blk {block_num} tx {tx_hash_hex} log {log_index} "
            f"token {token_addr} err={type(e).__name__}: {e}"
        )

    # tiny console breadcrumb (optional)
    sym = token.symbol or "?"
    print(f"[Transfer] blk {block_num} | {_short(token_addr)} {sym}: {_short(from_addr)} → {_short(to_addr)} | value={value_str}")

# Optional stub to keep your map happy if you still route "Mint"
async def lp_mint(evt: Any, **kwargs) -> None:
    w3 = get_w3()
    pool_addr = Web3.to_checksum_address(_evt_get(evt, "address"))
    await _get_or_create_pool(w3, pool_addr)
    print(f"[Mint] blk {_evt_get(evt,'blockNumber')} | pool {_short(pool_addr)}")

# ---------------------------------------------------------------------
# Debug / sanity helpers
# ---------------------------------------------------------------------
async def print_last_swaps(pool_addr: str, limit: int = 5):
    """
    Quick sanity check: print the last N swaps for a pool.
    """
    pool_addr = Web3.to_checksum_address(pool_addr)
    p = await Pool.get_or_none(address=pool_addr)
    if not p:
        print(f"Pool not found: {pool_addr}")
        return
    swaps = await Swap.filter(pool=p).order_by("-block_number", "-log_index").limit(limit)
    print(f"Last {len(swaps)} swaps for {pool_addr}:")
    for s in swaps:
        print(f" • blk {s.block_number} | tx {s.tx_hash}#{s.log_index} | a0={s.amount0_raw} a1={s.amount1_raw}")
