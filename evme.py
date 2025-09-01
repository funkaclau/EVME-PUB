import asyncio
import logging
import json
import threading
import random
from web3 import Web3
from typing import Callable, Dict, List

def attrdict_to_dict(value):
    """
    Recursively converts AttributeDict (and any nested structures)
    into standard Python dictionaries/lists, so they're JSON-serializable.
    """
    return {
        "trader": value.args.recipient,
        "amount0": value.args.amount0,
        "amount1": value.args.amount1,
        "hash": value.blockHash.hex(),
        "block": value.blockNumber,
    }


class AsyncEVME:
    def __init__(
        self,
        rpc_urls: List[str],  # List of RPC URLs for auto-switching
        contracts: Dict[str, list],  # {contract_address: contract_abi}
        event_callbacks: Dict[str, Dict[str, Callable]],  # {contract_address: {event_name: async_callback}}
        start_blocks_ago: int = 9999,
        start_from_block: int = 0,
        persistence_file: str = None,
    ):
        self.logger = logging.getLogger("AsyncEVME")
        logging.basicConfig(level=logging.INFO)

        self.rpc_urls = rpc_urls
        self.current_rpc = 0
        self.web3 = None
        self.init_web3()

        self.contracts = {
            Web3.to_checksum_address(addr): {
                "abi": abi,
                "contract": self.web3.eth.contract(address=Web3.to_checksum_address(addr), abi=abi),
            }
            for addr, abi in contracts.items()
        }
        self.event_callbacks = event_callbacks
        self.persistence_file = persistence_file
        self.lock = threading.Lock()
        
        current_block = self.web3.eth.block_number
        self.from_block = (
            start_from_block
            if start_from_block
            else max(current_block - start_blocks_ago, 0)
        )
        self.to_block = current_block

        self.event_signatures = self._get_event_signatures()
        self.logger.info("Initialized EventFetcher for multiple contracts")
        self.logger.info(f"Starting from block: {self.from_block}, Current block: {self.to_block}")
        print("LFG", self.event_signatures)

    def init_web3(self):
        """Initialize or reinitialize Web3 connection."""
        try:
            self.web3 = Web3(Web3.HTTPProvider(self.rpc_urls[self.current_rpc], request_kwargs={"timeout": 10}))
            if self.web3.is_connected():
                self.logger.info(f"Connected to RPC: {self.rpc_urls[self.current_rpc]}")
            else:
                self.logger.warning(f"Failed to connect to RPC: {self.rpc_urls[self.current_rpc]}")
                self.switch_rpc()
        except Exception as e:
            self.logger.error(f"Error initializing Web3: {e}")
            self.switch_rpc()

    def switch_rpc(self):
        """Switch to the next RPC in case of failure."""
        self.current_rpc = (self.current_rpc + 1) % len(self.rpc_urls)
        self.logger.warning(f"Switching to next RPC: {self.rpc_urls[self.current_rpc]}")
        self.init_web3()
        
    def _get_event_signatures(self) -> Dict[str, Dict[str, str]]:
        print("Signature")
        signatures = {}
        for contract_address, contract_data in self.contracts.items():
            #print(contract_address)
            
            contract_signatures = {}
            for event_name in self.event_callbacks.get(contract_address, {}):
                #print(event_name)
                for item in contract_data["abi"]:
                    if item.get("type") == "event" and item.get("name") == event_name:
                        inputs = item.get("inputs", [])
                        types = ",".join(inp["type"] for inp in inputs)
                        signature_str = f"{event_name}({types})"
                        contract_signatures[event_name] = "0x" + self.web3.keccak(text=signature_str).hex()
                        #print(contract_signatures[event_name])
                        break
                else:
                    raise ValueError(f"Event {event_name} not found in contract {contract_address} ABI.")
            signatures[contract_address] = contract_signatures
        return signatures

    async def fetch_logs(self, chunk_size=10000, max_retries=3):
        """Fetch logs while ensuring connection stability."""
        self.to_block = self.web3.eth.block_number
        while self.from_block <= self.to_block:
            end_block = min(self.from_block + chunk_size - 1, self.to_block)
            #print(json.dumps(self.event_signatures, indent=4))
            for contract_address, event_data in self.event_signatures.items():
                filter_options = {
                    "fromBlock": self.from_block,
                    "toBlock": end_block,
                    "address": contract_address,
                    "topics": [list(event_data.values())],
                }
                #print(filter_options)
                retries = 0
                while retries <= max_retries:
                    try:
                        logs = self.web3.eth.get_logs(filter_options)
                        if not logs:
                            self.logger.info(f"No logs found in blocks {self.from_block} - {end_block}")
                            break
                        for log in logs:
                            print(log)
                            #print(event_data)
                            for event_name, signature in event_data.items():
                                print("0x" + log["topics"][0].hex().lower(), str(signature.lower()), str("0x"+ log["topics"][0].hex().lower()) == str(signature.lower()))
                                if str("0x"+log["topics"][0].hex())== str(signature.lower()):
                                    decoded = self.contracts[contract_address]["contract"].events[event_name]().process_log(log)
                                    if decoded:
                                        await self.event_callbacks[contract_address][event_name](decoded)
                                    else:
                                        print(f"Unable to decode: {json.dumps(log, indent=4)}")
                                
                        break

                    except Exception as e:
                        retries += 1
                        self.logger.warning(f"RPC failed, switching... {e}")
                        self.switch_rpc()
                        await asyncio.sleep(2 ** retries)

            self.from_block = end_block + 1
            self.logger.info(f"Updated to block: {self.from_block}")
            await asyncio.sleep(random.uniform(4, 10))

    async def run_polling(self, sleep_time=5, chunk_size=2000):
        self.logger.info("Starting event polling...")
        try:
            while True:
                await self.fetch_logs(chunk_size=chunk_size)
                await asyncio.sleep(sleep_time)
        except asyncio.CancelledError:
            self.logger.info("Polling canceled.")
        except KeyboardInterrupt:
            self.logger.info("Polling stopped by user.")
            exit()