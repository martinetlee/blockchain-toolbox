import json
import os
from dotenv import load_dotenv
from web3 import Web3

def load_tx_data():
    """Load transaction data from tx_data.json"""
    try:
        with open('tx_data.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("Error: tx_data.json not found")
        exit(1)
    except json.JSONDecodeError:
        print("Error: Invalid JSON in tx_data.json")
        exit(1)

def get_chain_id(w3):
    """Get the current chain ID"""
    return w3.eth.chain_id

def estimate_gas_price(w3):
    """Get the current gas price"""
    return w3.eth.gas_price

def main():
    # Load environment variables
    load_dotenv()
    
    # Get private key and RPC URL from environment variables
    private_key = os.getenv('PRIVATE_KEY')
    rpc_url = os.getenv('RPC_URL')
    
    if not private_key or not rpc_url:
        print("Error: PRIVATE_KEY and RPC_URL must be set in .env file")
        exit(1)
    
    # Initialize Web3
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        print("Error: Could not connect to the blockchain")
        exit(1)
    
    # Load transaction data
    tx_data = load_tx_data()
    
    # Create account from private key
    account = w3.eth.account.from_key(private_key)
    
    # Replace the from address with our account address
    tx_data['from'] = account.address
    
    # Update chain-specific parameters
    current_chain_id = get_chain_id(w3)
    print(f"Current chain ID: {current_chain_id}")
    
    # Update chain ID
    tx_data['chainId'] = current_chain_id
    
    # Update gas price to current network conditions
    current_gas_price = estimate_gas_price(w3)
    print(f"Current gas price: {Web3.from_wei(current_gas_price, 'gwei')} Gwei")
    tx_data['gasPrice'] = hex(current_gas_price)
    
    # Add nonce to transaction
    tx_data['nonce'] = w3.eth.get_transaction_count(account.address)
    
    # Print transaction details before sending
    print("\nTransaction details:")
    print(f"From: {tx_data['from']}")
    print(f"To: {tx_data['to'] if tx_data['to'] else 'Contract Deployment'}")
    print(f"Value: {Web3.from_wei(int(tx_data['value'], 16), 'ether')} ETH")
    print(f"Gas: {tx_data['gas']}")
    print(f"Gas Price: {Web3.from_wei(int(tx_data['gasPrice'], 16), 'gwei')} Gwei")
    print(f"Chain ID: {tx_data['chainId']}")
    
    # Ask for confirmation before sending
    confirm = input("\nDo you want to send this transaction? (y/n): ")
    if confirm.lower() != 'y':
        print("Transaction cancelled")
        exit(0)
    
    # Sign transaction
    signed_tx = w3.eth.account.sign_transaction(tx_data, private_key)
    
    # Send transaction
    try:
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        print(f"Transaction sent! Hash: {tx_hash.hex()}")
        
        # Wait for transaction receipt
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        print(f"Transaction status: {'success' if receipt['status'] == 1 else 'failed'}")
        
    except Exception as e:
        print(f"Error sending transaction: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main() 