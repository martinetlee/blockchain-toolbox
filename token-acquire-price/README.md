# Token buy / sell history

Given:
- a token address
- a set of DEX exchange addresses
- a set of user addresses
- rpc api endpoint

what the script does:
- Attempts to find a file "{token_address}_all_transfer_events_block_{lastblock}.csv"
    - If the file doesn't exist, record all transfer events of the given ERC20 address into the file
    - if it exists, read from the file to obtain all the transfer events
- Filters out the transfer events and only keep the ones that is from or to the user's addresses
- process the filtered transfer events with the following rules
    - if the transfer is "from" the set of DEX exchange address, then the transfer should be labeled as a buy order
    - if the transfer is "to" the set of DEX exchange address, then the transfer should be labeled as a sell order
    - if the transfer is between the set of user addresses, they are not significant and label as "Transfer within"
    - if the transfer is "to/from" addresses that are unknown (not DEX exchange addresses nor user addresses), label as "Input unknown" if the user addresses are getting the token, label as "Output unknown" if the user addresses are sending away the token
- Write the above into a csv file with fields of "label", "amount", "from", "to"

## To run the script

First, create two text files:
1. dex_addresses.txt: List of DEX exchange addresses (one per line)
2. user_addresses.txt: List of user addresses to track (one per line)

Set these in .env file
```
RPC_URL=
TOKEN_ADDRESS=
DEX_ADDRESSES_FILE=""
USER_ADDRESSES_FILE=""
FROM_BLOCK= 
CHAIN_ID= # for coingecko
```