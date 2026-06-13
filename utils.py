# utils.py
import streamlit as st
import pandas as pd
from supabase import create_client

st.set_page_config(page_title="Taquilla POS", layout="wide")

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

# --- MÓDULO DE AUDITORÍA ---
def modulo_auditoria_hibrida():
    # 1. Leer de carga_actual (datos antiguos o de Admin)
    res_actual = supabase.table("carga_actual").select("*").execute()
    df_actual = pd.DataFrame(res_actual.data)
    
    # 2. Leer de cda_reportes_diarios (datos de la Taquilla nueva)
    res_taq = supabase.table("cda_reportes_diarios").select("*").execute()
    df_taq = pd.DataFrame(res_taq.data)
    
    if not df_taq.empty:
        df_taq = df_taq.rename(columns={
            "monto_venta": "venta",
            "monto_premios": "premios",
            "nombre_agency": "agencia"
        })
    
    # Combinar todas las cargas
    df_final = pd.concat([df_actual, df_taq], ignore_index=True)
    
    # 2. SELECCIÓN DE DIVISA
    divisa = st.selectbox("Seleccione Divisa:", ["COP", "BS", "USD"])
    
    # 3. CARGA DE OFICIAL
    res_ofi = supabase.table("carga_oficial").select("*").eq("moneda", divisa).execute()
    df_oficial = pd.DataFrame(res_ofi.data)

    # 4. AGRUPACIÓN Y CRUCE
    if not df_final.empty:
        taq_group = df_final[df_final['moneda'] == divisa].groupby(['agencia', 'sistema']).agg({
            'venta': 'sum', 'comision': 'sum', 'premios': 'sum'
        }).reset_index()

        if not df_oficial.empty:
            df_oficial.columns = [c.lower() for c in df_oficial.columns]
            df_auditoria = pd.merge(df_oficial, taq_group, on=['agencia', 'sistema'], suffixes=('_ofi', '_taq'), how='outer').fillna(0)
            
            st.subheader(f"📊 Resumen Financiero ({divisa})")
            columnas_finales = ['agencia', 'sistema', 'venta_ofi', 'venta_taq', 'comision_ofi', 'comision_taq', 'premios_ofi', 'premios_taq']
            st.dataframe(df_auditoria[columnas_finales].style.format("{:,.2f}"), use_container_width=True)

            c1, c2, c3 = st.columns(3)
            c1.metric("Ventas (Ofi/Taq)", f"{df_auditoria['venta_ofi'].sum():,.0f} / {df_auditoria['venta_taq'].sum():,.0f}")
            c2.metric("Premios (Ofi/Taq)", f"{df_auditoria['premios_ofi'].sum():,.0f} / {df_auditoria['premios_taq'].sum():,.0f}")
        else:
            st.warning("No se encontraron datos oficiales.")
    else:
        st.info("No hay datos de carga en la taquilla.")

# --- LÓGICA DE LOGIN Y APP ---
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
    admin_id = ag['user_id']
    periodo = obtener_periodo_trabajo(admin_id)
    
    with st.sidebar:
        st.info(f"📅 Ciclo: {periodo['desde']} al {periodo['hasta']}")
        seleccion = option_menu("Menú", ["Auditoría", "Cargar Ventas"], icons=["shield-check", "cloud-upload"])
        if st.button("🚪 Cerrar Sesión"):
            st.session_state.taquilla_autenticada = False
            st.rerun()

    if seleccion == "Auditoría":
        modulo_auditoria_hibrida()
    elif seleccion == "Cargar Ventas":
        # Aquí llamarías a tu función modulo_registro_taquilla
        st.write("Módulo de Carga")
