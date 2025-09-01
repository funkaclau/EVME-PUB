
from web3 import Web3
import os
from dotenv import load_dotenv
from abi.get_abis import RPI, ABI_FILES

# Web3 connection to Shido chain
RPC_URL = "https://rpc-nodes.shidoscan.com"

RPC2="https://evm.shidoscan.net/"
RPC = "https://shido-mainnet-archive-lb-nw5es9.zeeve.net/USjg7xqUmCZ4wCsqEOOE/rpc"
w3 = Web3(Web3.HTTPProvider(RPC_URL))

w32 = Web3(Web3.HTTPProvider("https://rpc-testnet-nodes.shidoscan.com"))

seed_round = "0xdD75c1a25C3bc4874C00f33C8639316dc819F34c"
stash = "0x5B73743d6e99E911e6C412C0BcA9a702475F0595"
batch = "0x1AD0D74967d8c91d88D88aA229a5DAf3e46538B6"
stashTest = "0xe5fEf772C4C0c41B709712CFE6B98023e3aEC54F"
presale = "0xC55E8183d69E165aFC0BD315f7725d203EAF8b2f"
staking_og = "0xbf2019c320AD99F7A84664c72599D772C225eF62"
staking_shido_dex = "0x1535A275c26Fa8157094683a049A3F8bF40609B3"
KIDDO = "0x2835Ad9a421C14E1C571a5Bb492B86b7E8f5873A"
lp = "0x76F2562B8826B14e0F0362724eC3887fbc62FB74"
usdclp = "0x499b71f3e427714d286f6c6ba3cab8d1adfa89df"
DEAD = "0x000000000000000000000000000000000000dEaD"
TAG = "0x5cA771A8cB1a51251174A9dfC2f06182d84914F6"
AH = "0x9a7D76dbdE5c60862c34e9A3D067ced2B651E18b"
msmoon = "0x1f5b6F4126575835c23D1b6c38535FA215df03c5"
msmoon_lp = "0x053a0d96eF36433f2ba01b7FFA0d2Ec3B9EFfd9E"
