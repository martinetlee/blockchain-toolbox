#!/usr/bin/env python3

import os
import csv
from datetime import datetime
from typing import List, Dict, Set
from web3 import Web3
from web3.middleware import geth_poa_middleware
import json

# ERC20 Transfer event signature
TRANSFER_EVENT_SIGNATURE = "Transfer(address,address,uint256)"
TRANSFER_EVENT_HASH = Web3.keccak(text=TRANSFER_EVENT_SIGNATURE).hex()

# ERC20 ABI for balance checking
ERC20_ABI = json.loads('''[
    {
        "constant": true,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": true,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    },
    {
        "constant": true,
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    }
]''')

def get_all_transfer_events(w3: Web3, token_address: str, from_block: int = 0) -> Set[str]:
    """Get all addresses involved in transfer events."""
    addresses = set()
    current_block = from_block
    batch_size = 2000  # Adjust based on RPC provider limits
    latest_block = w3.eth.block_number
    address_count = 0
    
    print(f"Latest block number: {latest_block}")

    while True:
        end_block = min(current_block + batch_size, latest_block)
        progress = ((current_block - from_block) / (latest_block - from_block)) * 100
        print(f"Processing from block {current_block} to {end_block} ({progress:.2f}% done)")

        # Get transfer events
        transfer_filter = w3.eth.filter({
            'fromBlock': current_block,
            'toBlock': end_block,
            'address': token_address,
            'topics': [TRANSFER_EVENT_HASH]
        })
        
        events = transfer_filter.get_all_entries()
        
        # Extract addresses from events
        for event in events:
            # Decode the event data
            topics = event['topics']
            if len(topics) >= 3:
                from_address = '0x' + topics[1].hex()[-40:]
                to_address = '0x' + topics[2].hex()[-40:]
                # Convert to checksum addresses
                addresses.add(w3.to_checksum_address(from_address))
                addresses.add(w3.to_checksum_address(to_address))
        
        if end_block >= latest_block:
            break
            
        current_block = end_block + 1
        
    return addresses

def get_balances(w3: Web3, token_address: str, addresses: Set[str]) -> List[Dict]:
    """Get current balances for all addresses."""
    token_contract = w3.eth.contract(address=token_address, abi=ERC20_ABI)
    total_supply = token_contract.functions.totalSupply().call()
    decimals = token_contract.functions.decimals().call()
    
    balances = []
    address_count = 0
    total_addresses = len(addresses)
    
    for address in addresses:
        try:
            balance = token_contract.functions.balanceOf(address).call()
            if balance > 0:
                percentage = (balance / total_supply) * 100
                balances.append({
                    'address': address,
                    'balance': balance / (10 ** decimals),
                    'percentage': percentage
                })
        except Exception as e:
            print(f"Error getting balance for {address}: {str(e)}")
        
        address_count += 1
        if address_count % 100 == 0:
            progress = (address_count / total_addresses) * 100
            print(f"Processed {address_count}/{total_addresses} addresses ({progress:.2f}% done)")
    
    return sorted(balances, key=lambda x: x['balance'], reverse=True)

def save_to_csv(balances: List[Dict], chain_id: int, token_address: str):
    """Save balances to a CSV file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"token_holders_{chain_id}_{token_address}_{timestamp}.csv"
    
    with open(filename, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['address', 'balance', 'percentage'])
        writer.writeheader()
        writer.writerows(balances)
    
    print(f"Results saved to {filename}")

def main():
    # Get configuration from environment variables
    rpc_url = os.getenv('RPC_URL')
    token_address = os.getenv('TOKEN_ADDRESS')
    from_block = int(os.getenv('FROM_BLOCK', '0'))  # Default to 0 if not specified
    
    if not rpc_url or not token_address:
        print("Please set RPC_URL and TOKEN_ADDRESS environment variables")
        return
    
    # Initialize Web3
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    
    if not w3.is_connected():
        print("Failed to connect to the RPC endpoint")
        return
    
    # Get chain ID
    chain_id = w3.eth.chain_id
    
    print(f"Getting transfer events for token {token_address} from block {from_block}...")
    addresses = get_all_transfer_events(w3, token_address, from_block=from_block)
    print(f"Found {len(addresses)} addresses involved in transfers")
    
    print("Getting current balances...")
    balances = get_balances(w3, token_address, addresses)
    print(f"Found {len(balances)} addresses with non-zero balances")
    
    save_to_csv(balances, chain_id, token_address)

if __name__ == "__main__":
    main()
