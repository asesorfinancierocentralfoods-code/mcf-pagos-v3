
import pandas as pd

def parse_sat_excel(file):
    try:
        df = pd.read_excel(file)
        # Normaliza columnas esperadas del SAT
        df.columns = [c.strip().lower() for c in df.columns]
        # Mapeo flexible
        col_map = {
            "uuid": "uuid", "folio fiscal": "uuid", "folio_fiscal": "uuid",
            "serie": "serie", "folio": "folio",
            "fecha": "emision", "emision": "emision",
            "rfc emisor": "emisor_rfc", "emisor_rfc": "emisor_rfc", "rfc": "emisor_rfc",
            "nombre emisor": "emisor_nombre", "emisor_nombre": "emisor_nombre", "proveedor": "emisor_nombre",
            "total": "total", "importe": "total", "monto": "total"
        }
        renamed = {}
        for c in df.columns:
            if c in col_map:
                renamed[c] = col_map[c]
        df = df.rename(columns=renamed)
        # Defaults
        if "uuid" not in df.columns:
            import uuid
            df["uuid"] = [str(uuid.uuid4()) for _ in range(len(df))]
        if "serie" not in df.columns: df["serie"] = "F"
        if "folio" not in df.columns: df["folio"] = df.index.astype(str)
        if "emisor_rfc" not in df.columns: df["emisor_rfc"] = "XAXX010101000"
        if "emisor_nombre" not in df.columns: df["emisor_nombre"] = "PROVEEDOR DEMO"
        if "total" not in df.columns: df["total"] = 1000.0
        if "emision" not in df.columns: 
            from datetime import date
            df["emision"] = date.today()
        df["total"] = pd.to_numeric(df["total"], errors="coerce").fillna(0)
        return df
    except Exception as e:
        print(f"Error parser: {e}")
        return pd.DataFrame()
