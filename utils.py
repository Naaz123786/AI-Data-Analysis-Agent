import pandas as pd
import tempfile
import csv
import os

def preprocess_and_save(file):
    try:
        # Supports:
        # - Werkzeug FileStorage (has .filename)
        # - File path (str / PathLike)
        # - File-like objects (may have .name)
        filename = None
        if isinstance(file, (str, os.PathLike)):
            filename = str(file)
        else:
            filename = getattr(file, "filename", None) or getattr(file, "name", None)

        filename = (filename or "").lower()

        if filename.endswith(".csv"):
            df = pd.read_csv(file, encoding="utf-8", na_values=["NA", "N/A", "missing"])
        elif filename.endswith(".xlsx"):
            df = pd.read_excel(file, na_values=["NA", "N/A", "missing"])
        else:
            return None, None, None, "Unsupported file format (upload .csv or .xlsx)."

        for col in df.select_dtypes(include=['object']):
            df[col] = df[col].astype(str).replace({r'"': '""'}, regex=True)

        for col in df.columns:
            if 'date' in col.lower():
                df[col] = pd.to_datetime(df[col], errors='coerce')
            elif df[col].dtype == 'object':
                try:
                    df[col] = pd.to_numeric(df[col])
                except:
                    pass

        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode="w", newline="", encoding="utf-8") as temp_file:
            df.to_csv(temp_file.name, index=False, quoting=csv.QUOTE_ALL)
            return df, df.columns.tolist(), df.to_html(classes='table-auto w-full'), None
    except Exception as e:
        return None, None, None, str(e)
