import requests
import pandas as pd
import json
import random
from datetime import datetime, timedelta

# --- 1. Configuration Area (For Groww) ---
# NOTE: Enter your actual Groww API Key & User ID in the strings below.
GROWW_API_KEY = ""  # <-- Enter your API Key
GROWW_USER_ID = ""  # <-- Enter your User ID
# Update the actual Base URL and endpoints for Groww
GROWW_BASE_URL = "https://api.groww.in/v1"

# Headers for API call
HEADERS = {
    'Authorization': f'Bearer {GROWW_API_KEY}',
    'User-ID': GROWW_USER_ID,
    'Content-Type': 'application/json'
}

# --- 2. Data Simulation (In absence of API) ---
def _simulate_api_response(endpoint, params):
    print(f"Simulating API call for: {endpoint} with params: {params}")
    today = datetime.now().strftime("%Y-%m-%d")
    if 'quotes' in endpoint:
        data = [{'symbol': s, 'ltp': round(random.uniform(100, 5000), 2),
                 'change_pc': round(random.uniform(-5, 5), 2)} for s in params.get('symbols', '').split(',')]
        return {"status": "success", "quotes": data}
    elif 'historical' in endpoint or 'intraday' in endpoint:
        data = []
        start_date = datetime.now() - timedelta(days=5)
        for i in range(10):
            date = (start_date + timedelta(days=i)).strftime("%Y-%m-%d %H:%M:%S")
            data.append({
                'timestamp': date,
                'open': random.uniform(500, 510),
                'high': random.uniform(510, 520),
                'low': random.uniform(490, 500),
                'close': random.uniform(500, 510),
                'volume': random.randint(100000, 500000)
            })
        return {"status": "success", "chartData": data}
    elif 'optionchain' in endpoint:
        data = []
        for strike in [19500, 20000, 20500]:
            data.append({'strikePrice': strike, 'type': 'CE', 'oi': random.randint(1000, 5000),
                         'ltp': round(random.uniform(50, 150), 2)})
            data.append({'strikePrice': strike, 'type': 'PE', 'oi': random.randint(1000, 5000),
                         'ltp': round(random.uniform(50, 150), 2)})
        return {"status": "success", "optionChain": data}
    elif 'topmovers' in endpoint:
        data = [{'symbol': f'STOCK{i}', 'ltp': round(random.uniform(100, 1000), 2),
                 'pct_change': round(random.uniform(2, 10)
                 * (1 if params.get('type') == 'GAINERS' else -1), 2)} for i in range(5)]
        return {"status": "success", "movers": data}
    elif 'instruments' in endpoint:
        data = [{'symbol': f'INSTR{i}', 'exchange': 'NSE', 'name': f'Instrument {i}', 'isin': f'IN0000000{i}'}
                for i in range(10)]
        return {"status": "success", "instruments": data}
    return {"status": "failure", "error": "Endpoint not recognized in simulation"}

# --- 3. Core API Fetch Function ---
def fetch_data(endpoint, params=None):
    if not GROWW_API_KEY:
        return _simulate_api_response(endpoint, params)
    url = f"{GROWW_BASE_URL}/{endpoint}"
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        response.raise_for_status() 
        try:
            return response.json()
        except json.JSONDecodeError:
            error_msg = "JSON Decode Error: Response was not valid JSON."
            print(f"❌ {error_msg} from {endpoint}")
            return {"status": "failure", "error": error_msg, "response_text": response.text}
    except requests.exceptions.Timeout:
        error_msg = "Request Timed out."
        print(f"❌ {error_msg} from {endpoint}")
        return {"status": "failure", "error": error_msg}
    except requests.exceptions.RequestException as e:
        error_msg = f"HTTP Error or Connection Failure: {e}"
        print(f"❌ {error_msg} from {endpoint}")
        return {"status": "failure", "error": error_msg}


# --- 4. Function to Convert Data to DataFrame ---
def create_dataframe(api_response, sheet_name, key_to_extract=None):
    if api_response.get("status") == "failure" or api_response.get("error"):
        error_details = api_response.get("error", "Unknown API error")
        error_df = pd.DataFrame([{
            "API Endpoint": sheet_name,
            "Status": "FAILED",
            "Details": error_details,
            "Timestamp": datetime.now().isoformat()
        }])
        return error_df, True
    try:
        data = api_response.get(key_to_extract, api_response)
        if not data:
            df = pd.DataFrame([{"Message": "No data returned (Empty List)", "Source": sheet_name}])
        else:
            df = pd.DataFrame(data)
        return df, False
    except Exception as e:
        error_details = f"DataFrame Creation Logic Error: {e}"
        error_df = pd.DataFrame([{
            "API Endpoint": sheet_name,
            "Status": "FAILED",
            "Details": error_details,
            "Timestamp": datetime.now().isoformat()
        }])
        return error_df, True

