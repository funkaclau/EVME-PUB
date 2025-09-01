# store/helpers.py
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, Tuple
from tortoise.exceptions import IntegrityError
from web3 import Web3
from .models import Token, Pool, Swap, Transfer

# Simple in-process caches
_token_cache: dict[str, int] = {}
_pool_cache: dict[str, int] = {}
_block_ts_cache: dict[int, datetime] = {}

ERC20_ABI = [
    {"name": "symbol", "outputs":[{"type":"string"}],"inputs":[],"stateMutability":"view","type":"function"},
    {"name": "decimals","outputs":[{"type":"uint8"}],"inputs":[],"stateMutability":"view","type":"function"},
]
POOL_ABI = [
    {"name":"token0","outputs":[{"type":"address"}],"inputs":[],"stateMutability":"view","type":"function"},
    {"name":"token1","outputs":[{"type":"address"}],"inputs":[],"stateMutability":"view","type":"function"},
    {"name":"fee","outputs":[{"type":"uint24"}],"inputs":[],"stateMutability":"view","type":"function"},
]

async def ensure_token(w3: Web3, addr: str) -> Token:
    addr = Web3.to_checksum_address(addr)
    if addr in _token_cache:
        return await Token.get(id=_token_cache[addr])
    tok = await Token.get_or_none(address=addr)
    if tok is None:
        # Try fetch meta but don’t die if it fails
        symbol, decimals = None, None
        try:
            c = w3.eth.contract(address=addr, abi=ERC20_ABI)
            symbol = c.functions.symbol().call()
            decimals = int(c.functions.decimals().call())
        except Exception:
            pass
        tok = await Token.create(address=addr, symbol=symbol, decimals=decimals)
    _token_cache[addr] = tok.id
    return tok

async def ensure_pool(w3: Web3, pool_addr: str) -> Pool:
    pool_addr = Web3.to_checksum_address(pool_addr)
    if pool_addr in _pool_cache:
        return await Pool.get(id=_pool_cache[pool_addr])

    p = await Pool.get_or_none(address=pool_addr)
    if p is None:
        # fetch token0/1 (+ fee if available)
        c = w3.eth.contract(address=pool_addr, abi=POOL_ABI)
        t0 = c.functions.token0().call()
        t1 = c.functions.token1().call()
        fee = None
        try:
            fee = int(c.functions.fee().call())
        except Exception:
            pass
        tok0 = await ensure_token(w3, t0)
        tok1 = await ensure_token(w3, t1)
        p = await Pool.create(address=pool_addr, token0=tok0, token1=tok1, fee=fee)

    _pool_cache[pool_addr] = p.id
    return p

def _coerce_event(evt: Dict[str, Any]) -> Dict[str, Any]:
    e = dict(evt)
    if "transactionHash" in e and not isinstance(e["transactionHash"], str):
        try:
            e["transactionHash"] = e["transactionHash"].hex()
        except Exception:
            e["transactionHash"] = str(e["transactionHash"])
    if "address" in e and isinstance(e["address"], str):
        e["address"] = Web3.to_checksum_address(e["address"])
    return e

def _block_ts(w3: Web3, block_number: int) -> datetime:
    ts = _block_ts_cache.get(block_number)
    if ts is None:
        b = w3.eth.get_block(block_number)
        ts = datetime.fromtimestamp(int(b.timestamp), tz=timezone.utc)
        _block_ts_cache[block_number] = ts
        if len(_block_ts_cache) > 4096:
            _block_ts_cache.clear()
    return ts

async def insert_swap_event(w3: Web3, evt: Dict[str, Any]) -> Tuple[Swap | None, bool]:
    """
    Returns (obj, created). Swallows duplicate via unique key (tx_hash, log_index).
    """
    e = _coerce_event(evt)
    args = e.get("args", {})
    pool_addr = e["address"]
    pool = await ensure_pool(w3, pool_addr)

    try:
        obj = await Swap.create(
            pool=pool,
            block_number=int(e["blockNumber"]),
            tx_hash=e["transactionHash"],
            log_index=int(e["logIndex"]),
            sender=args.get("sender"),
            recipient=args.get("recipient"),
            amount0_raw=int(args.get("amount0", 0)),
            amount1_raw=int(args.get("amount1", 0)),
            sqrt_price_x96=str(args.get("sqrtPriceX96", "")),
            liquidity=str(args.get("liquidity", "")),
            tick=int(args.get("tick", 0)) if args.get("tick") is not None else None,
            ts=_block_ts(w3, int(e["blockNumber"])),
        )
        return obj, True
    except IntegrityError:
        return await Swap.get_or_none(tx_hash=e["transactionHash"], log_index=int(e["logIndex"])), False

async def insert_transfer_event(w3: Web3, evt: Dict[str, Any]) -> Tuple[Transfer | None, bool]:
    e = _coerce_event(evt)
    args = e.get("args", {})
    token_addr = e["address"]
    tok = await ensure_token(w3, token_addr)

    try:
        obj = await Transfer.create(
            token=tok,
            block_number=int(e["blockNumber"]),
            tx_hash=e["transactionHash"],
            log_index=int(e["logIndex"]),
            from_addr=args.get("from"),
            to_addr=args.get("to"),
            value_raw=str(int(args.get("value", 0))),
            ts=_block_ts(w3, int(e["blockNumber"])),
        )
        return obj, True
    except IntegrityError:
        return await Transfer.get_or_none(tx_hash=e["transactionHash"], log_index=int(e["logIndex"])), False
