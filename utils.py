# utils.py
import streamlit as st
import pandas as pd
from supabase import create_client

@st.cache_resource
def get_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = get_supabase()

# AÑADE EL PARÁMETRO u_id OPCIONAL PARA EVITAR EL ERROR DE UUID
def db_engine(tabla, accion, datos=None, u_id=None, filtrar_usuario=True):
    """
    Motor unificado. 
    Añadimos 'filtrar_usuario' para poder leer tablas globales (como config_sistema)
    sin que nos obligue a filtrar por ID de agencia.
    """
    try:
        if accion == "leer":
            query = supabase.table(tabla).select("*")
            
            # Solo filtramos si la tabla lo requiere y si 'filtrar_usuario' es True
            if filtrar_usuario and u_id:
                query = query.eq("user_id", u_id)
            
            res = query.execute()
            df = pd.DataFrame(res.data or [])
            if not df.empty:
                df.columns = [c.lower().strip() for c in df.columns]
            return df
        
        elif accion == "guardar":
            if datos:
                # Aquí seguimos obligando a guardar con el ID del usuario actual
                for d in datos: d["user_id"] = u_id
                return supabase.table(tabla).insert(datos).execute()
                
    except Exception as e:
        st.error(f"Error en db_engine ({tabla}): {e}")
        return pd.DataFrame()

def obtener_periodo_trabajo(u_id):
    default = {"desde": "2026-06-01", "hasta": "2026-06-07", "tipo": "SEMANAL", "semana": "23"}
    try:
        # AQUI ESTÁ EL CAMBIO: Ponemos filtrar_usuario=False 
        # para que lea la config sin importar qué ID de agencia tenga la taquilla
        df_conf = db_engine("config_sistema", "leer", u_id=u_id, filtrar_usuario=False) 
        
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
