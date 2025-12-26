
import akshare as ak
import pandas as pd
import sys
import traceback

output_file = "debug_output.txt"

with open(output_file, "w", encoding="utf-8") as f:
    try:
        f.write("Starting debug...\n")
        f.write(f"Akshare version: {ak.__version__}\n")
        
        f.write("Calling stock_board_industry_name_em()...\n")
        df = ak.stock_board_industry_name_em()
        
        if df is None:
            f.write("Result is None\n")
        elif df.empty:
            f.write("Result is Empty DataFrame\n")
        else:
            f.write(f"Success! Shape: {df.shape}\n")
            f.write(f"Columns: {df.columns.tolist()}\n")
            f.write(f"First row: {df.iloc[0].to_dict()}\n")
            
    except Exception:
        f.write("Exception occurred:\n")
        traceback.print_exc(file=f)

print("Debug script finished.")