# --- 5. Groww API-specific data fetchers ---
def get_market_quotes_data(instruments):
    response = fetch_data("market/quotes", {'symbols': ','.join(instruments)})
    return create_dataframe(response, 'Market_Quotes', 'quotes')

def get_instrument_details_data(exchange):
    response = fetch_data("instruments/list", {'exchange': exchange})
    return create_dataframe(response, 'Instruments_List', 'instruments')

def get_historical_and_intraday_data(symbol):
    params_hist = {'symbol': symbol, 'period': '1D', 'from': '2024-01-01', 'to': datetime.now().strftime("%Y-%m-%d")}
    hist_response = fetch_data("historical/data", params_hist)
    params_intraday = {'symbol': symbol, 'interval': '5m'}
    intraday_response = fetch_data("chart/intraday", params_intraday)
    df_hist, is_err_hist = create_dataframe(hist_response, 'Historical_Data', 'chartData')
    df_intraday, is_err_intra = create_dataframe(intraday_response, 'Intraday_Chart', 'chartData')
    return [
        ('Historical_Data', df_hist, is_err_hist),
        ('Intraday_Chart', df_intraday, is_err_intra)
    ]

def get_option_chain_data(symbol, expiry_date):
    params = {'symbol': symbol, 'expiry': expiry_date}
    response = fetch_data("derivatives/optionchain", params)
    return create_dataframe(response, 'Option_Chain', 'optionChain')

def get_top_movers_data(exchange):
    gainers_response = fetch_data("market/topmovers", {'exchange': exchange, 'type': 'GAINERS'})
    df_gainers, is_err_gain = create_dataframe(gainers_response, 'Top_Gainers', 'movers')
    losers_response = fetch_data("market/topmovers", {'exchange': exchange, 'type': 'LOSERS'})
    df_losers, is_err_lose = create_dataframe(losers_response, 'Top_Losers', 'movers')
    return [
        ('Top_Gainers', df_gainers, is_err_gain),
        ('Top_Losers', df_losers, is_err_lose)
    ]

# --- 6. Excel writing function ---
def write_to_excel(dataframes_list, filename="groww_live_data.xlsx"):
    print(f"\n--- Saving data to {filename} ---")
    successful_dfs = {}
    error_logs = []
    for sheet_name, df, is_error in dataframes_list:
        if is_error:
            error_logs.append(df)
            print(f"⚠ Error logged for {sheet_name}.")
        else:
            successful_dfs[sheet_name] = df
            print(f"✅ Data for {sheet_name} prepared.")
    if error_logs:
        print("\n!!! EXCEPTION AND ERROR TYPES FOUND !!!")
        combined_errors = pd.concat(error_logs, ignore_index=True)
        print(combined_errors.to_string())
        successful_dfs['API_Errors'] = combined_errors  
    try:
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            for sheet_name, df in successful_dfs.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        print(f"\n✨ Project complete! All data saved to {filename} in multiple sheets.")
    except Exception as e:
        print(f"\n❌ FATAL ERROR saving to Excel: {e}")

# --- 7. Main Function ---
def main():
    INSTRUMENTS_TO_TRACK = ["RELIANCE", "TCS", "HDFCBANK", "INFY"]
    FUTURES_SYMBOL = "NIFTY"
    EXPIRY_DATE = "2024-03-28"   # Update expiry as per Groww
    EXCHANGE = "NSE"
    all_data_to_write = []
    df, is_error = get_market_quotes_data(INSTRUMENTS_TO_TRACK)
    all_data_to_write.append(('Market_Quotes', df, is_error))
    df, is_error = get_instrument_details_data(EXCHANGE)
    all_data_to_write.append(('Instruments_List', df, is_error))
    results_hist_intraday = get_historical_and_intraday_data(INSTRUMENTS_TO_TRACK[0])
    all_data_to_write.extend(results_hist_intraday)
    df, is_error = get_option_chain_data(FUTURES_SYMBOL, EXPIRY_DATE)
    all_data_to_write.append(('Option_Chain', df, is_error))
    results_movers = get_top_movers_data(EXCHANGE)
    all_data_to_write.extend(results_movers)
    write_to_excel(all_data_to_write)

if __name__ == "__main__":
    try:
        main()
    except ImportError as e:
        print(f"\n!!! IMPORTANT: Missing required library: {e} !!!")
        print("Please run: pip install requests pandas openpyxl")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")