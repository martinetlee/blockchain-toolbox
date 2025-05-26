#!/usr/bin/env python3

import os
import csv
import json
import argparse
import time
from datetime import datetime, timedelta
import requests
from typing import Dict, List, Tuple
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Rate limiting settings
RATE_LIMIT_CALLS = 30  # conservative limit of 30 calls per minute
RATE_LIMIT_PERIOD = 60  # 60 seconds
last_call_time = 0

# Retry settings
MAX_RETRIES = 6
RETRY_DELAY = 15  # seconds

def rate_limit():
    """Implement rate limiting for API calls."""
    global last_call_time
    current_time = time.time()
    time_since_last_call = current_time - last_call_time
    
    if time_since_last_call < (RATE_LIMIT_PERIOD / RATE_LIMIT_CALLS):
        sleep_time = (RATE_LIMIT_PERIOD / RATE_LIMIT_CALLS) - time_since_last_call
        time.sleep(sleep_time)
    
    last_call_time = time.time()

def get_coin_id(token_address: str, chain_id: int) -> str:
    """Get CoinGecko coin ID from token address and chain ID."""
    # Map chain IDs to CoinGecko platforms
    chain_to_platform = {
        1: "ethereum",
        56: "bsc",
        137: "polygon",
        8453: "base",
        # Add more chains as needed
    }
    
    platform = chain_to_platform.get(chain_id)
    if not platform:
        raise ValueError(f"Unsupported chain ID: {chain_id}")
    
    # Get token info from CoinGecko
    url = f"https://api.coingecko.com/api/v3/coins/{platform}/contract/{token_address}"
    print(f"Fetching token info from: {url}")
    
    rate_limit()
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        print(f"Found token: {data.get('name', 'Unknown')} ({data.get('symbol', 'Unknown')})")
        return data['id']
    elif response.status_code == 404:
        raise ValueError(f"Token not found on CoinGecko for address {token_address} on {platform}")
    elif response.status_code == 429:
        raise ValueError("Rate limit exceeded")
    else:
        raise ValueError(f"CoinGecko API error: {response.status_code} - {response.text}")

def load_cached_prices(coin_id: str) -> Dict[str, float]:
    """Load cached historical prices from file."""
    cache_file = f"{coin_id}_price_cache.json"
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
                print(f"Loaded {len(data)} cached prices for {coin_id}")
                return data
        except Exception as e:
            print(f"Error loading cache: {str(e)}")
    return {}

def save_cached_prices(coin_id: str, prices: Dict[str, float]):
    """Save historical prices to cache file."""
    cache_file = f"{coin_id}_price_cache.json"
    try:
        with open(cache_file, 'w') as f:
            json.dump(prices, f, indent=2)
        print(f"Saved {len(prices)} prices to cache")
    except Exception as e:
        print(f"Error saving cache: {str(e)}")

