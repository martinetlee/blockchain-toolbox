#Tx Replicator
Given a tx data (in tx_data.txt), the scripts replicates the exact same tx, signs it with the local private key and sends the signed transaction to the blockchain. 

Private key and RPC URL is read from .env file

running the script:
```
python replicate_tx.py
```

.env content:
```
PRIVATE_KEY=your_private_key_here
RPC_URL=your_rpc_url_here
```

## fetch_tx_data

run:
```
python fetch_tx_data.py [tx_hash] [network_name like, sepolia or mainnet]
```