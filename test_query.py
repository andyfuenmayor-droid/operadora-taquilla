import os
import pandas as pd
from supabase import create_client

url = "https://envojryuxdmcamlolkgp.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVudm9qcnl1eGRtY2FtbG9sa2dwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzIwNzY1NzMsImV4cCI6MjA4NzY1MjU3M30.0zGpypHi09GInBksu-zNAKi1k-cTHIBM39YrsEaamRc"

supabase = create_client(url, key)

res = supabase.table("cda_pagos_diarios").select("*").execute()
df = pd.DataFrame(res.data or [])
print("Columns:", df.columns.tolist() if not df.empty else "No columns")
if not df.empty:
    print(df.to_string())
else:
    print("Empty table")
