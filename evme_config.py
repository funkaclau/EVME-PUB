

from settings import *
# main (excerpt)
from aux_funcs import my_func as handle_swap, handle_transfer, lp_mint
from evme import AsyncEVME

kensei = "0xfB889425B72c97C5b4484cF148AE2404AB7A13e7"
kensei_lp = "0x2f4Cdf4ad2203D5bcA9CCB5485727D89603e2E39"

kiddo = "0x2835Ad9a421C14E1C571a5Bb492B86b7E8f5873A"

moonshot = "0x7B616Cb032CaC2572bceC4ECAE68554609e75e1e"
moonshot_lp = "0x6016c8d74756C24DB1d36AeC5B4ea41582d01FB1"

sscl = "0xeFA580ec3F6bb02FD75AcAeD7112d95297a36639"
sscl_lp = "0x522d5AEa9a4D512348cE0A3734bA866421c028f4"

sds = "0xF7B264B723059a05fBf13E32783F88db33A24365"
sds_lp ="0x258b4Bd56428c97EcAC4903C1cBa6303254d1c48"

zeroxdead = "0x796F48d17d38E5f0A7aFe7966448828bdc13e8B1"
zeroxdead_lp = "0x2aCe39961C52D513AE0893891cf22eFb2173d78b"

monkey = "0x525d1e8Df8889A2E8d40bE24d8A21d18Ec161f7F"
monkey_lp = "0xc57e71F33C2Ce6FDcC6535F2d62e045053C10C91"

shibo ="0x10808137849E3Ed8860Da01CAD376B03889684Ef"
shibo_lp ="0xa4A708B96A513113d30C4a09F410E28F10bdB147"
CONTRACT_ABI_MAP = {
    KIDDO_LP: ABI_FILES["lp_pair_abi"],
    msmoon_lp: ABI_FILES["lp_pair_abi"], #21073537
    msmoon: ABI_FILES["erc20_abi"],
    moonshot_lp: ABI_FILES["lp_pair_abi"], #  last 21075290
    moonshot: ABI_FILES["erc20_abi"],
    sscl_lp: ABI_FILES["lp_pair_abi"], # start at 20885477 / last 21075616
    sscl: ABI_FILES["erc20_abi"],
    sds_lp: ABI_FILES["lp_pair_abi"], #21073537
    sds: ABI_FILES["erc20_abi"],
    monkey: ABI_FILES["erc20_abi"], # starts 19903684
    monkey_lp: ABI_FILES["lp_pair_abi"], 
    shibo: ABI_FILES["erc20_abi"], # starts 19903684
    shibo_lp: ABI_FILES["lp_pair_abi"], 

}

CONTRACT_EVENT_MAP = {
    monkey_lp: {
        "Swap": handle_swap,
        "Mint": lp_mint,
    },
    monkey: {
        "Transfer": handle_transfer,
    },
}

fetcher = AsyncEVME(
    rpc_urls=[RPC2, RPC],
    contracts=CONTRACT_ABI_MAP,
    event_callbacks=CONTRACT_EVENT_MAP,
    start_blocks_ago=1000,
    start_from_block=19903684,
    persistence_file="/mnt/usb/RPI4/KIDDO/last_block.json"
)

