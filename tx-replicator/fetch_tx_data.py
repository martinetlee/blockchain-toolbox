import json
import os
from dotenv import load_dotenv
from web3 import Web3

def hex_to_str(obj):
    """Convert HexBytes to string if needed"""
    if isinstance(obj, bytes):
        return obj.hex()
    return obj

def get_tx_data(tx_hash, w3):
    """Fetch transaction data using web3"""
    try:
        # Get transaction details
        tx = w3.eth.get_transaction(tx_hash)
        
        if not tx:
            print(f"Error: Transaction {tx_hash} not found")
            exit(1)
            
        # Format transaction data
        tx_data = {
            "from": hex_to_str(tx['from']),
            "to": hex_to_str(tx['to']) if tx['to'] else None,  # None for contract deployments
            "value": hex(tx['value']),
            "gas": tx['gas'],
            "gasPrice": hex(tx['gasPrice']),
            "data": hex_to_str(tx['input']),
            "chainId": tx['chainId']
        }
            
        return tx_data
        
    except Exception as e:
        print(f"Error fetching transaction data: {str(e)}")
        exit(1)

def main():
    # Load environment variables
    load_dotenv()
    
    # Get RPC URL from environment variables
    rpc_url = os.getenv('RPC_URL')
    if not rpc_url:
        print("Error: RPC_URL must be set in .env file")
        exit(1)
    
    # Initialize Web3
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        print("Error: Could not connect to the blockchain")
        exit(1)
    
    # Get transaction hash from command line argument
    import sys
    if len(sys.argv) != 2:
        print("Usage: python fetch_tx_data.py <transaction_hash>")
        exit(1)
    
    tx_hash = sys.argv[1]
    
    # Fetch and format transaction data
    tx_data = get_tx_data(tx_hash, w3)
    
    # Save to tx_data.json
    with open('tx_data.json', 'w') as f:
        json.dump(tx_data, f, indent=4)
    
    print(f"Transaction data has been saved to tx_data.json")
    
    # Print some helpful information
    if not tx_data['to']:
        print("\nThis appears to be a contract deployment transaction")
    else:
        print(f"\nTransaction to: {tx_data['to']}")
    print(f"Value: {Web3.from_wei(int(tx_data['value'], 16), 'ether')} ETH")
    print(f"Gas: {tx_data['gas']}")
    print(f"Gas Price: {Web3.from_wei(int(tx_data['gasPrice'], 16), 'gwei')} Gwei")
    print(f"Chain ID: {tx_data['chainId']}")

if __name__ == "__main__":
    main() 