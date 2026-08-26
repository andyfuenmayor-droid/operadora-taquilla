import os
from datetime import datetime, timedelta
import streamlit as st
import pandas as pd
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
from supabase import create_client

@st.cache_resource
def get_supabase():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        try:
            if "SUPABASE_URL" in st.secrets:
                url = st.secrets["SUPABASE_URL"]
            if "SUPABASE_KEY" in st.secrets:
                key = st.secrets["SUPABASE_KEY"]
        except Exception:
            pass

    if not url or not key:
        st.error("⚠️ Error: No se encontraron SUPABASE_URL ni SUPABASE_KEY en las variables de entorno ni en `.streamlit/secrets.toml`.")
        
    return create_client(url, key)

supabase = get_supabase()

def db_engine(tabla, accion, datos=None, u_id=None, filtrar_usuario=True):
    try:
        if accion == "leer":
            query = supabase.table(tabla).select("*")
            if filtrar_usuario and u_id:
                query = query.eq("user_id", u_id)
            res = query.execute()
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

def obtener_periodo_trabajo(u_id):
    # Valores por defecto calculados dinámicamente (Semana actual Lunes a Domingo)
    hoy = datetime.now().date()
    lunes = hoy - timedelta(days=hoy.weekday())
    domingo = lunes + timedelta(days=6)
    sem_no = hoy.strftime("%V")
    default = {"desde": str(lunes), "hasta": str(domingo), "tipo": "SEMANAL", "semana": str(sem_no)}
    try:
        # Forzar que u_id sea string y sin espacios
        u_id_clean = str(u_id).strip() if u_id else None
        
        # 1. Intentamos obtener el periodo específico del usuario
        df_conf = db_engine("config_sistema", "leer", u_id=u_id_clean, filtrar_usuario=True) 
        
        # 2. Si no hay configuración para este usuario, buscamos la configuración GLOBAL (la primera que encuentre)
        if df_conf is None or df_conf.empty:
            df_conf = db_engine("config_sistema", "leer", u_id=None, filtrar_usuario=False)

        if df_conf is not None and not df_conf.empty:
            # LIMPIEZA PROFUNDA: Quitamos espacios y pasamos a minúsculas los parámetros prueba de git
            df_conf['parametro'] = df_conf['parametro'].astype(str).str.strip().str.lower()
            df_conf['valor'] = df_conf['valor'].astype(str).str.strip()
            
            conf_dict = dict(zip(df_conf["parametro"], df_conf["valor"]))
            
            return {
                "desde": conf_dict.get("fecha_desde", default["desde"]),
                "hasta": conf_dict.get("fecha_hasta", default["hasta"]),
                "tipo": conf_dict.get("tipo_cierre", default["tipo"]),
                "semana": conf_dict.get("semana_no", default["semana"])
            }
    except Exception as e:
        st.error(f"DEBUG ERROR Periodo: {e}")
    return default

def obtener_whatsapp_agencia_local(u_id: str, agencia_nombre: str) -> str:
    cms_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "operadora-cms", "data", "agencias_whatsapp.json"))
    if os.path.exists(cms_path):
        try:
            import json
            with open(cms_path, "r", encoding="utf-8") as f:
                store = json.load(f)
                key = f"{str(u_id).strip()}_{str(agencia_nombre).strip().upper()}"
                return store.get(key, "")
        except Exception:
            pass
    return ""

def obtener_pagos_locales_agencia(u_id: str, agencia_nombre: str) -> list:
    cms_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "operadora-cms", "data", "agencias_pagos.json"))
    if os.path.exists(cms_path):
        try:
            import json
            with open(cms_path, "r", encoding="utf-8") as f:
                store = json.load(f)
                key = f"{str(u_id).strip()}_{str(agencia_nombre).strip().upper()}"
                return store.get(key, [])
        except Exception:
            pass
    return []

def obtener_gastos_locales_agencia(u_id: str, agencia_nombre: str) -> list:
    cms_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "operadora-cms", "data", "agencias_gastos.json"))
    if os.path.exists(cms_path):
        try:
            import json
            with open(cms_path, "r", encoding="utf-8") as f:
                store = json.load(f)
                key = f"{str(u_id).strip()}_{str(agencia_nombre).strip().upper()}"
                return store.get(key, [])
        except Exception:
            pass
    return []


def obtener_etiqueta_confirmacion(row):
    """
    Retorna la etiqueta legible del estado de confirmación:
    - ❌ Rechazado (con motivo si existe)
    - ✅ C (si confirmado)
    - ⏳ Pendiente (si no confirmado ni rechazado)
    """
    if isinstance(row, dict):
        rechazado = bool(row.get("rechazado", False))
        confirmado = bool(row.get("confirmado", False))
        motivo = str(row.get("motivo_rechazo", "") or "").strip()
    else:
        rechazado = bool(row.get("rechazado", False)) if hasattr(row, "get") else False
        confirmado = bool(row.get("confirmado", False)) if hasattr(row, "get") else False
        motivo = str(row.get("motivo_rechazo", "") or "").strip() if hasattr(row, "get") else ""

    if rechazado:
        return f"❌ Rechazado ({motivo})" if motivo else "❌ Rechazado"
    if confirmado:
        return "✅ C"
    return "⏳ Pendiente"



