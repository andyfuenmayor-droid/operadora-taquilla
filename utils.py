# utils.py
import streamlit as st
import pandas as pd
from supabase import create_client

@st.cache_resource
def get_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = get_supabase()

# AÑADE EL PARÁMETRO u_id OPCIONAL PARA EVITAR EL ERROR DE UUID
def db_engine(tabla, accion, datos=None, u_id=None):
    try:
        if accion == "leer":
            # Si no pasas un u_id, no filtra, o usa el que le des
            query = supabase.table(tabla).select("*")
            if u_id:
                query = query.eq("user_id", u_id)
            res = query.execute()
            df = pd.DataFrame(res.data or [])
            if not df.empty:
                df.columns = [c.lower().strip() for c in df.columns]
            return df
        # ... resto de la función (guardar/borrar) ...
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error en db_engine ({tabla}): {e}")
        return pd.DataFrame()

def obtener_periodo_trabajo(u_id): # AHORA NECESITA EL u_id
    # ... (tu lógica de fechas) ...
    # Asegúrate de llamar a db_engine así:
    df_conf = db_engine("config_sistema", "leer", u_id=u_id)
    # ... resto del código ...
