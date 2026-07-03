import asyncio
import time
from datetime import date
from pybhav import NSEBhavcopy

async def main():
    nse = NSEBhavcopy()
    
    # Let's fetch the last 3 trading days of June 2024 to test
    # (Choosing historical dates we know exist and are trading days)
    start = date(2024, 6, 26) # Wed
    end = date(2024, 6, 28)   # Fri
    
    print(f"Fetching async range from {start} to {end}...")
    
    t0 = time.time()
    # Skip errors = False to ensure we get hard failures if something is broken
    df = await nse.async_get_range(start, end, skip_errors=False)
    t1 = time.time()
    
    print(f"Success! Fetched {len(df)} rows across {df['_date'].nunique()} days in {t1-t0:.2f} seconds.")
    print("\nSample Data:")
    print(df[["SYMBOL", "OPEN", "HIGH", "LOW", "CLOSE", "_date"]].head())
    print(df[["SYMBOL", "OPEN", "HIGH", "LOW", "CLOSE", "_date"]].tail())

if __name__ == "__main__":
    asyncio.run(main())
