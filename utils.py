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

# utils.py (Asegúrate de que esta función acepte u_id)
def obtener_periodo_trabajo(u_id):
    default = {"desde": "2026-03-09", "hasta": "2026-03-15", "tipo": "SEMANAL", "semana": "11"}
    try:
        # Llamamos al motor pasándole el u_id que viene de la agencia logueada
        df_conf = db_engine("config_sistema", "leer", u_id=u_id) 
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
