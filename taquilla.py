import streamlit as st
from utils import supabase
from datetime import datetime

def modulo_registro_taquilla(agencia_data):
    st.header(f"➕ Registro Manual: {agencia_data['nombre_agencia']}")
    
    # Obtenemos los sistemas permitidos configurados en el Admin
    sistemas_lista = [s.strip() for s in str(agencia_data.get("sistemas", "BETM3")).split(",")]
    
    # Iteramos sobre cada sistema para mostrar su formulario
    for sist in sistemas_lista:
        with st.container(border=True):
            st.markdown(f"#### 📍 Sistema: {sist}")
            
            # Usamos columnas para un diseño limpio
            col1, col2, col3, col4 = st.columns(4)
            
            # Campos de entrada
            # Usamos keys dinámicas para que no interfieran entre sistemas
            venta = col1.number_input(f"Venta", min_value=0.0, format="%.2f", key=f"venta_{sist}")
            comision = col2.number_input(f"Comisión", min_value=0.0, format="%.2f", key=f"comi_{sist}")
            premios = col3.number_input(f"Premios", min_value=0.0, format="%.2f", key=f"prem_{sist}")
            
            # Cálculo dinámico del Neto
            neto_calculado = venta - comision - premios
            col4.metric("Neto Calculado", f"{neto_calculado:,.2f}")
            
            # Botón de guardar individual para este sistema
            if st.button(f"🚀 Guardar {sist}", key=f"btn_{sist}"):
                if venta > 0:
                    try:
                        data_registro = {
                            "nombre_agency": agencia_data['nombre_agencia'], # Campo específico de taquilla
                            "sistema": sist,
                            "monto_venta": venta,
                            "monto_premios": premios,
                            "comision": comision,
                            "neto": neto_calculado,
                            "fecha": datetime.now().strftime("%Y-%m-%d"),
                            "moneda": "COP" # O la lógica que maneje tu taquilla
                        }
                        # Insertar en la tabla de taquilla
                        supabase.table("cda_reportes_diarios").insert(data_registro).execute()
                        st.success(f"✅ {sist} registrado correctamente.")
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")
                else:
                    st.warning("Debes ingresar un monto de venta.")

    if st.button("🧹 LIMPIAR PANTALLA"):
        st.rerun()