def get_historical_prices(coin_id: str, start_date: datetime, end_date: datetime) -> Dict[str, float]:
    """Get historical prices for a date range from CoinGecko, using cache when possible."""
    # Load cached prices
    prices = load_cached_prices(coin_id)
    
    # Find dates that need to be fetched
    current_date = start_date
    dates_to_fetch = []
    
    while current_date <= end_date:
        date_key = current_date.strftime('%Y-%m-%d')
        if date_key not in prices:
            dates_to_fetch.append(current_date)
        current_date += timedelta(days=1)
    
    if not dates_to_fetch:
        print("All required prices found in cache")
        return prices
    
    print(f"Fetching {len(dates_to_fetch)} missing prices from CoinGecko")
    
    # Fetch missing prices
    i = 0
    while i < len(dates_to_fetch):
        current_date = dates_to_fetch[i]
        retry_count = 0
        
        while retry_count < MAX_RETRIES:
            try:
                url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/history"
                params = {
                    'date': current_date.strftime('%d-%m-%Y'),
                    'localization': 'false'
                }
                
                print(f"Fetching price for {coin_id} at {current_date.strftime('%d-%m-%Y')}")
                
                rate_limit()
                response = requests.get(url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    if 'market_data' in data and 'current_price' in data['market_data']:
                        price = data['market_data']['current_price']['usd']
                        prices[current_date.strftime('%Y-%m-%d')] = price
                        print(f"Price: ${price:,.8f}")
                        break  # Success, move to next date
                    else:
                        print(f"Warning: No price data available for {current_date.strftime('%Y-%m-%d')}")
                        break  # No data available, move to next date
                elif response.status_code == 429:
                    retry_count += 1
                    if retry_count < MAX_RETRIES:
                        print(f"Rate limit exceeded. Retrying in {RETRY_DELAY} seconds... (Attempt {retry_count}/{MAX_RETRIES})")
                        time.sleep(RETRY_DELAY)
                    else:
                        print(f"Rate limit exceeded after {MAX_RETRIES} attempts. Moving to next date.")
                        break
                else:
                    print(f"Warning: Could not get price for {current_date.strftime('%Y-%m-%d')}")
                    break  # Other error, move to next date
                
            except Exception as e:
                retry_count += 1
                if retry_count < MAX_RETRIES:
                    print(f"Error: {str(e)}. Retrying in {RETRY_DELAY} seconds... (Attempt {retry_count}/{MAX_RETRIES})")
                    time.sleep(RETRY_DELAY)
                else:
                    print(f"Failed after {MAX_RETRIES} attempts: {str(e)}")
                    break
        
        i += 1  # Move to next date
    
    # Save updated prices to cache
    save_cached_prices(coin_id, prices)
    return prices

def process_trade_history(file_path: str, prices: Dict[str, float]) -> Tuple[float, float, float]:
    """Process trade history and calculate total cost, revenue, and remaining tokens."""
    total_cost = 0.0
    total_revenue = 0.0
    remaining_tokens = 0.0
    
    with open(file_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            amount = float(row['amount'])
            timestamp = datetime.strptime(row['timestamp'], '%Y-%m-%d %H:%M:%S')
            date_key = timestamp.strftime('%Y-%m-%d')
            
            if date_key not in prices:
                print(f"Warning: No price data available for {date_key}")
                continue
                
            price = prices[date_key]
            
            if row['label'] == 'Buy':
                total_cost += amount * price
                remaining_tokens += amount
            elif row['label'] == 'Sell':
                total_revenue += amount * price
                remaining_tokens -= amount
    
    if remaining_tokens < 0:
        print(f"Warning: Remaining tokens is negative ({remaining_tokens}). This might indicate an error in the trade history.")
    
    return total_cost, total_revenue, remaining_tokens

def calculate_loss_free_price(token_address: str, chain_id: int, trade_history_file: str):
    """Calculate loss-free remaining token price."""
    try:
        # Get CoinGecko coin ID
        coin_id = get_coin_id(token_address, chain_id)
        print(f"Found CoinGecko coin ID: {coin_id}")
        
        # Get date range from trade history
        start_date = None
        end_date = None
        with open(trade_history_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                timestamp = datetime.strptime(row['timestamp'], '%Y-%m-%d %H:%M:%S')
                if start_date is None or timestamp < start_date:
                    start_date = timestamp
                if end_date is None or timestamp > end_date:
                    end_date = timestamp
        
        print(f"\nFetching historical prices from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        prices = get_historical_prices(coin_id, start_date, end_date)
        
        # Process trade history
        total_cost, total_revenue, remaining_tokens = process_trade_history(trade_history_file, prices)
        
        # Calculate remaining amount to recover
        remaining_amount = total_cost - total_revenue
        
        # Calculate loss-free remaining token price
        if remaining_tokens > 0:
            loss_free_price = remaining_amount / remaining_tokens
        else:
            loss_free_price = 0
        
        # Print results
        print("\nResults:")
        print(f"Total Cost: ${total_cost:,.2f}")
        print(f"Total Revenue: ${total_revenue:,.2f}")
        print(f"Remaining Amount to Recover: ${remaining_amount:,.2f}")
        print(f"Remaining Tokens: {remaining_tokens:,.8f}")
        print(f"Loss-free Remaining Token Price: ${loss_free_price:,.8f}")
        
        # Save results to file
        results = {
            'token_address': token_address,
            'chain_id': chain_id,
            'total_cost': total_cost,
            'total_revenue': total_revenue,
            'remaining_amount': remaining_amount,
            'remaining_tokens': remaining_tokens,
            'loss_free_price': loss_free_price,
            'calculated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        output_file = f"{token_address}_loss_free_price_chain_{chain_id}.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {output_file}")
        
    except Exception as e:
        print(f"Error: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description='Calculate loss-free price for a token')
    parser.add_argument('--token-address', type=str, default="",
                      help='Token address to calculate price for')
    parser.add_argument('--chain-id', type=int, default=8453,
                      help='Chain ID (default: 8453 for Base)')
    parser.add_argument('--trade-history', type=str, required=True,
                      help='Path to the trade history CSV file')
    
    args = parser.parse_args()
    
    calculate_loss_free_price(args.token_address, args.chain_id, args.trade_history)

if __name__ == "__main__":
    main() 