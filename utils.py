import streamlit as st
import pandas as pd
from utils import supabase, obtener_periodo_trabajo
from datetime import datetime
from streamlit_option_menu import option_menu

# 1. ESTO DEBE SER SIEMPRE LO PRIMERO
st.set_page_config(page_title="Taquilla POS", layout="wide")

# --- MÓDULO DE REGISTRO (Cargar Ventas) ---
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
    periodo = obtener_periodo_trabajo(ag['user_id'])
    
    with st.sidebar:
        st.info(f"📅 Ciclo: {periodo['desde']} al {periodo['hasta']}")
        seleccion = option_menu("Menú", ["Auditoría", "Cargar Ventas"], icons=["shield-check", "cloud-upload"])
        if st.button("🚪 Cerrar Sesión"):
            st.session_state.taquilla_autenticada = False
            st.rerun()

    if seleccion == "Auditoría":
        modulo_auditoria_hibrida()
    elif seleccion == "Cargar Ventas":
        modulo_registro_taquilla(ag)
