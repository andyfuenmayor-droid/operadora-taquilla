import streamlit as st
from supabase import create_client

# Configuración de Supabase usando los Secrets de Streamlit
@st.cache_resource
def get_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_supabase()

def obtener_periodo_trabajo():
    # Retorna valores básicos o los que necesites
    return {"desde": "2026-03-09", "hasta": "2026-03-15"}
