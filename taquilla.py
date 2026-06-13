import streamlit as st
from utils import supabase
from datetime import datetime

st.set_page_config(page_title="Taquilla POS", layout="centered")

# --- FUNCIÓN DE REGISTRO DINÁMICO ---
def modulo_registro_taquilla(agencia_data):
    st.header(f"🎰 Taquilla: {agencia_data['nombre_agencia']}")
    
    # Sistemas configurados en el Admin (separados por coma)
    sistemas_lista = [s.strip() for s in str(agencia_data.get("sistemas", "BETM3")).split(",")]
    
    for sist in sistemas_lista:
        with st.container(border=True):
            st.markdown(f"#### 📍 Sistema: {sist}")
            
            c1, c2, c3, c4 = st.columns(4)
            
            # Formulario dinámico
            venta = c1.number_input(f"Venta", min_value=0.0, format="%.2f", key=f"v_{sist}")
            comision = c2.number_input(f"Comisión", min_value=0.0, format="%.2f", key=f"c_{sist}")
            premios = c3.number_input(f"Premios", min_value=0.0, format="%.2f", key=f"p_{sist}")
            
            neto_calculado = venta - comision - premios
            c4.metric("Neto", f"{neto_calculado:,.2f}")
            
            if st.button(f"🚀 Guardar {sist}", key=f"btn_{sist}"):
                if venta > 0:
                    try:
                        data = {
                            "nombre_agency": agencia_data['nombre_agencia'],
                            "sistema": sist,
                            "monto_venta": venta,
                            "monto_premios": premios,
                            "comision": comision,
                            "neto": neto_calculado,
                            "fecha": datetime.now().strftime("%Y-%m-%d"),
                            "moneda": "COP", # Puedes cambiar esto si la agencia maneja varias
                            "user_id": agencia_data['user_id']
                        }
                        supabase.table("cda_reportes_diarios").insert(data).execute()
                        st.success(f"✅ {sist} registrado!")
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.warning("Ingrese un monto válido.")

# --- LÓGICA DE LOGIN ---
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
    # --- ZONA DE USUARIO AUTENTICADO ---
    ag = st.session_state.agencia_actual
    
    # Llamamos al módulo que definimos arriba
    modulo_registro_taquilla(ag)

    if st.button("Cerrar Sesión"):
        st.session_state.taquilla_autenticada = False
        st.rerun()
