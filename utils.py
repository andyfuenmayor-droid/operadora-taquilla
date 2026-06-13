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

def modulo_auditoria_hibrida():
    # 1. CARGA DE DATOS (TAQUILLA + CARGA ACTUAL)
    res_actual = supabase.table("carga_actual").select("*").execute()
    df_actual = pd.DataFrame(res_actual.data)
    
    res_taq = supabase.table("cda_reportes_diarios").select("*").execute()
    df_taq = pd.DataFrame(res_taq.data)
    
    if not df_taq.empty:
        df_taq = df_taq.rename(columns={
            "monto_venta": "venta",
            "monto_premios": "premios",
            "nombre_agency": "agencia"
        })
    
    # Combinar todas las cargas de taquilla
    df_final = pd.concat([df_actual, df_taq], ignore_index=True)
    
    # 2. SELECCIÓN DE DIVISA
    divisa = st.selectbox("Seleccione Divisa:", ["COP", "BS", "USD"])
    
    # 3. CARGA DE OFICIAL (Supongamos que tu tabla oficial se llama 'carga_oficial')
    # Ajusta el nombre de la tabla si es diferente
    res_ofi = supabase.table("carga_oficial").select("*").eq("moneda", divisa).execute()
    df_oficial = pd.DataFrame(res_ofi.data)

    # 4. AGRUPACIÓN Y CRUCE
    if not df_final.empty:
        # Agrupamos la taquilla por Agencia y Sistema
        taq_group = df_final[df_final['moneda'] == divisa].groupby(['agencia', 'sistema']).agg({
            'venta': 'sum', 'comision': 'sum', 'premios': 'sum'
        }).reset_index()

        # Si tienes df_oficial, hacemos el merge
        if not df_oficial.empty:
            # Aseguramos nombres de columnas alineados para el merge
            df_oficial.columns = [c.lower() for c in df_oficial.columns]
            
            # Cruzamos los datos
            df_auditoria = pd.merge(df_oficial, taq_group, on=['agencia', 'sistema'], suffixes=('_ofi', '_taq'), how='outer').fillna(0)
            
            # 5. MOSTRAR TABLA
            st.subheader(f"📊 Resumen Financiero ({divisa})")
            
            # Filtramos para mostrar las columnas que pediste
            columnas_finales = [
                'agencia', 'sistema', 
                'venta_ofi', 'venta_taq', 
                'comision_ofi', 'comision_taq', 
                'premios_ofi', 'premios_taq'
            ]
            
            # Formato de visualización
            st.dataframe(df_auditoria[columnas_finales].style.format("{:,.2f}", subset=['venta_ofi', 'venta_taq', 'comision_ofi', 'comision_taq', 'premios_ofi', 'premios_taq']), use_container_width=True)

            # 6. TOTALES GLOBALES
            c1, c2, c3 = st.columns(3)
            c1.metric("Ventas (Ofi/Taq)", f"{df_auditoria['venta_ofi'].sum():,.0f} / {df_auditoria['venta_taq'].sum():,.0f}")
            c2.metric("Premios (Ofi/Taq)", f"{df_auditoria['premios_ofi'].sum():,.0f} / {df_auditoria['premios_taq'].sum():,.0f}")
            c3.metric("Comisiones (Ofi/Taq)", f"{df_auditoria['comision_ofi'].sum():,.0f} / {df_auditoria['comision_taq'].sum():,.0f}")

        else:
            st.warning("No se encontraron datos oficiales para comparar.")
    else:
        st.info("No hay datos de carga en la taquilla.")
