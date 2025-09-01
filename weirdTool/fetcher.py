from typing import Iterable, List, Optional, Dict, Any, Tuple, Callable
from dataclasses import dataclass
from time import sleep
from web3 import Web3
from web3._utils.events import get_event_data
from hexbytes import HexBytes

SWAP_EVENT_ABI = {
    "anonymous": False,
    "inputs": [
        {"indexed": True,  "name": "sender",    "type": "address"},
        {"indexed": True,  "name": "recipient", "type": "address"},
        {"indexed": False, "name": "amount0",   "type": "int256"},
        {"indexed": False, "name": "amount1",   "type": "int256"},
        {"indexed": False, "name": "sqrtPriceX96", "type": "uint160"},
        {"indexed": False, "name": "liquidity",    "type": "uint128"},
        {"indexed": False, "name": "tick",         "type": "int24"},
    ],
    "name": "Swap",
    "type": "event",
}

@dataclass
class DecodedSwap:
    pool: str
    blockNumber: int
    txHash: str
    logIndex: int
    sender: str
    recipient: str
    amount0: int
    amount1: int
    sqrtPriceX96: int
    liquidity: int
    tick: int

def _topic0_for_swap(w3: Web3) -> HexBytes:
    return w3.keccak(text="Swap(address,address,int256,int256,uint160,uint128,int24)")

def _topic_addr(addr: str) -> str:
    a = Web3.to_checksum_address(addr)
    return "0x" + "00"*12 + a.lower().replace("0x","")

def _decode_swap(w3: Web3, log: Dict[str, Any]) -> DecodedSwap:
    ev = get_event_data(w3.codec, SWAP_EVENT_ABI, log)
    args = ev["args"]
    return DecodedSwap(
        pool=log["address"],
        blockNumber=log["blockNumber"],
        txHash=ev["transactionHash"].hex(),
        logIndex=log["logIndex"],
        sender=args["sender"],
        recipient=args["recipient"],
        amount0=int(args["amount0"]),
        amount1=int(args["amount1"]),
        sqrtPriceX96=int(args["sqrtPriceX96"]),
        liquidity=int(args["liquidity"]),
        tick=int(args["tick"]),
    )

def get_swaps_multi(
    w3: Web3,
    pools: Iterable[str],
    *,
    user: Optional[str] = None,           # filter by user address
    role: str = "any",                     # "sender" | "recipient" | "any"
    from_block: int = 0,
    to_block: int | str = "latest",
    block_span: Optional[int] = 5000,
    verbose: bool = True,                  # <— progress prints
    retries: int = 3,                      # simple retry per chunk
    sleep_s: float = 0.8,                  # backoff base
) -> List[DecodedSwap]:
    pools = [Web3.to_checksum_address(p) for p in pools]
    topic0 = _topic0_for_swap(w3)
    user_topic = _topic_addr(user) if user else None

    end = w3.eth.block_number if to_block == "latest" else int(to_block)
    start = int(from_block)
    def ranges() -> Iterable[Tuple[int,int]]:
        if not block_span:
            yield start, end
        else:
            cur = start
            while cur <= end:
                hi = min(cur + block_span - 1, end)
                yield cur, hi
                cur = hi + 1

    def fetch_one(pool_addr: str, role_: str) -> List[Dict[str, Any]]:
        logs: List[Dict[str, Any]] = []
        topics = [topic0, None, None]
        if user_topic:
            if role_ == "sender":    topics[1] = user_topic
            elif role_ == "recipient": topics[2] = user_topic
        for lo, hi in ranges():
            attempt = 0
            while True:
                try:
                    flt = {
                        "fromBlock": lo, "toBlock": hi,
                        "address": pool_addr,
                        "topics": topics,
                    }
                    got = w3.eth.get_logs(flt)
                    if verbose:
                        print(f"[{pool_addr[:8]}..] blocks {lo}-{hi} → {len(got)} logs")
                    logs.extend(got)
                    break
                except Exception as e:
                    attempt += 1
                    if attempt > retries:
                        if verbose:
                            print(f"[{pool_addr[:8]}..] blocks {lo}-{hi} ✖ error: {e} (giving up)")
                        break
                    if verbose:
                        print(f"[{pool_addr[:8]}..] blocks {lo}-{hi} ! retry {attempt}/{retries}: {e}")
                    sleep(sleep_s * attempt)
        return logs

    raw_logs: List[Dict[str, Any]] = []
    for pool_addr in pools:
        if user and role == "any":
            raw_logs.extend(fetch_one(pool_addr, "sender"))
            raw_logs.extend(fetch_one(pool_addr, "recipient"))
        else:
            raw_logs.extend(fetch_one(pool_addr, role))

    # Dedup + decode
    seen = set(); decoded: List[DecodedSwap] = []
    for lg in raw_logs:
        key = (lg["transactionHash"].hex(), lg["logIndex"])
        if key in seen: continue
        seen.add(key)
        decoded.append(_decode_swap(w3, lg))

    decoded.sort(key=lambda x: (x.blockNumber, x.logIndex))
    if verbose:
        print(f"Done. total decoded swaps: {len(decoded)}")
    return decoded
