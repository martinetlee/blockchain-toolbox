#!/usr/bin/env python3

import os
import csv
import json
from typing import List, Dict, Set
from web3 import Web3
from web3.middleware import geth_poa_middleware
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Debug prints to verify environment variables
print("Environment variables loaded:")
print(f"RPC_URL: {os.getenv('RPC_URL')}")
print(f"TOKEN_ADDRESS: {os.getenv('TOKEN_ADDRESS')}")
print(f"DEX_ADDRESSES_FILE: {os.getenv('DEX_ADDRESSES_FILE')}")
print(f"USER_ADDRESSES_FILE: {os.getenv('USER_ADDRESSES_FILE')}")
print(f"FROM_BLOCK: {os.getenv('FROM_BLOCK')}")

# ERC20 Transfer event signature
TRANSFER_EVENT_SIGNATURE = "Transfer(address,address,uint256)"
TRANSFER_EVENT_HASH = Web3.keccak(text=TRANSFER_EVENT_SIGNATURE).hex()

# ERC20 ABI for decimals
ERC20_ABI = json.loads('''[
    {
        "constant": true,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    }
]''')

def get_all_transfer_events(w3: Web3, token_address: str, from_block: int = 0) -> List[Dict]:
    """Get all transfer events for the token."""
    events = []
    current_block = from_block
    batch_size = 500  # Adjust based on RPC provider limits
    latest_block = w3.eth.block_number
    
    print(f"From block number: {current_block}")
    print(f"Latest block number: {latest_block}")
    
    # Time tracking variables
    start_time = datetime.now()
    last_progress_time = start_time
    blocks_processed = 0
    
    while True:
        end_block = min(current_block + batch_size, latest_block)
        progress = ((current_block - from_block) / (latest_block - from_block)) * 100
        
        # Calculate time estimates
        current_time = datetime.now()
        elapsed_time = (current_time - start_time).total_seconds()
        blocks_processed = current_block - from_block
        if blocks_processed > 0:
            blocks_per_second = blocks_processed / elapsed_time
            remaining_blocks = latest_block - current_block
            estimated_remaining_seconds = remaining_blocks / blocks_per_second if blocks_per_second > 0 else 0
            estimated_completion_time = current_time + timedelta(seconds=estimated_remaining_seconds)
            
            print(f"Processing from block {current_block} to {end_block} ({progress:.2f}% done)")
            print(f"Processing speed: {blocks_per_second:.2f} blocks/second")
            print(f"Estimated completion time: {estimated_completion_time.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print(f"Processing from block {current_block} to {end_block} ({progress:.2f}% done)")

        try:
            # Get transfer events using get_logs instead of filter
            logs = w3.eth.get_logs({
                'fromBlock': current_block,
                'toBlock': end_block,
                'address': token_address,
                'topics': [TRANSFER_EVENT_HASH]
            })
            
            # Process events
            for event in logs:
                topics = event['topics']
                if len(topics) >= 3:
                    from_address = w3.to_checksum_address('0x' + topics[1].hex()[-40:])
                    to_address = w3.to_checksum_address('0x' + topics[2].hex()[-40:])
                    # Convert bytes data to hex string before parsing
                    amount = int(event['data'].hex(), 16)
                    block_number = event['blockNumber']
                    # Get block timestamp
                    block = w3.eth.get_block(block_number)
                    timestamp = datetime.fromtimestamp(block['timestamp'])
                    events.append({
                        'from': from_address,
                        'to': to_address,
                        'amount': amount,
                        'block_number': block_number,
                        'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S')
                    })
            
            if end_block >= latest_block:
                break
                
            current_block = end_block + 1
            
        except Exception as e:
            print(f"Error processing blocks {current_block} to {end_block}: {str(e)}")
            # If we hit an error, try with a smaller batch size
            if batch_size > 1000:
                batch_size = batch_size // 2
                print(f"Reducing batch size to {batch_size}")
                continue
            else:
                print("Batch size too small, skipping these blocks")
                current_block = end_block + 1
                batch_size = 20000  # Reset batch size for next attempt
    
    return events

def save_transfer_events(events: List[Dict], token_address: str, latest_block: int, chain_id: int):
    """Save transfer events to a CSV file."""
    filename = f"{token_address}_all_transfer_events_chain_{chain_id}_block_{latest_block}.csv"
    with open(filename, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['from', 'to', 'amount', 'block_number', 'timestamp'])
        writer.writeheader()
        writer.writerows(events)
    print(f"Saved {len(events)} transfer events to {filename}")

def get_latest_recorded_block(token_address: str, chain_id: int) -> int:
    """Read the latest recorded block from the event log record file."""
    try:
        with open('event_log_record.json', 'r') as f:
            records = json.load(f)
            key = f"{token_address}_{chain_id}"
            print(f"{records[key]}")
            if key in records:
                return records[key]['latest_block']
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        pass
    return 0

