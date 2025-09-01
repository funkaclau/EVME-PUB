from typing import Iterable, List, Optional, Dict, Any, Tuple, Callable
from dataclasses import dataclass
from time import sleep
from web3 import Web3
from weirdTool.fetcher import get_swaps_multi

w3 = Web3(Web3.HTTPProvider("https://evm.shidoscan.net/"))
POOLS = [
    "0x76F2562B8826B14e0F0362724eC3887fbc62FB74",
    "0x26FcCF369656A30Dd792A40037875E55C937e8a8",
    "0x7cf3600309337c77453123FB2e695c508C61Ed12",
    "0x7b65b7cf3c8b20a2c6f034d329b70daf84258e50"
]
swaps = get_swaps_multi(w3, POOLS, user="0x386f4A00d86e783b9a0f83A7A767f6384b94e529", from_block=4_790_000, to_block="latest", block_span=10000, verbose=True)
print("first 3:")
for s in swaps[:3]:
    print(s.blockNumber, s.txHash, s.pool, s.sender, s.recipient, s.amount0, s.amount1)
