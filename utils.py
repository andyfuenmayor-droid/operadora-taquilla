import streamlit as st
import pandas as pd
from supabase import create_client
import os

# Configuración del Cliente
@st.cache_resource
def get_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_supabase()

def db_engine(tabla, accion, datos=None):
    """Motor unificado para comunicación con Supabase"""
    try:
        # Nota: En Taquilla, esto podría requerir una lógica de sesión distinta 
        # si no usas st.session_state["user"] igual que en el Admin.
        u_id = st.secrets.get("USER_ID_TAQUILLA", "taquilla_global") 
        
        if accion == "leer":
            res = supabase.table(tabla).select("*").eq("user_id", u_id).execute()
            df = pd.DataFrame(res.data or [])
            if not df.empty:
                df.columns = [c.lower().strip() for c in df.columns]
            return df
        elif accion == "guardar":
            if datos:
                for d in datos: d["user_id"] = u_id
                return supabase.table(tabla).insert(datos).execute()
    except Exception as e:
        st.error(f"Error en db_engine ({tabla}): {e}")
        return pd.DataFrame()

def obtener_periodo_trabajo():
    default = {
        "desde": "2026-03-09", 
        "hasta": "2026-03-15", 
        "tipo": "SEMANAL", 
        "semana": "11"
    }
    try:
        df_conf = db_engine("config_sistema", "leer")
        if df_conf is not None and not df_conf.empty:
            conf_dict = dict(zip(df_conf["parametro"], df_conf["valor"]))
            return {
                "desde": str(conf_dict.get("fecha_desde", default["desde"])),
                "hasta": str(conf_dict.get("fecha_hasta", default["hasta"])),
                "tipo": str(conf_dict.get("tipo_cierre", default["tipo"])),
                "semana": str(conf_dict.get("semana_no", default["semana"]))
            }
    except Exception:
        pass 
    return default
