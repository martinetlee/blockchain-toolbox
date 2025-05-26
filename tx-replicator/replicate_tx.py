import json
import os
from dotenv import load_dotenv
from web3 import Web3
from eth_abi import decode
import re

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

def is_deployment_tx(tx_data):
    """Check if the transaction is a contract deployment"""
    return not tx_data.get('to') or tx_data.get('to') == '0x' or tx_data.get('to') == ''

def find_metadata_end(data, start_pos):
    """Find the end of metadata by looking for known end markers"""
    # Known metadata end markers
    end_markers = ['0033', '0032', '0029']
    
    for marker in end_markers:
        pos = data.find(marker, start_pos)
        if pos != -1:
            # Verify this is actually the end of metadata
            # by checking if the next bytes look like constructor args
            next_bytes = data[pos + 4:pos + 12]  # Look at next 4 bytes
            if len(next_bytes) == 8 and all(c in '0123456789abcdef' for c in next_bytes):
                return pos
    
    return -1

def extract_constructor_args(tx_data):
    """Extract constructor arguments from deployment transaction data"""
    if not is_deployment_tx(tx_data):
        return None, None
    
    data = tx_data['data']
    # Find the position of the metadata (starts with 64736f6c6343)
    metadata_pos = data.find('64736f6c6343')
    if metadata_pos == -1:
        return None, None
    
    # Extract bytecode and constructor args
    bytecode = data[:metadata_pos]
    
    # Find the end of metadata
    metadata_end = find_metadata_end(data, metadata_pos)
    if metadata_end == -1:
        print("Warning: Could not find metadata end marker")
        return None, None
    
    # Skip the metadata (including the end marker)
    constructor_args_hex = data[metadata_end + 4:]
    
    print("constructor_args_hex", constructor_args_hex)
    print("len", len(constructor_args_hex))
    
    # Try to decode common types
    try:
        interpretations = []
        
        # For fixed-length data (32 bytes)
        if len(constructor_args_hex) == 64:  # 32 bytes
            # As address
            address = '0x' + constructor_args_hex[-40:]  # Last 20 bytes
            if Web3.is_address(address):
                interpretations.append(('address', address))
            
            # As uint256
            uint_value = int(constructor_args_hex, 16)
            interpretations.append(('uint256', uint_value))
            
            # As bool
            if uint_value in (0, 1):
                interpretations.append(('bool', bool(uint_value)))
            
            # As bytes32
            try:
                bytes_value = bytes.fromhex(constructor_args_hex)
                interpretations.append(('bytes32', bytes_value))
            except ValueError:
                pass
            
            # As string (empty string)
            interpretations.append(('string', ''))
            
            # As bytes (empty bytes)
            interpretations.append(('bytes', b''))
        
        # For dynamic-length data
        if len(constructor_args_hex) > 64:  # At least 32 bytes
            try:
                # First 32 bytes is the length
                length = int(constructor_args_hex[:64], 16)
                # Next bytes are the data
                data_hex = constructor_args_hex[64:64 + length * 2]
                
                # Try as string
                try:
                    str_value = bytes.fromhex(data_hex).decode('utf-8').rstrip('\x00')
                    interpretations.append(('string', str_value))
                except UnicodeDecodeError:
                    pass
                
                # Try as bytes
                try:
                    bytes_value = bytes.fromhex(data_hex)
                    interpretations.append(('bytes', bytes_value))
                except ValueError:
                    pass
            except ValueError:
                pass
        
        # Show all interpretations and let user choose
        if interpretations:
            print("\nPossible interpretations of the constructor argument:")
            for i, (arg_type, value) in enumerate(interpretations, 1):
                if arg_type in ('bytes', 'bytes32'):
                    print(f"{i}. {arg_type}: 0x{value.hex()}")
                else:
                    print(f"{i}. {arg_type}: {value}")
            
            choice = input("\nChoose the correct type (enter number) or press Enter to skip: ")
            if choice.strip():
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(interpretations):
                        return bytecode, [interpretations[idx]]
                except ValueError:
                    pass
            
    except Exception as e:
        print(f"Warning: Could not decode constructor arguments: {str(e)}")
    
    return bytecode, None

def encode_constructor_args(bytecode, args):
    """Encode constructor arguments and combine with bytecode"""
    if not args:
        return bytecode
    
    # Encode arguments based on their type
    encoded_args = ''
    for arg_type, value in args:
        if arg_type == 'address':
            # Remove '0x' prefix and pad to 32 bytes
            encoded_args += value[2:].zfill(64)
        elif arg_type == 'uint256':
            encoded_args += hex(value)[2:].zfill(64)
        elif arg_type == 'bool':
            encoded_args += '1' if value else '0'.zfill(64)
        elif arg_type == 'bytes32':
            encoded_args += value.hex().ljust(64, '0')
        elif arg_type == 'string':
            # Encode string length and value
            str_bytes = value.encode('utf-8')
            length_hex = hex(len(str_bytes))[2:].zfill(64)
            value_hex = str_bytes.hex().ljust(64, '0')
            encoded_args += length_hex + value_hex
        elif arg_type == 'bytes':
            # Encode bytes length and value
            length_hex = hex(len(value))[2:].zfill(64)
            value_hex = value.hex().ljust(64, '0')
            encoded_args += length_hex + value_hex
    
    return bytecode + '64736f6c63430008140033' + encoded_args

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
    
    # Handle constructor arguments for deployment transactions
    if is_deployment_tx(tx_data):
        bytecode, args = extract_constructor_args(tx_data)
        print("bytecode", bytecode)
        print("args", args)
        if args:
            print("\nDetected constructor arguments:")
            for arg_type, value in args:
                print(f"Type: {arg_type}, Value: {value}")
            
            modify = input("\nDo you want to modify the constructor arguments? (y/n): ")
            if modify.lower() == 'y':
                new_args = []
                for arg_type, old_value in args:
                    new_value = input(f"Enter new value for {arg_type} (current: {old_value}): ")
                    if arg_type == 'address':
                        if not Web3.is_address(new_value):
                            print("Invalid address format")
                            exit(1)
                        new_value = Web3.to_checksum_address(new_value)
                    elif arg_type == 'uint256':
                        try:
                            new_value = int(new_value)
                        except ValueError:
                            print("Invalid number format")
                            exit(1)
                    elif arg_type == 'bool':
                        new_value = new_value.lower() in ('true', '1', 'yes')
                    elif arg_type == 'bytes32':
                        try:
                            new_value = bytes.fromhex(new_value)
                            if len(new_value) != 32:
                                print("Invalid bytes32 length")
                                exit(1)
                        except ValueError:
                            print("Invalid bytes32 format")
                            exit(1)
                    elif arg_type == 'string':
                        new_value = str(new_value)
                    elif arg_type == 'bytes':
                        try:
                            new_value = bytes.fromhex(new_value)
                        except ValueError:
                            print("Invalid bytes format")
                            exit(1)
                    new_args.append((arg_type, new_value))
                
                # Update transaction data with new constructor arguments
                tx_data['data'] = encode_constructor_args(bytecode, new_args)
    
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
        
        if is_deployment_tx(tx_data) and receipt['status'] == 1:
            print(f"Contract deployed at: {receipt['contractAddress']}")
        
    except Exception as e:
        print(f"Error sending transaction: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main() 