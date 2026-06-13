import streamlit as st
from utils import supabase
from datetime import datetime
from streamlit_option_menu import option_menu # Asegúrate de importar esto

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
    
    # Definimos variables de seguridad para que el código copiado no falle
    user_actual = type('obj', (object,), {'email': ag.get('nombre_agencia', 'Taquilla')})()
    acceso_ok = True
    msg_error = ""
    if "key_menu" not in st.session_state: st.session_state["key_menu"] = 1

    # Llamamos al módulo
    modulo_registro_taquilla(ag)

    # --- MENÚ Y SIDEBAR (Código copiado indentado correctamente) ---
    with st.sidebar:
        st.markdown(f"""
            <div style='padding: 10px; border-bottom: 1px solid #eee; margin-bottom: 10px;'>
                <p style='margin:0; font-size: 10px; color: #888;'>USUARIO ACTIVO</p>
                <p style='margin:0; font-size: 12px; font-weight: bold; color: #333;'>{user_actual.email}</p>
            </div>
        """, unsafe_allow_html=True)

        if st.button("🔄 Refrescar", use_container_width=True):
             st.session_state["key_menu"] += 1
             st.rerun()

        lista_opciones = ["Inicio", "Cargar Ventas", "Pagos", "Gastos Operativos"]
        lista_iconos = ["house", "cloud-upload", "cash-coin", "receipt"]

        seleccion = option_menu(
            "", 
            lista_opciones,
            icons=lista_iconos, 
            menu_icon="cast", default_index=0,
            key=f'menu_saas_final_{st.session_state["key_menu"]}',
            styles={
                "container": {"padding": "0!important", "background-color": "#fafafa"},
                "icon": {"color": "#ff9800", "font-size": "14px"}, 
                "nav-link": {"font-size": "12px", "text-align": "left", "margin": "0px", "--hover-color": "#eee"},
                "nav-link-selected": {"background-color": "#02ab21"},
            }
        )

        st.divider()
        if st.button("🚪 Cerrar Sesión", use_container_width=True, type="secondary"):
            st.session_state.taquilla_autenticada = False
            st.rerun()

    # Mapeo (Si no existen estas funciones en este archivo, el menú no hará nada)
    paginas = {
        "Inicio": lambda: st.write("Bienvenido"), 
        "Cargar Ventas": lambda: modulo_registro_taquilla(ag), 
        "Pagos": lambda: st.write("Módulo Pagos"),
        "Gastos Operativos": lambda: st.write("Módulo Gastos")
    }

    if seleccion in paginas:
        paginas[seleccion]()
