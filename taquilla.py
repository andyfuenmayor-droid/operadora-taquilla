import streamlit as st
from utils import supabase
from datetime import datetime

st.set_page_config(page_title="Taquilla POS", layout="centered")

# Login simplificado
if "taquilla_autenticada" not in st.session_state:
    st.session_state.taquilla_autenticada = False

if not st.session_state.taquilla_autenticada:
    st.title("🔐 Acceso Taquilla")
    ag_input = st.text_input("Nombre de la Agencia").strip().upper()
    key_input = st.text_input("Clave de Acceso", type="password")
    
    if st.button("Ingresar"):
        res = supabase.table("agencias").select("*").eq("nombre_agencia", ag_input).eq("clave_taquilla", key_input).execute()
        if res.data:
            st.session_state.taquilla_autenticada = True
            st.session_state.agencia_actual = res.data[0]
            st.rerun()
        else:
            st.error("Datos incorrectos")
else:
    ag = st.session_state.agencia_actual
    st.title(f"🎰 Taquilla: {ag['nombre_agencia']}")
    
    with st.form("carga_ventas"):
        venta = st.number_input("Venta Bruta", min_value=0.0)
        premios = st.number_input("Premios Pagados", min_value=0.0)
        comision = st.number_input("Comisión", min_value=0.0)
        moneda = st.selectbox("Moneda", ag['monedas'].split(", "))
        sistema = st.selectbox("Sistema", ag['sistemas'].split(", "))
        
        if st.form_submit_button("Registrar Movimiento"):
            neto = venta - comision - premios
            data = {
                "agencia": ag['nombre_agencia'],
                "sistema": sistema,
                "moneda": moneda,
                "venta": venta,
                "premios": premios,
                "comision": comision,
                "neto": neto,
                "fecha": datetime.now().strftime("%Y-%m-%d"),
                "user_id": ag['user_id']
            }
            supabase.table("carga_actual").insert(data).execute()
            st.success("✅ Venta registrada!")

    if st.button("Cerrar Sesión"):
        st.session_state.taquilla_autenticada = False
        st.rerun()
