# ERC20 Token Holder Balance

Creates a snapshot of the current holder of a given token.

Given:
- RPC endpoint for the chain
- ERC20 token address

the script does these things:
- detect all the transfer events from the ERC20 token and record all the addresses involved, this is done in batches so that it is not being rate-limited
- query the current balance of the addresses that was involved in the transfer events, also calculate the percentage of token holding of the address
- Write the result in a csv file with the fields of [address, balance, percentage]
- The file should reflect the current date, time, chainID, and token address

## Running the script

```
pip install -r requirements.txt
```

```
export RPC_URL="your_rpc_endpoint"
export TOKEN_ADDRESS="your_token_address"
export FROM_BLOCK="from_block"
```

Run the script: 
```
python token-holder-snapshot.py
```