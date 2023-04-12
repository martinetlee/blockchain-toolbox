import requests
import json
import os

filename = "events_data.json"
event_topic = "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" # keccak("EVENTNAME(arg1type,arg2type)")
contract_address = "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"

topic_index = 1 # 0 will be the event_topic, 1 is the first argument of the event


if os.path.exists(filename):
    # If the file exists, read from it
    with open(filename, "r") as f:
        file_contents = f.read()
    data = json.loads(file_contents)

else:
    # Etherscan API endpoint for getting contract events
    url = "https://api.etherscan.io/api" #ethereum
    # url = "https://api.polygonscan.com/api" #polygon
    # url = "https://api.bscscan.com/api" #bsc
    # url = "https://api.ftmscan.com/api" #fantom
    # url = "https://api.arbiscan.io/api" #arbitrum
    # url = "https://api-optimistic.etherscan.io/api" #optimism
    # url = "https://api.snowtrace.io/api" #avalanche


    # Set the API key and other parameters for the request
    api_key = "" #ethereum
    # api_key = "" #polygon
    # api_key = "" #bsc
    # api_key = "" #fantom
    # api_key = "" #arbitrum
    # api_key = "" #optimism
    # api_key = "" #avalanche

    module = "logs"
    action = "getLogs"
    fromBlock = "0"
    toBlock = "latest"
    address = contract_address
    topic0 = event_topic

    # Create the request URL
    params = {
        "module": module,
        "action": action,
        "fromBlock": fromBlock,
        "toBlock": toBlock,
        "address": address,
        "topic0": topic0,
        "apikey": api_key
    }
    response = requests.get(url, params=params)
    print(response)
    # Parse the response as JSON
    data = json.loads(response.text)

    # Write the events data to a file
    with open("events_data.json", "w") as f:
        json.dump(data, f)

## print out data

input_array = []
for log in data["result"]:
    input_array.append( "0x" + log['topics'][topic_index][26:] )

unique_array = list(set(input_array))

for ele in unique_array:
    print(ele)