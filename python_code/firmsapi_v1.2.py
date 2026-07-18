"""firmsapi_v1.2.py
Linghan Qi
Last updated 07/07/2026

Use FIRMS API to fetch active fire data or historical fire data from NASA, save it as a CSV file or GeoDataFrame shapefile, and handle potential errors gracefully.
"""

import requests
import pandas as pd
import geopandas as gpd
import io
import time
from datetime import datetime, timedelta

def fetch_historical_firms_data(map_key, source, bbox, start_date_str, end_date_str):
    """
    Fetch historical fire data from NASA FIRMS API in batches for a specified date range.
    Automatically bypasses the 5-day limit for _SP data and merges all chunks into a single DataFrame.
    """
    # Convert string dates to datetime objects for calculation
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    
    if start_date > end_date:
        print("❌ Error: Start date cannot be later than end date!")
        return None

    all_dataframes = []
    current_start = start_date
    
    current_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{current_time_str}] Starting to fetch historical data from {start_date_str} to {end_date_str}...")

    # Set maximum day range constraint (NASA limit for _SP is 5 days)
    MAX_DAY_RANGE = 5

    # Loop to slice dates, pushing forward by a maximum of 5 days each iteration
    while current_start <= end_date:
        # Calculate the DAY_RANGE needed for this batch (ensuring it doesn't exceed 5)
        days_diff = (end_date - current_start).days + 1
        day_range = min(MAX_DAY_RANGE, days_diff)
        
        # Format the current start date as a URL parameter
        date_param = current_start.strftime("%Y-%m-%d")
        
        url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{map_key}/{source}/{bbox}/{day_range}/{date_param}"
        batch_end_date = (current_start + timedelta(days=day_range - 1)).strftime("%Y-%m-%d")
        print(f"⏳ Fetching data from {date_param} to {batch_end_date} (Span: {day_range} days)...")
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status() 

            csv_data = io.StringIO(response.text)
            df = pd.read_csv(csv_data)
            
            if not df.empty:
                all_dataframes.append(df)
            else:
                print(f"⚠️ Warning: No fire points detected during this specific time frame.")

        except requests.exceptions.HTTPError as errh:
            print(f"❌ HTTP Error (If 429 Too Many Requests, rate limit was triggered): {errh}")
        except Exception as err:
            print(f"❌ An unexpected error occurred: {err}")
            
        # Push forward and update the start date for the next loop iteration
        current_start += timedelta(days=day_range)
        
        # Protect the API Key: pause for 2 seconds after each request to avoid being blocked by NASA
        time.sleep(2)

    # Merge all dataframes after the loop ends
    if all_dataframes:
        final_df = pd.concat(all_dataframes, ignore_index=True)
        # Remove duplicates based on latitude, longitude, and time to ensure data purity
        final_df = final_df.drop_duplicates(subset=['latitude', 'longitude', 'acq_date', 'acq_time'])
        print(f"🎉 Successfully completed! Fetched and merged {len(final_df)} historical fire records.")
        return final_df
    else:
        print("⚠️ No valid data obtained within the entire specified date range.")
        return None

def fetch_firms_data(map_key, source, day_range, bbox):
    """
    Fetch active fire data from NASA FIRMS API based on the provided parameters.
    Returns a Pandas DataFrame if successful, or None if an error occurs.
    """
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{map_key}/{source}/{bbox}/{day_range}"
    
    current_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{current_time_str}] Fetching data from NASA FIRMS...")

    try:
        # Send the network request with a 30-second timeout
        response = requests.get(url, timeout=30)
        # Raise an HTTPError if the status code is not 200
        response.raise_for_status() 

        # Parse and inspect the data
        data = io.StringIO(response.text)
        df = pd.read_csv(data)

        # Check if active fire data was actually retrieved
        if df.empty:
            print("⚠️ WARNING: Request successful, but no active fires were detected in this area/timeframe.")
            return None
            
        print(f"🎉 Successfully retrieved {len(df)} active fire records from API.")
        return df

    except requests.exceptions.HTTPError as errh:
        print(f"❌ HTTP Error (Check API key or rate limits): {errh}")
    except requests.exceptions.ConnectionError as errc:
        print(f"❌ Connection Error: {errc}")
    except requests.exceptions.Timeout as errt:
        print(f"❌ Timeout Error: {errt}")
    except pd.errors.EmptyDataError:
        print("❌ Data Parsing Error: NASA returned invalid CSV format.")
    except Exception as err:
        print(f"❌ Unexpected error occurred during fetch: {err}")
    
    return None

def save_to_csv_files(df, base_filename):
    """
    Save the provided DataFrame to local CSV file.
    Only handles file I/O operations.
    """
    if df is None or df.empty:
        print("⚠️ No data to save.")
        return

    csv_name = f"{base_filename}.csv"

    try:
        # Save as CSV
        df.to_csv(csv_name, index=False, encoding='utf-8')
        print(f"✅ Saved CSV: {csv_name}")
        
    except Exception as e:
        print(f"❌ Error occurred while saving files: {e}")

def save_to_shp_files(df, base_filename):
    """
    Save the provided DataFrame to local Shapefile.
    Only handles file I/O operations.
    """
    if df is None or df.empty:
        print("⚠️ No data to save.")
        return

    shp_name = f"{base_filename}.shp"

    try:
        # Save as Shapefile
        gdf = gpd.GeoDataFrame(
            df,
            geometry=gpd.points_from_xy(df.longitude, df.latitude),
            crs="EPSG:4326"
        )
        gdf.to_file(shp_name, driver="ESRI Shapefile")
        print(f"✅ Saved Shapefile: {shp_name}")
        
    except Exception as e:
        print(f"❌ Error occurred while saving files: {e}")

def main():
    """
    Main function to orchestrate the fetching and saving of NASA FIRMS active fire data.
    """
    # 1. Set parameters
    MAP_KEY = '2c33b1776d6f5df23aa0c3582fc3db15'
    SOURCE = 'VIIRS_SNPP_SP'            # Can not use _NRT for historical data
    # DAY_RANGE = '1'
    START_DATE = '2025-01-07'
    END_DATE = '2025-01-15'
    BBOX = '-124.4,32.5,-114.1,42.0'

    # 2. Fetch data from NASA FIRMS API
    # fire_df = fetch_firms_data(
    #    map_key=MAP_KEY,
    #    source=SOURCE,
    #    day_range=DAY_RANGE,
    #    bbox=BBOX
    # )

    # 2.1 Use the historical fetch function for date ranges
    fire_df = fetch_historical_firms_data(
         map_key=MAP_KEY,
         source=SOURCE,
         bbox=BBOX,
         start_date_str=START_DATE,
         end_date_str=END_DATE
    )

    # 3. If data was successfully fetched, save it to CSV and Shapefile
    if fire_df is not None:
        file_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # base_name = f"firms_data_{file_timestamp}"
        base_name = f"firms_data_historical_{START_DATE}_to_{END_DATE}_{file_timestamp}"
        save_to_csv_files(fire_df, base_name)
        save_to_shp_files(fire_df, base_name)
        
    # Future steps can be seamlessly inserted here, such as：
    # fire_df = clean_data(fire_df)
    # upload_to_postgis(fire_df)

if __name__ == '__main__':
    main()