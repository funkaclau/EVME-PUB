import json
RPI = False

abi_list = [
    "erc20_abi",
    #"stash_abi",
    #"seedround_abi",
    #"batch_abi",
    #"tagbattle_abi",
    #"staking_og_abi",
    #"staking_shido_dex_abi",
    "lp_pair_abi",
    #"ah_abi"
]

def rpi(path):
    return "/mnt/usb/RPI4/KIDDO2/settings/abi/" + path 

def get_abi(filename):

    with open(f"./abi/{filename}.json" if not RPI else rpi(f"{filename}.json")) as f:
        return json.load(f)
        
def get_abis():
    return {i: get_abi(i) for i in abi_list}

ABI_FILES = get_abis()