import streamlit as st
from utils import supabase
from datetime import datetime
from streamlit_option_menu import option_menu
from utils import supabase, obtener_periodo_trabajo

# Dentro de tu zona autenticada o donde necesites mostrar las fechas:
periodo = obtener_periodo_trabajo()
st.sidebar.info(f"📅 Ciclo actual: {periodo['desde']} al {periodo['hasta']}")

st.set_page_config(page_title="Taquilla POS", layout="centered")

# --- FUNCIÓN DE REGISTRO DINÁMICO ---
def modulo_registro_taquilla(agencia_data):
    st.header(f"🎰 Taquilla: {agencia_data['nombre_agencia']}")
    
    sistemas_lista = [s.strip() for s in str(agencia_data.get("sistemas", "BETM3")).split(",")]
    
    for sist in sistemas_lista:
        with st.container(border=True):
            st.markdown(f"#### 📍 Sistema: {sist}")
            c1, c2, c3, c4 = st.columns(4)
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
                            "moneda": "COP",
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
    # Zona autenticada
    ag = st.session_state.agencia_actual
    
    # Sidebar
    with st.sidebar:
        st.write(f"**Usuario:** {ag['nombre_agencia']}")
        
        seleccion = option_menu(
            "Menú Taquilla", 
            ["Inicio", "Cargar Ventas"],
            icons=["house", "cloud-upload"], 
            menu_icon="cast", default_index=0
        )
        
        st.divider()
        if st.button("🚪 Cerrar Sesión"):
            st.session_state.taquilla_autenticada = False
            st.rerun()

    # Mapeo de páginas
    if seleccion == "Inicio":
        st.write("Bienvenido a la Taquilla")
    elif seleccion == "Cargar Ventas":
        modulo_registro_taquilla(ag)
