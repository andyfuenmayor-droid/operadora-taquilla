import streamlit as st
import pandas as pd
from utils import supabase, obtener_periodo_trabajo, verificar_suscripcion
from datetime import datetime

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

# --- FUNCIÓN UNIFICADA DE REGISTRO (Cargar Ventas) ---
def modulo_registro_taquilla(agencia_data):
    st.header(f"🎰 Carga de Ventas: {agencia_data['nombre_agencia']}")
    
    # Separamos los sistemas configurados para esta agencia
    sistemas_lista = [s.strip() for s in str(agencia_data.get("sistemas", "BETM3")).split(",")]
    
    for sist in sistemas_lista:
        with st.container(border=True):
            st.markdown(f"#### 📍 Sistema: {sist}")
            c1, c2, c3, c4 = st.columns(4)
            
            venta = c1.number_input(f"Venta", min_value=0.0, format="%.2f", key=f"v_{sist}")
            comision = c2.number_input(f"Comisión", min_value=0.0, format="%.2f", key=f"c_{sist}")
            premios = c3.number_input(f"Premios", min_value=0.0, format="%.2f", key=f"p_{sist}")
            
            neto_calculado = venta - comision - premios
            c4.metric("Neto Calculated", f"{neto_calculado:,.2f}")
            
            if st.button(f"🚀 Guardar {sist}", key=f"btn_{sist}"):
                if venta >= 0:
                    try:
                        # Extraemos el cajero actual si existe en la sesión para guardarlo como auditoría
                        cajero_id_val = st.session_state.cajero_actual["id"] if "cajero_actual" in st.session_state else None
                        
                        data = {
                            "nombre_agency": agencia_data['nombre_agencia'],
                            "sistema": sist,
                            "monto_venta": venta,
                            "monto_premios": premios,
                            "comision": comision,
                            "neto": neto_calculado,
                            "fecha": datetime.now().strftime("%Y-%m-%d"),
                            "moneda": "COP",
                            "user_id": agencia_data['user_id'],
                            "cajero_id": cajero_id_val # Nueva columna relacional de auditoría
                        }
                        supabase.table("cda_reportes_diarios").insert(data).execute()
                        st.success(f"✅ {sist} registrado con éxito!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar en base de datos: {e}")
                else:
                    st.warning("Ingrese un monto válido.")

# --- NUEVA LÓGICA DE LOGIN RELACIONAL POR USUARIO ---
if "taquilla_autenticada" not in st.session_state:
    st.session_state.taquilla_autenticada = False

