import streamlit as st
import pandas as pd
from utils import supabase, obtener_periodo_trabajo, verificar_suscripcion
from datetime import datetime
from streamlit_option_menu import option_menu

# 📱 1. DETECCIÓN MÓVIL GLOBAL (Inicialización)
user_agent = st.context.headers.get("User-Agent", "").lower()
if "ipad" in user_agent or ("android" in user_agent and "mobile" not in user_agent):
    st.session_state["dispositivo"] = "Tablet"
elif any(word in user_agent for word in ["iphone", "android", "blackberry", "opera mini"]):
    st.session_state["dispositivo"] = "Teléfono"
else:
    st.session_state["dispositivo"] = "Escritorio"

# 🚀 CONTROL DEL MENÚ LATERAL BASE
if st.session_state.get("dispositivo") in ["Teléfono", "Tablet"]:
    estado_sidebar = "collapsed"
else:
    estado_sidebar = "expanded"

# CONFIGURACIÓN DE PÁGINA OBLIGATORIA
st.set_page_config(
    page_title="Taquilla POS", 
    layout="wide", 
    initial_sidebar_state=estado_sidebar
)

# --- FUNCIÓN DE REGISTRO (Cargar Ventas) ---
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
                if venta >= 0:
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
                        st.error(f"Error al guardar: {e}")
                else:
                    st.warning("Ingrese un monto válido.")

# --- MÓDULO DE AUDITORÍA ---
def modulo_auditoria_hibrida():
    res_actual = supabase.table("carga_actual").select("*").execute()
    df_actual = pd.DataFrame(res_actual.data)
    res_taq = supabase.table("cda_reportes_diarios").select("*").execute()
    df_taq = pd.DataFrame(res_taq.data)
    
    if not df_taq.empty:
        df_taq = df_taq.rename(columns={"monto_venta": "venta", "monto_premios": "premios", "nombre_agency": "agencia"})
    
    df_final = pd.concat([df_actual, df_taq], ignore_index=True)
    divisa = st.selectbox("Seleccione Divisa:", ["COP", "BS", "USD"])
    res_ofi = supabase.table("carga_oficial").select("*").eq("moneda", divisa).execute()
    df_oficial = pd.DataFrame(res_ofi.data)

    if not df_final.empty:
        taq_group = df_final[df_final['moneda'] == divisa].groupby(['agencia', 'sistema']).agg({'venta': 'sum', 'comision': 'sum', 'premios': 'sum'}).reset_index()
        if not df_oficial.empty:
            df_oficial.columns = [c.lower() for c in df_oficial.columns]
            df_auditoria = pd.merge(df_oficial, taq_group, on=['agencia', 'sistema'], suffixes=('_ofi', '_taq'), how='outer').fillna(0)
            st.subheader(f"📊 Resumen Financiero ({divisa})")
            st.dataframe(df_auditoria[['agencia', 'sistema', 'venta_ofi', 'venta_taq', 'comision_ofi', 'comision_taq', 'premios_ofi', 'premios_taq']].style.format("{:,.2f}"), use_container_width=True)
        else:
            st.warning("No se encontraron datos oficiales.")
    else:
        st.info("No hay datos de carga en la taquilla.")

# --- LÓGICA DE LOGIN ---
if "taquilla_autenticada" not in st.session_state:
    st.session_state.taquilla_autenticada = False

if not st.session_state.taquilla_autenticada:
    st.session_state["menu_colapsado_post_login"] = False
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
    # 📱 TRUCO MAESTRO REFORZADO: Cierre automático en móviles
    if "menu_colapsado_post_login" in st.session_state and not st.session_state["menu_colapsado_post_login"]:
        if st.session_state["dispositivo"] in ["Teléfono", "Tablet"]:
            import streamlit.components.v1 as components
            components.html(
                """
                <script>
                function intentarColapsarMenu() {
                    try {
                        var doc = window.parent.document;
                        var sidebar = doc.querySelector('section[data-testid="stSidebar"]');
                        if (sidebar && sidebar.getAttribute('data-collapsed') === 'false') {
                            var closeBtn = doc.querySelector('button[data-testid="stSidebarCollapseButton"]');
                            if (closeBtn) closeBtn.click();
                        }
                    } catch (e) { console.log(e); }
                }
                setTimeout(intentarColapsarMenu, 300);
                setTimeout(intentarColapsarMenu, 700);
                </script>
                """, height=0, width=0
            )
        st.session_state["menu_colapsado_post_login"] = True

    # 3. VALIDACIÓN DE LICENCIA
    acceso_ok, msg_error = verificar_suscripcion()
    ag = st.session_state.agencia_actual
    periodo = obtener_periodo_trabajo(ag['user_id'])
    
    with st.sidebar:
        if not acceso_ok:
            st.error(msg_error)
            st.stop()
            
        st.info(f"📅 Ciclo: {periodo['desde']} al {periodo['hasta']}")
        seleccion = option_menu("Menú", ["Auditoría", "Cargar Ventas"], icons=["shield-check", "cloud-upload"])
        if st.button("🚪 Cerrar Sesión"):
            st.session_state.taquilla_autenticada = False
            st.rerun()

    if seleccion == "Auditoría":
        modulo_auditoria_hibrida()
    elif seleccion == "Cargar Ventas":
        modulo_registro_taquilla(ag)