def update_event_log_record(token_address: str, chain_id: int, latest_block: int):
    """Update the event log record with the latest block number."""
    try:
        records = {}
        try:
            with open('event_log_record.json', 'r') as f:
                records = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        
        key = f"{token_address}_{chain_id}"
        records[key] = {
            'latest_block': latest_block,
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        with open('event_log_record.json', 'w') as f:
            json.dump(records, f, indent=2)
    except Exception as e:
        print(f"Error updating event log record: {str(e)}")

def load_transfer_events(token_address: str, chain_id: int) -> List[Dict]:
    """Load transfer events from the most recent CSV file and fetch new events if needed."""
    # Find the most recent file
    files = [f for f in os.listdir('.') if f.startswith(f"{token_address}_all_transfer_events_chain_{chain_id}_block_")]
    if not files:
        return []
    
    latest_file = max(files)
    events = []
    with open(latest_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            events.append({
                'from': row['from'],
                'to': row['to'],
                'amount': int(row['amount']),
                'block_number': int(row['block_number']),
                'timestamp': row['timestamp']
            })
    
    # Get the latest recorded block
    latest_recorded_block = get_latest_recorded_block(token_address, chain_id)
    
    # Initialize Web3
    w3 = Web3(Web3.HTTPProvider(os.getenv('RPC_URL')))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    current_latest_block = w3.eth.block_number
    
    # If we have new blocks to process
    if (latest_recorded_block < current_latest_block): # add and False to skip this part and process directly without getting new blocks
        print(f"Found new blocks from {latest_recorded_block} to {current_latest_block}")
        new_events = get_all_transfer_events(w3, token_address, from_block=latest_recorded_block + 1)
        events.extend(new_events)
        
        # Save updated events
        save_transfer_events(events, token_address, current_latest_block, chain_id)
        # Update the event log record
        update_event_log_record(token_address, chain_id, current_latest_block)
    
    print(f"Loaded {len(events)} transfer events from {latest_file}")
    return events

def process_transfer_events(events: List[Dict], dex_addresses: Set[str], user_addresses: Set[str], decimals: int) -> List[Dict]:
    """Process transfer events and label them according to the rules."""
    processed_events = []
    
    for event in events:
        from_address = event['from']
        to_address = event['to']
        amount = event['amount'] / (10 ** decimals)
        
        # Determine if addresses are DEX or user addresses
        from_is_dex = from_address in dex_addresses
        to_is_dex = to_address in dex_addresses
        from_is_user = from_address in user_addresses
        to_is_user = to_address in user_addresses
        
        # Apply labeling rules
        if from_is_dex and to_is_user:
            label = "Buy"
        elif from_is_user and to_is_dex:
            label = "Sell"
        elif from_is_user and to_is_user:
            label = "Transfer within"
        elif to_is_user:
            label = "Input unknown"
        elif from_is_user:
            label = "Output unknown"
        else:
            continue  # Skip if neither address is relevant
        
        processed_events.append({
            'label': label,
            'amount': amount,
            'from': from_address,
            'to': to_address,
            'block_number': event['block_number'],
            'timestamp': event['timestamp']
        })
    
    return processed_events

def save_trade_history(events: List[Dict], token_address: str, chain_id: int):
    """Save processed trade history to a CSV file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{token_address}_trade_history_chain_{chain_id}_{timestamp}.csv"
    
    with open(filename, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['label', 'amount', 'from', 'to', 'block_number', 'timestamp'])
        writer.writeheader()
        writer.writerows(events)
    
    print(f"Saved trade history to {filename}")

def main():
    # Get configuration from environment variables
    rpc_url = os.getenv('RPC_URL')
    token_address = os.getenv('TOKEN_ADDRESS')
    dex_addresses_file = os.getenv('DEX_ADDRESSES_FILE')
    user_addresses_file = os.getenv('USER_ADDRESSES_FILE')
    from_block = int(os.getenv('FROM_BLOCK', '0'))  # Default to 0 if not specified
    
    if not all([rpc_url, token_address, dex_addresses_file, user_addresses_file]):
        print("Please ensure all required variables are set in .env file:")
        print("RPC_URL - Your RPC endpoint")
        print("TOKEN_ADDRESS - The token contract address")
        print("DEX_ADDRESSES_FILE - Path to file containing DEX addresses")
        print("USER_ADDRESSES_FILE - Path to file containing user addresses")
        print("FROM_BLOCK (optional) - Starting block number")
        return
    
    # Initialize Web3
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    
    if not w3.is_connected():
        print("Failed to connect to the RPC endpoint")
        return
    
    # Get chain ID
    chain_id = w3.eth.chain_id
    print(f"Connected to chain ID: {chain_id}")
    
    # Load addresses
    with open(dex_addresses_file, 'r') as f:
        dex_addresses = {w3.to_checksum_address(line.strip()) for line in f if line.strip()}
    
    with open(user_addresses_file, 'r') as f:
        user_addresses = {w3.to_checksum_address(line.strip()) for line in f if line.strip()}
    
    # Get token decimals
    token_contract = w3.eth.contract(address=token_address, abi=ERC20_ABI)
    decimals = token_contract.functions.decimals().call()
    
    # Try to load existing transfer events
    events = load_transfer_events(token_address, chain_id)
    
    # If no existing events, fetch them
    if not events:
        print(f"No existing transfer events found. Fetching from blockchain starting from block {from_block}...")
        events = get_all_transfer_events(w3, token_address, from_block=from_block)
        save_transfer_events(events, token_address, w3.eth.block_number, chain_id)
    
    # Process events
    print("Processing transfer events...")
    processed_events = process_transfer_events(events, dex_addresses, user_addresses, decimals)
    
    # Save trade history
    save_trade_history(processed_events, token_address, chain_id)

if __name__ == "__main__":
    main() 