if not st.session_state.taquilla_autenticada:
    st.session_state["menu_colapsado_post_login"] = False
    st.title("🔐 Acceso Taquilla POS")
    
    user_input = st.text_input("Usuario de Taquilla").strip().lower()
    key_input = st.text_input("Clave / PIN de Acceso", type="password").strip()
    
    if st.button("Ingresar al Sistema"):
        # Validación directa contra la nueva tabla multiusuario
        res = supabase.table("taquilla_usuarios")\
            .select("*, agencias(*)")\
            .eq("usuario", user_input)\
            .eq("clave", key_input)\
            .eq("activo", True)\
            .execute()
            
        if res.data:
            user_data = res.data[0]
            st.session_state.taquilla_autenticada = True
            st.session_state.agencia_actual = user_data["agencias"]
            st.session_state.cajero_actual = {
                "id": user_data["id"],
                "usuario": user_data["usuario"],
                "rol": user_data["rol"],
                "nombre": user_data["nombre_cajero"]
            }
            # Marcar último ingreso en base de datos
            supabase.table("taquilla_usuarios").update({"ultimo_ingreso": datetime.now().isoformat()}).eq("id", user_data["id"]).execute()
            st.rerun()
        else:
            st.error("❌ Datos incorrectos o usuario desactivado.")
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

    # VALIDACIÓN DE LICENCIA SILENCIOSA
    acceso_ok, msg_error = verificar_suscripcion()
    ag = st.session_state.agencia_actual
    cajero = st.session_state.cajero_actual
    periodo = obtener_periodo_trabajo(ag['user_id'])
    
    # BARRA LATERAL SIMPLIFICADA
    with st.sidebar:
        if not acceso_ok:
            st.error(msg_error)
            st.stop()
            
        st.info(f"📅 Ciclo Activo:\n{periodo['desde']} al {periodo['hasta']}")
        st.write(f"**Terminal:** {ag['nombre_agencia']}")
        st.write(f"**Usuario:** {cajero['nombre'] if cajero['nombre'] else cajero['usuario'].upper()}")
        st.write(f"**Rol:** `{cajero['rol'].upper()}`")
        st.divider()
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            st.session_state.taquilla_autenticada = False
            st.rerun()

    # EJECUCIÓN DIRECTA DEL MÓDULO DE CARGA
    modulo_registro_taquilla(ag)

    # 🛡️ 3. VISTA EXCLUSIVA PARA EL ROL SUPERVISOR (FUSIONADA Y CORREGIDA)
    if cajero['rol'] == 'supervisor':
        st.markdown("---")
        st.subheader("🛡️ Panel Administrativo de Supervisión")
        st.caption("Herramientas de control de turnos, corrección de errores y visualización de cierres.")
        
        tab_cierres, tab_correcciones = st.tabs(["📊 Cierres y Totales", "✏️ Corrección de Errores"])
        
        # Inicializamos df_turno vacío por seguridad para evitar NameError en las pestañas cruzadas
        df_turno = pd.DataFrame()
        
        try:
            res_v = supabase.table("cda_reportes_diarios")\
                .select("sistema, monto_venta, monto_premios, comision, neto, fecha")\
                .eq("nombre_agency", ag['nombre_agencia'])\
                .gte("fecha", periodo['desde'])\
                .lte("fecha", periodo['hasta'])\
                .execute()
            df_turno = pd.DataFrame(res_v.data or [])
        except Exception as e:
            st.error(f"Error al conectar con los reportes del ciclo: {e}")
        
        with tab_cierres:
            st.markdown(f"#### 📈 Acumulado del Ciclo Active ({ag['nombre_agencia']})")
            if not df_turno.empty:
                c1, c2, c3 = st.columns(3)
                c1.metric("Total Ventas", f"{df_turno['monto_venta'].sum():,.2f} COP")
                c2.metric("Total Premios", f"{df_turno['monto_premios'].sum():,.2f} COP")
                c3.metric("Neto de Caja", f"{df_turno['neto'].sum():,.2f} COP")
                
                st.dataframe(df_turno, use_container_width=True, hide_index=True)
            else:
                st.info("💡 No se han registrado ventas en este ciclo todavía.")
                
        with tab_correcciones:
            st.markdown("#### ✏️ Modificar Registro Diario")
            st.caption("Selecciona un registro ingresado por los cajeros para corregir montos erróneos.")
            
            if not df_turno.empty:
                df_turno["opcion_select"] = df_turno["fecha"] + " - " + df_turno["sistema"] + " (Neto: " + df_turno["neto"].astype(str) + ")"
                registro_sel = st.selectbox("Seleccione el reporte a corregir:", df_turno["opcion_select"].tolist())
                
                fila_editar = df_turno[df_turno["opcion_select"] == registro_sel].iloc[0]
                
                with st.form(key=f"form_corregir_err"):
                    st.markdown(f"**Modificando:** `{fila_editar['sistema']}` del día `{fila_editar['fecha']}`")
                    v_edit = st.number_input("Nueva Venta", min_value=0.0, value=float(fila_editar['monto_venta']), format="%.2f")
                    c_edit = st.number_input("Nueva Comisión", min_value=0.0, value=float(fila_editar['comision']), format="%.2f")
                    p_edit = st.number_input("Nuevo Premio", min_value=0.0, value=float(fila_editar['monto_premios']), format="%.2f")
                    
                    if st.form_submit_button("💾 Aplicar Corrección"):
                        nuevo_neto = v_edit - c_edit - p_edit
                        try:
                            supabase.table("cda_reportes_diarios")\
                                .update({
                                    "monto_venta": v_edit,
                                    "comision": c_edit,
                                    "monto_premios": p_edit,
                                    "neto": nuevo_neto
                                })\
                                .eq("nombre_agency", ag['nombre_agencia'])\
                                .eq("fecha", fila_editar['fecha'])\
                                .eq("sistema", fila_editar['sistema'])\
                                .execute()
                                
                            st.success("✅ ¡Registro corregido perfectamente!")
                            st.rerun()
                        except Exception as error_up:
                            st.error(f"No se pudo actualizar: {error_up}")
            else:
                st.info("💡 No hay registros disponibles para corregir en este ciclo.")
