import streamlit as st
import pandas as pd
import time
import urllib.parse
from utils import supabase
from datetime import datetime, timedelta

user_agent = st.context.headers.get("User-Agent", "").lower()
if "ipad" in user_agent or ("android" in user_agent and "mobile" not in user_agent):
    st.session_state["dispositivo"] = "Tablet"
elif any(word in user_agent for word in ["iphone", "android", "blackberry", "opera mini"]):
    st.session_state["dispositivo"] = "Teléfono"
else:
    st.session_state["dispositivo"] = "Escritorio"

st.set_page_config(
    page_title="Taquilla POS",
    page_icon="assets/pos_icon.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Anti-cache meta tags, JS auto-clearing script y CSS para visibilidad de controles
st.markdown("""
    <head>
        <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate" />
        <meta http-equiv="Pragma" content="no-cache" />
        <meta http-equiv="Expires" content="0" />
    </head>
    <script>
    (function() {
        var V = "2026.07.20-v3.1.0";
        var cur = localStorage.getItem("taquilla_build_v3");
        if (!cur) {
            localStorage.setItem("taquilla_build_v3", V);
        } else if (cur !== V) {
            localStorage.clear();
            sessionStorage.clear();
            localStorage.setItem("taquilla_build_v3", V);
            if ('caches' in window) { caches.keys().then(function(ks){ for(var i=0; i<ks.length; i++) caches.delete(ks[i]); }); }
            if ('serviceWorker' in navigator) { navigator.serviceWorker.getRegistrations().then(function(rs){ for(var j=0; j<rs.length; j++) rs[j].unregister(); }); }
            window.location.reload(true);
        }
    })();
    </script>
    <style>
    /* Estilos del Login en la carga inicial (Frame 1) */
    form[data-testid="stForm"],
    div[data-testid="stForm"] {
        background-color: rgba(15, 23, 42, 0.75) !important;
        backdrop-filter: blur(24px) !important;
        -webkit-backdrop-filter: blur(24px) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 24px !important;
        padding: 2.5rem 2rem !important;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.6) !important;
        width: 100% !important;
        max-width: 533px !important;
        margin: 0 auto !important;
    }
    [data-testid="stForm"] > div {
        gap: 1.25rem !important;
    }
    [data-testid="stWidgetLabel"] p {
        color: #94a3b8 !important;
        font-weight: 600 !important;
        font-size: 0.75rem !important;
        letter-spacing: 0.05em !important;
        text-transform: uppercase !important;
        margin-bottom: 0.35rem !important;
    }
    div[data-baseweb="input"],
    div[data-baseweb="input"] > div,
    div[data-baseweb="input"] input {
        background-color: #0f172a !important;
        color: #f8fafc !important;
        border-color: rgba(255, 255, 255, 0.08) !important;
        border-radius: 10px !important;
    }
    div[data-baseweb="input"]:focus-within {
        border-color: #6366f1 !important;
    }
    input {
        color: #f8fafc !important;
        font-size: 0.95rem !important;
    }
    [data-testid="stFormSubmitButton"] button {
        width: 100% !important;
        background: linear-gradient(90deg, #6366f1 0%, #8b5cf6 100%) !important;
        color: #ffffff !important;
        border: none !important;
        padding: 0.75rem 1.5rem !important;
        border-radius: 12px !important;
        font-size: 0.95rem !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 12px rgba(99, 102, 241, 0.35) !important;
        margin-top: 0.5rem !important;
    }
    [data-testid="collapsedControl"] {
        display: flex !important;
        visibility: visible !important;
        z-index: 999999 !important;
        position: fixed !important;
        top: 10px !important;
        left: 10px !important;
        background-color: #1e293b !important;
        color: #ffffff !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        border-radius: 8px !important;
        padding: 4px !important;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3) !important;
    }
    [data-testid="stHeader"] {
        background-color: transparent !important;
    }
    [data-testid="stDecoration"] {
        display: none !important;
    }
    [data-testid="stToolbar"] {
        display: none !important;
    }
    .stAppDeployButton {
        display: none !important;
    }
    #MainMenu {
        visibility: hidden !important;
    }
    footer {
        visibility: hidden !important;
    }
    </style>
""", unsafe_allow_html=True)


if "tema_oscuro" not in st.session_state:
    st.session_state.tema_oscuro = True

# ? helpers de cierre diario ?

def _check_cerrado_col():
    """Verifica que la columna `cerrado` exista en cda_reportes_diarios."""
    if "check_ok" not in st.session_state:
        try:
            supabase.table("cda_reportes_diarios").select("cerrado").limit(1).execute()
            st.session_state["check_ok"] = True
        except Exception:
            st.session_state["check_ok"] = False
            st.warning(
                "⚠️ La columna `cerrado` NO existe en `cda_reportes_diarios`. "
                "Ejecuta este SQL en el Editor SQL de Supabase:\n\n"
                "```sql\n"
                "ALTER TABLE cda_reportes_diarios ADD COLUMN cerrado BOOLEAN DEFAULT FALSE;\n"
                "```"
            )
    return st.session_state["check_ok"]

def dia_esta_cerrado(agencia_nombre, fecha):
    """Retorna True si el día ya fue cerrado para esta agencia."""
    try:
        res = supabase.table("cda_reportes_diarios")\
            .select("cerrado")\
            .eq("nombre_agency", agencia_nombre)\
            .eq("fecha", str(fecha))\
            .eq("cerrado", True)\
            .limit(1)\
            .execute()
        return len(res.data or []) > 0
    except Exception:
        return False

def cerrar_dia(agencia_nombre, fecha, cajero_id):
    """Marca todas las filas del día como cerrado=True."""
    try:
        supabase.table("cda_reportes_diarios")\
            .update({"cerrado": True})\
            .eq("nombre_agency", agencia_nombre)\
            .eq("fecha", str(fecha))\
            .execute()
        return True
    except Exception as e:
        st.error(f"Error al cerrar el día: {e}")
        return False

def reabrir_dia(agencia_nombre, fecha):
    """Marca todas las filas del día como cerrado=False (supervisor)."""
    try:
        supabase.table("cda_reportes_diarios")\
            .update({"cerrado": False})\
            .eq("nombre_agency", agencia_nombre)\
            .eq("fecha", str(fecha))\
            .execute()
        return True
    except Exception as e:
        st.error(f"Error al reabrir el día: {e}")
        return False

def obtener_ultimo_dia_cerrado(agencia_nombre):
    """Retorna la última fecha cerrada, o None si no hay ninguna."""
    try:
        res = supabase.table("cda_reportes_diarios")\
            .select("fecha")\
            .eq("nombre_agency", agencia_nombre)\
            .eq("cerrado", True)\
            .order("fecha", desc=True)\
            .limit(1)\
            .execute()
        if res.data:
            fecha = res.data[0]["fecha"]
            return pd.to_datetime(fecha).date()
    except Exception:
        pass
    return None


# �?� módulos de la taquilla �?�
def modulo_registro_taquilla(agencia_data):
    st.header(f"🎰 Carga de Ventas: {agencia_data['nombre_agencia']}")
    rol_usuario = st.session_state.get("cajero_actual", {}).get("rol", "cajero")
    es_supervisor = (rol_usuario == 'supervisor')
    sistemas_lista = [s.strip() for s in str(agencia_data.get("sistemas", "BETM3")).split(",")]

    if "fecha_carga_actual" not in st.session_state:
        st.session_state["fecha_carga_actual"] = obtener_ultimo_dia_cerrado(agencia_data['nombre_agencia']) or datetime.now().date()

    fecha_seleccionada = st.date_input(
        "📅 Seleccione el día a cargar:",
        value=st.session_state["fecha_carga_actual"],
        key="fecha_carga_input",
        on_change=lambda: setattr(st.session_state, 'fecha_carga_actual', st.session_state["fecha_carga_input"])
    )
    fecha_carga_iso = str(fecha_seleccionada)

    cerrado = dia_esta_cerrado(agencia_data['nombre_agencia'], fecha_carga_iso)
    if cerrado:
        if es_supervisor:
            st.warning(f"🔒 El día {fecha_carga_iso} está **cerrado**. Solo un supervisor puede reabrirlo.")
        else:
            st.error(f"🔒 El día {fecha_carga_iso} ya fue cerrado. Contacta al supervisor para modificarlo.")
            return

    try:
        res_existentes = supabase.table("cda_reportes_diarios")\
            .select("*")\
            .eq("nombre_agency", agencia_data['nombre_agencia'])\
            .eq("fecha", fecha_carga_iso)\
            .execute()
        df_existentes = pd.DataFrame(res_existentes.data or [])
        if not df_existentes.empty:
            df_existentes.columns = [c.lower() for c in df_existentes.columns]
    except Exception:
        df_existentes = pd.DataFrame()

    st.info("🎟️ Los premios se registran exclusivamente en el módulo **Tickets Premiados**.")

    for sist in sistemas_lista:
        with st.container(border=True):
            st.markdown(f"#### 📍 Sistema: {sist}")
            existe_en_db = False
            v_val, c_val, p_val = 0.0, 0.0, 0.0
            if not df_existentes.empty:
                match = df_existentes[df_existentes["sistema"] == sist]
                if not match.empty:
                    existe_en_db = True
                    row = match.iloc[0]
                    v_val = float(row.get("monto_venta", 0))
                    c_val = float(row.get("comision", 0))
                    p_val = float(row.get("monto_premios", 0))

            c1, c2, c3 = st.columns(3)
            venta = c1.number_input("Venta", min_value=0.0, format="%.2f", key=f"v_{sist}_{fecha_carga_iso}", value=v_val)
            comision = c2.number_input("Comisión", min_value=0.0, format="%.2f", key=f"c_{sist}_{fecha_carga_iso}", value=c_val)
            premios_vista = c3.number_input("Premios (solo vista)", format="%.2f", value=p_val, disabled=True, key=f"p_{sist}_{fecha_carga_iso}_view")

            texto_boton = "💾 Guardar Cambios" if existe_en_db else "🚀 Guardar"
            if st.button(f"{texto_boton} {sist}", key=f"btn_{sist}"):
                try:
                    monto_premios_existente = p_val if existe_en_db else 0
                    data = {
                        "sistema": sist,
                        "monto_venta": venta,
                        "monto_premios": monto_premios_existente,
                        "comision": comision,
                        "neto": venta - comision - monto_premios_existente,
                        "moneda": "COP",
                        "user_id": agencia_data['user_id'],
                        "cajero_id": st.session_state.get("cajero_actual", {}).get("id")
                    }
                    if existe_en_db:
                        supabase.table("cda_reportes_diarios")\
                            .update(data)\
                            .eq("nombre_agency", agencia_data['nombre_agencia'])\
                            .eq("fecha", fecha_carga_iso)\
                            .eq("sistema", sist)\
                            .execute()
                        st.success(f"✅ {sist} guardado!")
                    else:
                        data["nombre_agency"] = agencia_data['nombre_agencia']
                        data["fecha"] = fecha_carga_iso
                        supabase.table("cda_reportes_diarios").insert(data).execute()
                        st.success(f"✅ {sist} registrado para el {fecha_carga_iso}!")
                    time.sleep(1.2); st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")


def modulo_gastos(agencia_data):
    st.header("💸 Gestión de Gastos")
    u_id = agencia_data['user_id']
    ag_nombre = agencia_data['nombre_agencia']

    if "fecha_gasto_filtro" not in st.session_state:
        st.session_state["fecha_gasto_filtro"] = obtener_ultimo_dia_cerrado(ag_nombre) or datetime.now().date()

    fecha_filtro = st.date_input(
        "📅 Ver gastos del día:",
        value=st.session_state["fecha_gasto_filtro"],
        key="fecha_gasto_filtro_input"
    )

    cerrado = dia_esta_cerrado(ag_nombre, fecha_filtro)
    if cerrado:
        st.info(f"🔒 El día {fecha_filtro} está cerrado. No se pueden registrar nuevos gastos.")

    try:
        res_g = supabase.table("cda_gastos_diarios").select("*").eq("user_id", u_id).eq("fecha", str(fecha_filtro)).execute()
        df_g = pd.DataFrame(res_g.data or [])
        if not df_g.empty:
            df_g.columns = [c.lower() for c in df_g.columns]
    except Exception:
        df_g = pd.DataFrame()

    if not df_g.empty:
        cols_orden = ["id", "agencia", "moneda", "monto", "concepto", "fecha", "created_at", "user_id"]
        cols_existentes = [c for c in cols_orden if c in df_g.columns]
        st.dataframe(df_g[cols_existentes], use_container_width=True, hide_index=True)
    else:
        st.info("ℹ️ No hay gastos en este día.")

    if not cerrado:
        with st.container(border=True):
            st.subheader("📝 Registrar Nuevo Gasto")
            with st.form("form_g", clear_on_submit=True):
                c1, c2, c3 = st.columns([1, 1, 2])
                fecha_g = c1.date_input("Fecha", value=fecha_filtro)
                moneda_g = c2.selectbox("Moneda", ["COP", "USD", "BS"], index=0)
                monto_g = c3.number_input("Monto", min_value=0.0, format="%.2f")
                concepto_g = st.text_input("Concepto:")
                if st.form_submit_button("💾 GUARDAR", use_container_width=True):
                    if not concepto_g.strip() or monto_g <= 0:
                        st.error("Complete los campos.")
                    else:
                        supabase.table("cda_gastos_diarios").insert({
                            "fecha": str(fecha_g), "agencia": ag_nombre,
                            "concepto": concepto_g.upper().strip(),
                            "monto": round(float(monto_g), 2),
                            "moneda": moneda_g, "user_id": u_id
                        }).execute()
                        st.success("✅ Gasto guardado!"); time.sleep(1); st.rerun()


def modulo_pagos(agencia_data):
    st.header("💰 Recepción de Pagos")
    u_id = agencia_data['user_id']
    ag_nombre = agencia_data['nombre_agencia']

    if "fecha_pago_filtro" not in st.session_state:
        st.session_state["fecha_pago_filtro"] = obtener_ultimo_dia_cerrado(ag_nombre) or datetime.now().date()

    fecha_filtro = st.date_input(
        "📅 Ver pagos del día:",
        value=st.session_state["fecha_pago_filtro"],
        key="fecha_pago_filtro_input"
    )

    cerrado = dia_esta_cerrado(ag_nombre, fecha_filtro)
    if cerrado:
        st.info(f"🔒 El día {fecha_filtro} está cerrado. No se pueden registrar nuevos pagos.")

    try:
        res_p = supabase.table("cda_pagos_diarios").select("*").eq("user_id", u_id).eq("fecha", str(fecha_filtro)).execute()
        df_p = pd.DataFrame(res_p.data or [])
        if not df_p.empty:
            df_p.columns = [c.lower() for c in df_p.columns]
    except Exception:
        df_p = pd.DataFrame()

    if not df_p.empty:
        cols_p = ["id", "agencia", "sistema", "moneda", "monto", "estado", "fecha", "created_at", "user_id"]
        cols_p = [c for c in cols_p if c in df_p.columns]
        st.dataframe(df_p[cols_p], use_container_width=True, hide_index=True)
    else:
        st.info("ℹ️ No hay pagos en este día.")

    if not cerrado:
        with st.container(border=True):
            st.subheader("📝 Registrar Nuevo Pago")
            with st.form("form_p", clear_on_submit=True):
                c1, c2, c3 = st.columns([1, 1, 2])
                fecha_pg = c1.date_input("Fecha", value=fecha_filtro)
                moneda_pg = c2.selectbox("Moneda", ["COP", "USD", "BS"], index=0)
                monto_pg = c3.number_input("Monto", min_value=0.0, format="%.2f")
                tipo_pg = st.selectbox("Tipo Pago", ["Pago Móvil", "Transferencia", "Zelle", "Efectivo"])
                if st.form_submit_button("💾 GUARDAR", use_container_width=True):
                    if monto_pg <= 0:
                        st.error("Ingrese un monto válido.")
                    else:
                        supabase.table("cda_pagos_diarios").insert({
                            "fecha": str(fecha_pg), "agencia": ag_nombre,
                            "tipo_pago": tipo_pg, "monto": round(float(monto_pg), 2),
                            "moneda": moneda_pg, "user_id": u_id
                        }).execute()
                        st.success("✅ Pago guardado!"); time.sleep(1); st.rerun()


def modulo_reporte_rango(agencia_data):
    st.header("📊 Reporte por Rango de Fechas")
    st.markdown(f"**Terminal:** {agencia_data['nombre_agencia']}")
    u_id = agencia_data['user_id']

    hoy = datetime.now().date()
    c1, c2 = st.columns(2)
    d = c1.date_input("📅 Desde", value=hoy)
    h = c2.date_input("📅 Hasta", value=hoy)

    if d > h:
        st.error("La fecha 'Desde' no puede ser mayor que 'Hasta'.")
        return

    try:
        df_v = pd.DataFrame(supabase.table("cda_reportes_diarios")
            .select("*").eq("nombre_agency", agencia_data['nombre_agencia'])
            .gte("fecha", str(d)).lte("fecha", str(h)).execute().data or [])
        df_g = pd.DataFrame(supabase.table("cda_gastos_diarios")
            .select("*").eq("user_id", u_id)
            .gte("fecha", str(d)).lte("fecha", str(h)).execute().data or [])
        df_p = pd.DataFrame(supabase.table("cda_pagos_diarios")
            .select("*").eq("user_id", u_id)
            .gte("fecha", str(d)).lte("fecha", str(h)).execute().data or [])
        df_t = pd.DataFrame(supabase.table("cda_premios_tickets")
            .select("*").eq("agencia", agencia_data['nombre_agencia'])
            .gte("fecha", str(d)).lte("fecha", str(h)).execute().data or [])
        if not df_v.empty: df_v.columns = [c.lower() for c in df_v.columns]
        if not df_g.empty: df_g.columns = [c.lower() for c in df_g.columns]
        if not df_p.empty: df_p.columns = [c.lower() for c in df_p.columns]
        if not df_t.empty: df_t.columns = [c.lower() for c in df_t.columns]
        if not df_v.empty and 'fecha' in df_v.columns: df_v['fecha'] = pd.to_datetime(df_v['fecha']).dt.date
        if not df_g.empty and 'fecha' in df_g.columns: df_g['fecha'] = pd.to_datetime(df_g['fecha']).dt.date
        if not df_p.empty and 'fecha' in df_p.columns: df_p['fecha'] = pd.to_datetime(df_p['fecha']).dt.date
        if not df_t.empty and 'fecha' in df_t.columns: df_t['fecha'] = pd.to_datetime(df_t['fecha']).dt.date
    except Exception as e:
        st.error(f"Error: {e}"); return

    st.subheader("📈 Resumen General")
    tv = float(df_v['monto_venta'].sum()) if not df_v.empty else 0
    tc = float(df_v['comision'].sum()) if not df_v.empty else 0
    tp = float(df_v['monto_premios'].sum()) if not df_v.empty else 0
    tg = float(df_g['monto'].sum()) if not df_g.empty else 0
    tpg = float(df_p['monto'].sum()) if not df_p.empty else 0
    saldo_calculado = tv - tc - tp - tg - tpg

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Ventas", f"${tv:,.2f}")
    c2.metric("Comisión", f"${tc:,.2f}")
    c3.metric("Premios", f"${tp:,.2f}")
    c4.metric("Gastos", f"${tg:,.2f}")
    c5.metric("Pagos", f"${tpg:,.2f}")
    c6.metric("Saldo", f"${saldo_calculado:,.2f}")
    st.divider()

    st.subheader("📋 Detalle por Día")
    if not df_v.empty:
        cols = ["fecha", "sistema", "monto_venta", "comision", "monto_premios"]
        cols = [c for c in cols if c in df_v.columns]
        st.dataframe(df_v[cols].sort_values(["fecha", "sistema"]), use_container_width=True, hide_index=True)
    else:
        st.info("Sin ventas registradas.")

    if not df_g.empty:
        with st.expander("💸 Gastos"):
            cols_g = ["id", "agencia", "moneda", "monto", "concepto", "fecha", "created_at", "user_id"]
            cols_g = [c for c in cols_g if c in df_g.columns]
            st.dataframe(df_g[cols_g], use_container_width=True, hide_index=True)
    if not df_p.empty:
        with st.expander("💰 Pagos"):
            cols_p = ["id", "agencia", "sistema", "moneda", "monto", "estado", "fecha", "created_at", "user_id"]
            cols_p = [c for c in cols_p if c in df_p.columns]
            st.dataframe(df_p[cols_p], use_container_width=True, hide_index=True)
    if not df_t.empty:
        with st.expander("🎟️ Tickets Premios"):
            cols_t = ["id", "agencia", "sistema", "numero_ticket", "monto", "estado", "fecha", "created_at", "user_id"]
            cols_t = [c for c in cols_t if c in df_t.columns]
            st.dataframe(df_t[cols_t], use_container_width=True, hide_index=True)

    # WhatsApp
    def txt_rango():
        nom = agencia_data['nombre_agencia']
        lines = []
        lines.append("=" * 36)
        lines.append(f"  Reporte: {d} al {h}")
        lines.append(f"  {nom}")
        lines.append("=" * 36)
        if not df_v.empty:
            for fe in sorted(df_v["fecha"].unique()):
                lines.append(f"  --- {fe} ---")
                df_dia = df_v[df_v["fecha"] == fe]
                for _, r in df_dia.iterrows():
                    lines.append(f"  {r['sistema']}")
                    lines.append(f"    Venta:    {float(r['monto_venta']):>12,.2f}")
                    lines.append(f"    Comision: {float(r['comision']):>12,.2f}")
                    lines.append(f"    Premios:  {float(r['monto_premios']):>12,.2f}")
                lines.append("-" * 36)
        lines.append("=" * 36)
        lines.append(f"  TOTAL VENTAS:    ${tv:>10,.2f}")
        lines.append(f"  TOTAL COMISION:  ${tc:>10,.2f}")
        lines.append(f"  TOTAL PREMIOS:   ${tp:>10,.2f}")
        lines.append(f"  TOTAL GASTOS:    ${tg:>10,.2f}")
        lines.append(f"  TOTAL PAGOS:     ${tpg:>10,.2f}")
        lines.append("-" * 36)
        lines.append(f"  SALDO:           ${saldo_calculado:>10,.2f}")
        lines.append("=" * 36)
        lines.append("  Generado: " + datetime.now().strftime("%Y-%m-%d %H:%M"))
        lines.append("=" * 36)
        return "\n".join(lines)

    txt_r = txt_rango()
    st.text_area("📄 Vista previa", txt_r, height=200)
    wa_url = f"https://wa.me/?text={urllib.parse.quote(txt_r)}"
    st.link_button("📲 Compartir por WhatsApp", url=wa_url, use_container_width=True)


def modulo_cierre_diario(agencia_data):
    st.header("🔒 Cierre Diario")
    u_id = agencia_data['user_id']
    nom = agencia_data['nombre_agencia']
    es_supervisor = st.session_state.get("cajero_actual", {}).get("rol", "") == "supervisor"

    if "fecha_cierre" not in st.session_state:
        st.session_state["fecha_cierre"] = obtener_ultimo_dia_cerrado(nom) or datetime.now().date()

    fecha_sel = st.date_input(
        "📅 Seleccione el día a cerrar:",
        value=st.session_state["fecha_cierre"],
        key="fecha_cierre_input"
    )

    cerrado = dia_esta_cerrado(nom, fecha_sel)

    # Cargar datos del día
    try:
        df_v = pd.DataFrame(supabase.table("cda_reportes_diarios")
            .select("*").eq("nombre_agency", nom).eq("fecha", str(fecha_sel)).execute().data or [])
        df_g = pd.DataFrame(supabase.table("cda_gastos_diarios")
            .select("*").eq("user_id", u_id).eq("fecha", str(fecha_sel)).execute().data or [])
        df_pg = pd.DataFrame(supabase.table("cda_pagos_diarios")
            .select("*").eq("user_id", u_id).eq("fecha", str(fecha_sel)).execute().data or [])
        if not df_v.empty: df_v.columns = [c.lower() for c in df_v.columns]
        if not df_g.empty: df_g.columns = [c.lower() for c in df_g.columns]
        if not df_pg.empty: df_pg.columns = [c.lower() for c in df_pg.columns]
    except Exception as e:
        st.error(f"Error: {e}"); return

    t_venta = float(df_v['monto_venta'].sum()) if not df_v.empty else 0
    t_comis = float(df_v['comision'].sum()) if not df_v.empty else 0
    t_premios = float(df_v['monto_premios'].sum()) if not df_v.empty else 0
    t_gastos = float(df_g['monto'].sum()) if not df_g.empty else 0
    t_pagos = float(df_pg['monto'].sum()) if not df_pg.empty else 0
    t_saldo = t_venta - t_comis - t_premios - t_gastos - t_pagos

    st.subheader(f"📊 Resumen del {fecha_sel}")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Ventas", f"${t_venta:,.2f}")
    c2.metric("Comisión", f"${t_comis:,.2f}")
    c3.metric("Premios", f"${t_premios:,.2f}")
    c4.metric("Gastos", f"${t_gastos:,.2f}")
    c5.metric("Pagos", f"${t_pagos:,.2f}")
    c6.metric("Saldo", f"${t_saldo:,.2f}")

    if not df_v.empty:
        with st.expander("📋 Detalle por Sistema", expanded=True):
            cols = ["sistema", "monto_venta", "comision", "monto_premios"]
            cols = [c for c in cols if c in df_v.columns]
            st.dataframe(df_v[cols], use_container_width=True, hide_index=True)

    st.divider()

    if cerrado:
        st.success(f"✅ El día {fecha_sel} está **CERRADO**.")
        if es_supervisor:
            if st.button("🔓 Reabrir Día (solo supervisor)", type="secondary", use_container_width=True):
                if reabrir_dia(nom, fecha_sel):
                    st.success("✅ Día reabierto."); time.sleep(1); st.rerun()
    else:
        if df_v.empty and df_g.empty and df_pg.empty:
            st.info("ℹ️ No hay datos registrados para este día. Carga al menos una venta antes de cerrar.")
        elif not es_supervisor:
            st.info("ℹ️ Solo un supervisor puede cerrar el día. Solicita al supervisor que realice el cierre.")
        else:
            if st.button("🔒 Cerrar Día", type="primary", use_container_width=True):
                cajero_id = st.session_state.get("cajero_actual", {}).get("id")
                if cerrar_dia(nom, fecha_sel, cajero_id):
                    st.success("✅ Día cerrado exitosamente."); time.sleep(1); st.rerun()


def modulo_premios_tickets(agencia_data):
    st.header("🎟️ Tickets Premiados")
    rol_actual = st.session_state.get("cajero_actual", {}).get("rol", "cajero")
    es_supervisor = (rol_actual == "supervisor")
    u_id_real = str(st.session_state.get("cajero_actual", {}).get("id", agencia_data['user_id']))
    u_id_dueno = agencia_data['user_id']
    ag_nombre = agencia_data['nombre_agencia']

    if "fecha_ticket_filtro" not in st.session_state:
        st.session_state["fecha_ticket_filtro"] = obtener_ultimo_dia_cerrado(ag_nombre) or datetime.now().date()

    fecha_filtro = st.date_input(
        "📅 Ver tickets del día:",
        value=st.session_state["fecha_ticket_filtro"],
        key="fecha_ticket_filtro_input"
    )

    try:
        res = supabase.table("cda_premios_tickets")\
            .select("*")\
            .eq("agencia", ag_nombre)\
            .eq("fecha", str(fecha_filtro))\
            .order("fecha", desc=False)\
            .execute()
        df_t = pd.DataFrame(res.data or [])
        if not df_t.empty:
            df_t.columns = [c.lower() for c in df_t.columns]
    except Exception as e:
        st.error(f"Error al cargar tickets: {e}")
        df_t = pd.DataFrame()

    if st.checkbox("🔍 Ver TODOS los tickets (incluso de otro cajero)", value=False):
        try:
            res_all = supabase.table("cda_premios_tickets")\
                .select("*")\
                .eq("fecha", str(fecha_filtro))\
                .execute()
            df_all = pd.DataFrame(res_all.data or [])
            if not df_all.empty:
                df_all.columns = [c.lower() for c in df_all.columns]
                st.dataframe(df_all, use_container_width=True, hide_index=True)
            else:
                st.info("ℹ️ No hay tickets para este día.")
        except Exception as e:
            st.error(f"Error: {e}")

    cerrado = dia_esta_cerrado(ag_nombre, fecha_filtro)
    if cerrado and not es_supervisor:
        st.warning(f"🔒 El día {fecha_filtro} está cerrado. No se pueden registrar nuevos tickets.")
    elif cerrado and es_supervisor:
        st.info(f"🔒 El día {fecha_filtro} está cerrado. Solo un supervisor puede registrar tickets.")

    permitir_nuevo = not cerrado or es_supervisor
    if permitir_nuevo:
        st.markdown("### 📝 Registrar Nuevo Premio")
        with st.container(border=True):
            c1, c2 = st.columns(2)
            fecha_p = c1.date_input("Fecha del Sorteo", value=fecha_filtro)
            sistema_p = c2.selectbox("Sistema", ["BETM3", "GATOWEB", "KENO", "OTRO"], index=0)

            usar_lote = st.checkbox("📦 Ingresar últimos 3 dígitos del ticket")

            if usar_lote:
                cantidad = st.number_input("Cantidad de tickets", min_value=1, max_value=100, value=1, step=1)

                if cantidad <= 20:
                    st.markdown("##### Ingrese los datos de cada ticket")
                    digs = []
                    montos_lote = []
                    for i in range(int(cantidad)):
                        cols = st.columns([1, 2, 1, 3])
                        d = cols[0].text_input(f"#{i+1}", key=f"dig_{i}", max_chars=3, placeholder="000")
                        m = cols[2].number_input(f"Monto", min_value=0.0, format="%.2f", key=f"mon_lote_{i}")
                        digs.append(d)
                        montos_lote.append(m)

                    if st.button("💾 REGISTRAR LOTE", use_container_width=True, key="btn_lote"):
                        errores = []
                        ok_count = 0
                        for i in range(int(cantidad)):
                            serial = digs[i].strip().upper()
                            monto_i = montos_lote[i]
                            if not serial or monto_i <= 0:
                                errores.append(f"Ticket #{i+1}: completo los datos")
                                continue
                            num_ticket = serial
                            monto_red = round(float(monto_i), 2)
                            try:
                                supabase.table("cda_premios_tickets").insert({
                                    "agencia": ag_nombre, "sistema": sistema_p,
                                    "numero_ticket": num_ticket, "fecha": str(fecha_p),
                                    "monto": monto_red, "estado": "RECLAMADO",
                                    "user_id": u_id_real,
                                }).execute()
                                # actualizar cda_reportes_diarios
                                d_res = supabase.table("cda_reportes_diarios").select("*")\
                                    .eq("nombre_agency", ag_nombre).eq("fecha", str(fecha_p)).eq("sistema", sistema_p).execute()
                                if d_res.data:
                                    d_row = d_res.data[0]
                                    nuevo_mp = float(d_row.get("monto_premios", 0)) + monto_red
                                    nuevo_neto = float(d_row.get("monto_venta", 0)) - float(d_row.get("comision", 0)) - nuevo_mp
                                    supabase.table("cda_reportes_diarios").update({
                                        "monto_premios": nuevo_mp, "neto": nuevo_neto,
                                        "cajero_id": u_id_real,
                                    }).eq("id", d_row["id"]).execute()
                                else:
                                    supabase.table("cda_reportes_diarios").insert({
                                        "nombre_agency": ag_nombre, "fecha": str(fecha_p),
                                        "sistema": sistema_p, "monto_venta": 0, "comision": 0,
                                        "monto_premios": monto_red, "neto": -monto_red,
                                        "moneda": "COP", "user_id": agencia_data['user_id'],
                                        "cajero_id": u_id_real,
                                    }).execute()
                                ok_count += 1
                            except Exception as e:
                                errores.append(f"Ticket #{i+1}: {e}")
                        if ok_count:
                            st.success(f"✅ {ok_count} ticket(s) registrado(s).")
                        for e in errores:
                            st.warning(e)
                        if ok_count:
                            time.sleep(1); st.rerun()
                else:
                    st.info("📋 Modo *todos* — se registrarán N tickets con identificador TODOS")
                    monto_total = st.number_input("Monto Total COP", min_value=0.0, format="%.2f", key="monto_total_lote")

                    if st.button("💾 REGISTRAR LOTE", use_container_width=True, key="btn_lote_todos"):
                        if monto_total <= 0:
                            st.error("Ingrese un monto válido.")
                        else:
                            monto_por_ticket = round(float(monto_total) / int(cantidad), 2)
                            total_acumulado = 0
                            ok_count = 0
                            errores = []
                            for i in range(int(cantidad)):
                                monto_i = monto_por_ticket if i < int(cantidad) - 1 else round(float(monto_total) - total_acumulado, 2)
                                total_acumulado += monto_i
                                try:
                                    supabase.table("cda_premios_tickets").insert({
                                        "agencia": ag_nombre, "sistema": sistema_p,
                                        "numero_ticket": "TODOS", "fecha": str(fecha_p),
                                        "monto": monto_i, "estado": "RECLAMADO",
                                        "user_id": u_id_real,
                                    }).execute()
                                    ok_count += 1
                                except Exception as e:
                                    errores.append(f"Ticket #{i+1}: {e}")
                            # actualizar cda_reportes_diarios con el total
                            try:
                                d_res = supabase.table("cda_reportes_diarios").select("*")\
                                    .eq("nombre_agency", ag_nombre).eq("fecha", str(fecha_p)).eq("sistema", sistema_p).execute()
                                monto_total_red = round(float(monto_total), 2)
                                if d_res.data:
                                    d_row = d_res.data[0]
                                    nuevo_mp = float(d_row.get("monto_premios", 0)) + monto_total_red
                                    nuevo_neto = float(d_row.get("monto_venta", 0)) - float(d_row.get("comision", 0)) - nuevo_mp
                                    supabase.table("cda_reportes_diarios").update({
                                        "monto_premios": nuevo_mp, "neto": nuevo_neto,
                                        "cajero_id": u_id_real,
                                    }).eq("id", d_row["id"]).execute()
                                else:
                                    supabase.table("cda_reportes_diarios").insert({
                                        "nombre_agency": ag_nombre, "fecha": str(fecha_p),
                                        "sistema": sistema_p, "monto_venta": 0, "comision": 0,
                                        "monto_premios": monto_total_red, "neto": -monto_total_red,
                                        "moneda": "COP", "user_id": agencia_data['user_id'],
                                        "cajero_id": u_id_real,
                                    }).execute()
                            except Exception:
                                pass
                            if ok_count:
                                st.success(f"✅ {ok_count} ticket(s) TODOS registrados por ${monto_total:,.2f}.")
                            for e in errores:
                                st.warning(e)
                            if ok_count:
                                time.sleep(1); st.rerun()
            else:
                ticket = st.text_input("Número de Ticket").strip()
                monto_p = st.number_input("Monto del Premio COP", min_value=0.0, format="%.2f")
                if st.button("💾 REGISTRAR TICKET PAGADO", use_container_width=True):
                    if not ticket or monto_p <= 0:
                        st.error("El número de ticket y el monto son obligatorios.")
                    else:
                        nuevo = {
                            "agencia": ag_nombre, "sistema": sistema_p,
                            "numero_ticket": ticket.upper(), "fecha": str(fecha_p),
                            "monto": round(float(monto_p), 2), "estado": "RECLAMADO",
                            "user_id": u_id_real,
                        }
                        try:
                            res_ins = supabase.table("cda_premios_tickets").insert(nuevo).execute()
                            if res_ins.data:
                                try:
                                    d_res = supabase.table("cda_reportes_diarios").select("*")\
                                        .eq("nombre_agency", ag_nombre).eq("fecha", str(fecha_p)).eq("sistema", sistema_p).execute()
                                    monto_redondeado = round(float(monto_p), 2)
                                    if d_res.data:
                                        d_row = d_res.data[0]
                                        nuevo_mp = float(d_row.get("monto_premios", 0)) + monto_redondeado
                                        nuevo_neto = float(d_row.get("monto_venta", 0)) - float(d_row.get("comision", 0)) - nuevo_mp
                                        supabase.table("cda_reportes_diarios").update({
                                            "monto_premios": nuevo_mp, "neto": nuevo_neto,
                                            "cajero_id": u_id_real,
                                        }).eq("id", d_row["id"]).execute()
                                    else:
                                        supabase.table("cda_reportes_diarios").insert({
                                            "nombre_agency": ag_nombre, "fecha": str(fecha_p),
                                            "sistema": sistema_p, "monto_venta": 0, "comision": 0,
                                            "monto_premios": monto_redondeado, "neto": -monto_redondeado,
                                            "moneda": "COP", "user_id": agencia_data['user_id'],
                                            "cajero_id": u_id_real,
                                        }).execute()
                                except Exception:
                                    pass
                                st.success("✅ Premio registrado."); time.sleep(1); st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar: {e}")

    st.markdown(f"### 📋 Listado del {fecha_filtro}")

    if df_t.empty:
        st.info("ℹ️ No hay tickets registrados para esta fecha.")
        return

    df_view = df_t[df_t["estado"] == "RECLAMADO"][["fecha", "sistema", "numero_ticket", "monto", "id"]].copy()
    df_view["monto"] = pd.to_numeric(df_view["monto"], errors='coerce').fillna(0)

    total_reclamado = df_view["monto"].sum()
    st.metric("Premios Pagados (Salida caja)", f"${total_reclamado:,.2f}")
    st.divider()

    for idx, fila in df_view.iterrows():
        with st.container(border=True):
            c1, c2 = st.columns([2, 6])
            c1.markdown(f"**🎟️ {fila['numero_ticket']}**")
            c2.markdown(f"{fila['fecha']} | {fila['sistema']} | ${fila['monto']:,.2f}")


def modulo_reporte_diario(agencia_data):
    st.header("📆 Reporte Detallado por Día")
    st.markdown(f"**Terminal:** {agencia_data['nombre_agencia']}")
    u_id = agencia_data['user_id']

    if "fecha_reporte_dia" not in st.session_state:
        st.session_state["fecha_reporte_dia"] = obtener_ultimo_dia_cerrado(agencia_data['nombre_agencia']) or datetime.now().date()

    fecha_sel = st.date_input(
        "📅 Seleccione el día:",
        value=st.session_state["fecha_reporte_dia"],
        key="fecha_reporte_dia_input"
    )

    try:
        df_v = pd.DataFrame(supabase.table("cda_reportes_diarios")
            .select("*").eq("nombre_agency", agencia_data['nombre_agencia']).eq("fecha", str(fecha_sel)).execute().data or [])
        df_g = pd.DataFrame(supabase.table("cda_gastos_diarios")
            .select("*").eq("user_id", u_id).eq("fecha", str(fecha_sel)).execute().data or [])
        df_p = pd.DataFrame(supabase.table("cda_pagos_diarios")
            .select("*").eq("user_id", u_id).eq("fecha", str(fecha_sel)).execute().data or [])
        df_t = pd.DataFrame(supabase.table("cda_premios_tickets")
            .select("*").eq("agencia", agencia_data['nombre_agencia']).eq("fecha", str(fecha_sel)).execute().data or [])
        if not df_v.empty: df_v.columns = [c.lower() for c in df_v.columns]
        if not df_g.empty: df_g.columns = [c.lower() for c in df_g.columns]
        if not df_p.empty: df_p.columns = [c.lower() for c in df_p.columns]
        if not df_t.empty: df_t.columns = [c.lower() for c in df_t.columns]
    except Exception as e:
        st.error(f"Error: {e}"); return

    t_venta = float(df_v['monto_venta'].sum()) if not df_v.empty else 0.0
    t_comis = float(df_v['comision'].sum()) if not df_v.empty else 0.0
    t_premios = float(df_v['monto_premios'].sum()) if not df_v.empty else 0.0
    t_gastos = float(df_g['monto'].sum()) if not df_g.empty else 0.0
    t_pagos = float(df_p['monto'].sum()) if not df_p.empty else 0.0
    t_saldo = t_venta - t_comis - t_premios - t_gastos - t_pagos

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Ventas", f"${t_venta:,.2f}")
    m2.metric("Comision", f"${t_comis:,.2f}")
    m3.metric("Premios", f"${t_premios:,.2f}")
    m4.metric("Gastos", f"${t_gastos:,.2f}")
    m5.metric("Pagos", f"${t_pagos:,.2f}")
    m6.metric("Saldo", f"${t_saldo:,.2f}")

    with st.expander("📋 Detalle por Sistema", expanded=True):
        if not df_v.empty:
            cols = ["sistema", "monto_venta", "comision", "monto_premios"]
            cols = [c for c in cols if c in df_v.columns]
            st.dataframe(df_v[cols], use_container_width=True, hide_index=True)
        else:
            st.info("Sin ventas este dia.")

    # 80mm print
    line = "=" * 36
    def txt_80mm():
        nom = agencia_data['nombre_agencia']
        lines = []
        lines.append(line)
        lines.append(f"  Reporte Diario: {fecha_sel}")
        lines.append(f"  {nom}")
        lines.append(line)
        if not df_v.empty:
            for _, r in df_v.iterrows():
                lines.append(f"  {r['sistema']}")
                lines.append(f"    Venta:     {float(r['monto_venta']):>12,.2f}")
                lines.append(f"    Comision:  {float(r['comision']):>12,.2f}")
                lines.append(f"    Premios:   {float(r['monto_premios']):>12,.2f}")
                lines.append("-" * 36)
        lines.append(line)
        lines.append(f"  TOTAL VENTAS:    ${t_venta:>10,.2f}")
        lines.append(f"  TOTAL COMISION:  ${t_comis:>10,.2f}")
        lines.append(f"  TOTAL PREMIOS:   ${t_premios:>10,.2f}")
        lines.append(f"  TOTAL GASTOS:    ${t_gastos:>10,.2f}")
        lines.append(f"  TOTAL PAGOS:     ${t_pagos:>10,.2f}")
        lines.append("-" * 36)
        lines.append(f"  SALDO:           ${t_saldo:>10,.2f}")
        lines.append(line)

        if not df_t.empty:
            lines.append("  TICKETS PREMIADOS")
            lines.append("-" * 36)
            df_t_pago = df_t[df_t["estado"] == "RECLAMADO"] if "estado" in df_t.columns else df_t
            for _, r in df_t_pago.iterrows():
                t_sis = r.get('sistema', '')
                t_mon = r.get('moneda', '')
                t_est = r.get('estado', '')
                t_est = "PAGO" if t_est == "RECLAMADO" else t_est
                lines.append(f"  {r.get('numero_ticket','?'):>8s}  {float(r['monto']):>10,.2f}  {t_mon} {t_sis}  {t_est}")
            lines.append(line)

        if not df_g.empty:
            lines.append("  GASTOS")
            lines.append("-" * 36)
            for _, r in df_g.iterrows():
                lines.append(f"  {r.get('concepto','?')}  ${float(r['monto']):>10,.2f}")
            lines.append(line)

        if not df_p.empty:
            lines.append("  PAGOS")
            lines.append("-" * 36)
            for _, r in df_p.iterrows():
                lines.append(f"  {r.get('tipo_pago','?')}  ${float(r['monto']):>10,.2f}")
            lines.append(line)

        lines.append("  Generado: " + datetime.now().strftime("%Y-%m-%d %H:%M"))
        lines.append(line)
        return "\n".join(lines)

    txt_reporte = txt_80mm()

    st.markdown("### 🖨️ Impresion 80mm")
    st.text(txt_reporte)

    st.download_button(
        "🖨️ Descargar e Imprimir (80mm)",
        data=txt_reporte,
        file_name=f"reporte_{fecha_sel}.txt",
        mime="text/plain",
        use_container_width=True
    )

    wa_url = f"https://wa.me/?text={urllib.parse.quote(txt_reporte)}"
    st.link_button("📲 Compartir por WhatsApp", url=wa_url, use_container_width=True)


# 🔐 autenticación 🔐

if "tema_oscuro" not in st.session_state:
    st.session_state.tema_oscuro = True

if "taquilla_autenticada" not in st.session_state:
    st.session_state.taquilla_autenticada = False

if not st.session_state.taquilla_autenticada:
    if st.session_state.tema_oscuro:
        login_css = """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');

        /* Apply font to everything on login page */
        :root, .stApp {
            --primary-color: #6366f1 !important;
            --background-color: #080c14 !important;
            --secondary-background-color: #0f172a !important;
            --text-color: #f8fafc !important;
            font-family: 'Plus Jakarta Sans', sans-serif !important;
        }

        [data-testid="stHeader"], [data-testid="stSidebar"], [data-testid="collapsedControl"] {
            display: none !important;
        }

        footer, [data-testid="stDecoration"] {
            display: none !important;
        }

        .stApp, [data-testid="stAppViewContainer"], section.main, .main {
            background-color: #080c14 !important;
            background-image: 
                radial-gradient(at 0% 0%, rgba(99, 102, 241, 0.18) 0px, transparent 50%),
                radial-gradient(at 100% 0%, rgba(139, 92, 246, 0.15) 0px, transparent 50%),
                radial-gradient(at 50% 100%, rgba(244, 63, 94, 0.05) 0px, transparent 50%) !important;
            background-size: cover !important;
            min-height: 100vh !important;
        }

        [data-testid="stBlockContainer"],
        [data-testid="stAppViewBlockContainer"],
        [data-testid="stVerticalBlock"],
        [data-testid="stVerticalBlockBorderWrapper"],
        .block-container {
            max-width: 585px !important;
            padding-top: 4rem !important;
            padding-bottom: 4rem !important;
            margin: 0 auto !important;
            background: transparent !important;
            background-color: transparent !important;
            border: none !important;
            box-shadow: none !important;
            outline: none !important;
        }

        form[data-testid="stForm"],
        div[data-testid="stForm"] {
            background-color: rgba(15, 23, 42, 0.75) !important;
            backdrop-filter: blur(24px) !important;
            -webkit-backdrop-filter: blur(24px) !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            border-radius: 24px !important;
            padding: 2.5rem 2rem !important;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.6) !important;
            width: 100% !important;
            max-width: 533px !important;
            margin: 0 auto !important;
        }

        [data-testid="stForm"] > div {
            gap: 1.25rem !important;
        }

        /* Style Labels */
        [data-testid="stWidgetLabel"] p {
            color: #94a3b8 !important;
            font-weight: 600 !important;
            font-size: 0.75rem !important;
            letter-spacing: 0.05em !important;
            text-transform: uppercase !important;
            margin-bottom: 0.35rem !important;
        }

        /* Style Inputs (Selectbox, Text, Number, Date) */
        div[data-baseweb="input"],
        div[data-baseweb="input"] > div,
        div[data-baseweb="input"] input {
            background-color: #0f172a !important;
            color: #f8fafc !important;
            border-color: rgba(255, 255, 255, 0.08) !important;
            border-radius: 10px !important;
        }

        div[data-baseweb="input"]:focus-within {
            border-color: #6366f1 !important;
        }

        input {
            color: #f8fafc !important;
            font-size: 0.95rem !important;
        }

        /* Style Submit Button */
        [data-testid="stFormSubmitButton"] button {
            width: 100% !important;
            background: linear-gradient(90deg, #6366f1 0%, #8b5cf6 100%) !important;
            color: #ffffff !important;
            border: none !important;
            padding: 0.75rem 1.5rem !important;
            border-radius: 12px !important;
            font-size: 0.95rem !important;
            font-weight: 600 !important;
            transition: all 0.25s ease-in-out !important;
            box-shadow: 0 4px 12px rgba(99, 102, 241, 0.35) !important;
            margin-top: 0.5rem !important;
        }

        [data-testid="stFormSubmitButton"] button:hover {
            background: linear-gradient(90deg, #4f46e5 0%, #7c3aed 100%) !important;
            box-shadow: 0 6px 18px rgba(99, 102, 241, 0.5) !important;
            transform: translateY(-1px) !important;
        }

        [data-testid="stFormSubmitButton"] button:active {
            transform: translateY(1px) !important;
        }

        [data-testid="stNotification"] {
            background-color: rgba(239, 68, 68, 0.1) !important;
            border: 1px solid rgba(239, 68, 68, 0.2) !important;
            border-radius: 12px !important;
            margin-top: 1rem !important;
        }

        [data-testid="stNotification"] p {
            color: #fca5a5 !important;
            font-size: 0.9rem !important;
        }
        </style>
        """
    else:
        login_css = """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');

        /* Apply font to everything on login page */
        :root, .stApp {
            --primary-color: #4f46e5 !important;
            --background-color: #f8fafc !important;
            --secondary-background-color: #ffffff !important;
            --text-color: #0f172a !important;
            font-family: 'Plus Jakarta Sans', sans-serif !important;
        }

        [data-testid="stHeader"], [data-testid="stSidebar"], [data-testid="collapsedControl"] {
            display: none !important;
        }

        footer, [data-testid="stDecoration"] {
            display: none !important;
        }

        .stApp, [data-testid="stAppViewContainer"], section.main, .main {
            background-color: #f8fafc !important;
            background-image: 
                radial-gradient(at 0% 0%, rgba(99, 102, 241, 0.04) 0px, transparent 50%),
                radial-gradient(at 100% 0%, rgba(139, 92, 246, 0.03) 0px, transparent 50%),
                radial-gradient(at 50% 100%, rgba(244, 63, 94, 0.01) 0px, transparent 50%) !important;
            background-size: cover !important;
            min-height: 100vh !important;
        }

        [data-testid="stBlockContainer"],
        [data-testid="stAppViewBlockContainer"],
        [data-testid="stVerticalBlock"],
        [data-testid="stVerticalBlockBorderWrapper"],
        .block-container {
            max-width: 585px !important;
            padding-top: 4rem !important;
            padding-bottom: 4rem !important;
            margin: 0 auto !important;
            background: transparent !important;
            background-color: transparent !important;
            border: none !important;
            box-shadow: none !important;
            outline: none !important;
        }

        form[data-testid="stForm"],
        div[data-testid="stForm"] {
            background-color: #ffffff !important;
            border: 1px solid rgba(15, 23, 42, 0.08) !important;
            border-radius: 24px !important;
            padding: 2.5rem 2rem !important;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.05), 0 10px 10px -5px rgba(0, 0, 0, 0.04) !important;
            width: 100% !important;
            max-width: 533px !important;
            margin: 0 auto !important;
        }

        [data-testid="stForm"] > div {
            gap: 1.25rem !important;
        }

        /* Style Labels */
        [data-testid="stWidgetLabel"] p {
            color: #475569 !important;
            font-weight: 600 !important;
            font-size: 0.75rem !important;
            letter-spacing: 0.05em !important;
            text-transform: uppercase !important;
            margin-bottom: 0.35rem !important;
        }

        /* Style Inputs */
        div[data-baseweb="input"],
        div[data-baseweb="input"] > div,
        div[data-baseweb="input"] input {
            background-color: #ffffff !important;
            color: #0f172a !important;
            border-color: rgba(15, 23, 42, 0.12) !important;
            border-radius: 10px !important;
        }

        div[data-baseweb="input"]:focus-within {
            border-color: #4f46e5 !important;
        }

        input {
            color: #0f172a !important;
            font-size: 0.95rem !important;
        }

        /* Style Submit Button */
        [data-testid="stFormSubmitButton"] button {
            width: 100% !important;
            background: linear-gradient(90deg, #4f46e5 0%, #7c3aed 100%) !important;
            color: #ffffff !important;
            border: none !important;
            padding: 0.75rem 1.5rem !important;
            border-radius: 12px !important;
            font-size: 0.95rem !important;
            font-weight: 600 !important;
            transition: all 0.25s ease-in-out !important;
            box-shadow: 0 4px 12px rgba(79, 70, 229, 0.2) !important;
            margin-top: 0.5rem !important;
        }

        [data-testid="stFormSubmitButton"] button:hover {
            background: linear-gradient(90deg, #4338ca 0%, #6d28d9 100%) !important;
            box-shadow: 0 6px 18px rgba(79, 70, 229, 0.3) !important;
            transform: translateY(-1px) !important;
        }

        [data-testid="stFormSubmitButton"] button:active {
            transform: translateY(1px) !important;
        }

        [data-testid="stNotification"] {
            background-color: #fef2f2 !important;
            border: 1px solid #fee2e2 !important;
            border-radius: 12px !important;
            margin-top: 1rem !important;
        }

        [data-testid="stNotification"] p {
            color: #991b1b !important;
            font-size: 0.9rem !important;
        }
        </style>
        """
    st.markdown(login_css, unsafe_allow_html=True)
    
    color_titulo = "#ffffff" if st.session_state.tema_oscuro else "#0f172a"
    color_subtitulo = "#64748b" if st.session_state.tema_oscuro else "#475569"

    with st.form("login_form", clear_on_submit=False):
        st.markdown(
            f"""
            <div style="text-align: center; margin-bottom: 1.5rem;">
                <div style="font-size: 3rem; margin-bottom: 0.5rem;">🔐</div>
                <h2 style="color: {color_titulo}; font-size: 1.75rem; font-weight: 700; margin: 0; letter-spacing: -0.025em; line-height: 1.25;">
                    Taquilla POS
                </h2>
                <p style="color: {color_subtitulo}; font-size: 0.875rem; margin-top: 0.25rem; font-weight: 400;">
                    Acceso
                </p>
            </div>
            """, 
            unsafe_allow_html=True
        )
        user_input = st.text_input("Usuario", placeholder="Ingresa tu usuario").strip()
        key_input = st.text_input("Clave", type="password", placeholder="Ingresa tu clave").strip()
        submitted = st.form_submit_button("Iniciar Sesión")



    if submitted:
        res_user = supabase.table("taquilla_usuarios").select("*").ilike("usuario", user_input).eq("clave", key_input).execute()
        res_data = res_user.data or []
        if res_data:
            user_data = res_data[0]
            res_agencia = supabase.table("agencias").select("*").execute()
            df_todas = pd.DataFrame(res_agencia.data or [])
            raw_id = str(user_data["agencia_id"]).strip()
            match = df_todas[df_todas["id"].astype(str) == raw_id]
            if not match.empty:
                st.session_state.taquilla_autenticada = True
                st.session_state.agencia_actual = match.iloc[0].to_dict()
                st.session_state.cajero_actual = {"id": user_data["id"], "usuario": user_data["usuario"], "rol": user_data["rol"], "nombre": user_data.get("nombre_cajero", user_data["usuario"])}
                st.rerun()
            else:
                st.error("Agencia no encontrada.")
        else:
            st.error("Credenciales incorrectas.")
else:
    _check_cerrado_col()
    ag = st.session_state.agencia_actual
    cajero = st.session_state.cajero_actual
    ultimo_cierre = obtener_ultimo_dia_cerrado(ag['nombre_agencia'])

    if st.session_state.tema_oscuro:
        dashboard_css = """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');

        /* Global theme variables overrides */
        :root, .stApp {
            --primary-color: #6366f1 !important;
            --background-color: #0b0f19 !important;
            --secondary-background-color: #0f172a !important;
            --text-color: #f8fafc !important;
            font-family: 'Plus Jakarta Sans', sans-serif !important;
        }

        [data-testid="stHeader"] {
            background-color: rgba(11, 15, 25, 0.8) !important;
            backdrop-filter: blur(12px) !important;
            -webkit-backdrop-filter: blur(12px) !important;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05) !important;
        }

        footer, [data-testid="stDecoration"] {
            display: none !important;
        }

        /* Page background colors - dark mode */
        .stApp, [data-testid="stAppViewContainer"], section.main, .main {
            background-color: #0b0f19 !important;
            background-image: 
                radial-gradient(at 0% 0%, rgba(99, 102, 241, 0.06) 0px, transparent 40%),
                radial-gradient(at 100% 100%, rgba(139, 92, 246, 0.04) 0px, transparent 40%) !important;
            background-size: cover !important;
            min-height: 100vh !important;
        }

        [data-testid="stSidebar"], [data-testid="stSidebar"] > div {
            background-color: #0f172a !important;
            border-right: 1px solid rgba(255, 255, 255, 0.06) !important;
        }

        [data-testid="stBlockContainer"],
        [data-testid="stAppViewBlockContainer"],
        .block-container {
            max-width: 100% !important;
            padding: 3rem 4rem !important;
        }

        /* Style Metric Cards */
        [data-testid="stMetric"] {
            background-color: rgba(15, 23, 42, 0.45) !important;
            backdrop-filter: blur(10px) !important;
            -webkit-backdrop-filter: blur(10px) !important;
            border: 1px solid rgba(255, 255, 255, 0.06) !important;
            border-radius: 16px !important;
            padding: 1.25rem 1.5rem !important;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1) !important;
            transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out !important;
        }
        [data-testid="stMetric"]:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.2) !important;
            border-color: rgba(99, 102, 241, 0.25) !important;
        }
        [data-testid="stMetricLabel"] p {
            color: #94a3b8 !important;
            font-size: 0.8rem !important;
            font-weight: 600 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.05em !important;
        }
        [data-testid="stMetricValue"] {
            color: #ffffff !important;
            font-size: 1.75rem !important;
            font-weight: 700 !important;
        }

        /* Style Cards / Containers */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background-color: rgba(15, 23, 42, 0.35) !important;
            backdrop-filter: blur(12px) !important;
            -webkit-backdrop-filter: blur(12px) !important;
            border: 1px solid rgba(255, 255, 255, 0.06) !important;
            border-radius: 16px !important;
            padding: 1.75rem !important;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1) !important;
        }

        /* Style Labels */
        [data-testid="stWidgetLabel"] p {
            color: #94a3b8 !important;
            font-weight: 600 !important;
            font-size: 0.75rem !important;
            letter-spacing: 0.05em !important;
            text-transform: uppercase !important;
            margin-bottom: 0.35rem !important;
        }

        /* Style Inputs (Selectbox, Text, Number, Date, Textarea) - Dark */
        div[data-baseweb="input"],
        div[data-baseweb="textarea"],
        div[data-baseweb="select"] {
            background-color: #0f172a !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            border-radius: 10px !important;
        }
        div[data-baseweb="input"] *,
        div[data-baseweb="textarea"] *,
        div[data-baseweb="select"] * {
            color: #f8fafc !important;
            background-color: transparent !important;
        }
        input, select, textarea {
            color: #f8fafc !important;
            background-color: #0f172a !important;
        }
        div[data-baseweb="input"]:focus-within,
        div[data-baseweb="textarea"]:focus-within,
        div[data-baseweb="select"]:focus-within {
            border-color: #6366f1 !important;
            box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.25) !important;
        }

        /* Input SVGs / Icons */
        div[data-baseweb="select"] svg,
        div[data-baseweb="input"] svg {
            fill: #cbd5e1 !important;
            color: #cbd5e1 !important;
        }

        /* Input buttons (number input step controls) */
        div[data-baseweb="input"] button {
            background-color: #1e293b !important;
            color: #cbd5e1 !important;
            border: none !important;
        }
        div[data-baseweb="input"] button:hover {
            background-color: #334155 !important;
            color: #ffffff !important;
        }

        /* Disabled state */
        div[data-baseweb="input"] input:disabled,
        div[data-baseweb="input"] input[disabled],
        input:disabled, textarea:disabled {
            background-color: #1e293b !important;
            color: #64748b !important;
            cursor: not-allowed !important;
        }
        
        /* Popovers, calendars, and listbox menus */
        div[data-baseweb="popover"],
        div[role="dialog"],
        ul[role="listbox"],
        li[role="option"] {
            background-color: #0f172a !important;
            border-color: rgba(255, 255, 255, 0.1) !important;
            color: #f8fafc !important;
        }

        /* Dropdown options text color */
        li[role="option"] {
            color: #f8fafc !important;
            background-color: #0f172a !important;
            transition: background-color 0.15s ease !important;
        }
        li[role="option"]:hover,
        li[role="option"][aria-selected="true"] {
            background-color: #1e293b !important;
            color: #ffffff !important;
        }

        /* Target Date Picker calendar container styling */
        div[data-baseweb="calendar"] {
            background-color: #0f172a !important;
            border: 1px solid rgba(255, 255, 255, 0.1) !important;
        }
        div[data-baseweb="calendar"] * {
            background-color: transparent !important;
            color: #cbd5e1 !important;
        }
        div[data-baseweb="calendar"] select {
            background-color: #1e293b !important;
            color: #f8fafc !important;
            border: 1px solid rgba(255, 255, 255, 0.1) !important;
            border-radius: 6px !important;
        }
        div[data-baseweb="calendar"] [role="gridcell"] {
            transition: all 0.15s ease !important;
        }
        div[data-baseweb="calendar"] [role="gridcell"]:hover,
        div[data-baseweb="calendar"] [role="gridcell"]:hover * {
            background-color: #1e293b !important;
            color: #ffffff !important;
        }
        div[data-baseweb="calendar"] [aria-selected="true"],
        div[data-baseweb="calendar"] [aria-selected="true"] * {
            background-color: #6366f1 !important;
            color: #ffffff !important;
            border-radius: 50% !important;
        }
        div[data-baseweb="calendar"] [role="gridcell"][aria-disabled="true"],
        div[data-baseweb="calendar"] [role="gridcell"][aria-disabled="true"] * {
            color: #475569 !important;
        }
        div[data-baseweb="calendar"] button {
            color: #cbd5e1 !important;
        }
        div[data-baseweb="calendar"] button:hover {
            background-color: #1e293b !important;
            color: #ffffff !important;
        }

        /* Style Buttons */
        [data-testid="stBaseButton-secondary"] button,
        button[data-testid="stBaseButton-secondary"] {
            background-color: rgba(30, 41, 59, 0.5) !important;
            color: #f1f5f9 !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            border-radius: 10px !important;
            font-weight: 500 !important;
            padding: 0.5rem 1rem !important;
            transition: all 0.2s ease-in-out !important;
            width: 100% !important;
        }
        [data-testid="stBaseButton-secondary"] button:hover,
        button[data-testid="stBaseButton-secondary"]:hover {
            background-color: rgba(51, 65, 85, 0.7) !important;
            border-color: rgba(255, 255, 255, 0.15) !important;
            color: #ffffff !important;
        }

        [data-testid="stBaseButton-primary"] button,
        button[data-testid="stBaseButton-primary"] {
            background: linear-gradient(90deg, #6366f1 0%, #8b5cf6 100%) !important;
            color: #ffffff !important;
            border: none !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
            padding: 0.5rem 1rem !important;
            box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3) !important;
            transition: all 0.2s ease-in-out !important;
            width: 100% !important;
        }
        [data-testid="stBaseButton-primary"] button:hover,
        button[data-testid="stBaseButton-primary"]:hover {
            background: linear-gradient(90deg, #4f46e5 0%, #7c3aed 100%) !important;
            box-shadow: 0 6px 16px rgba(99, 102, 241, 0.4) !important;
            transform: translateY(-1px) !important;
        }

        /* Sidebar Cerrar Sesión Button */
        [data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"]:nth-last-child(1) {
            background-color: rgba(239, 68, 68, 0.06) !important;
            color: #fca5a5 !important;
            border: 1px solid rgba(239, 68, 68, 0.15) !important;
            border-radius: 10px !important;
        }
        [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:nth-last-child(1) button:hover {
            background-color: rgba(239, 68, 68, 0.15) !important;
            border-color: rgba(239, 68, 68, 0.35) !important;
            color: #ffffff !important;
        }

        /* Expanders styling */
        [data-testid="stExpander"] {
            background-color: rgba(15, 23, 42, 0.25) !important;
            border: 1px solid rgba(255, 255, 255, 0.06) !important;
            border-radius: 12px !important;
        }
        [data-testid="stExpander"] summary {
            color: #f1f5f9 !important;
            font-weight: 600 !important;
        }

        /* Preformatted Text blocks (st.text) */
        pre, code, [data-testid="stText"] {
            background-color: #0f172a !important;
            color: #cbd5e1 !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            border-radius: 8px !important;
            padding: 1rem !important;
        }

        /* HTML Tables styling */
        table {
            background-color: #0f172a !important;
            color: #cbd5e1 !important;
            border-collapse: collapse !important;
            width: 100% !important;
        }
        th {
            background-color: #1e293b !important;
            color: #ffffff !important;
            font-weight: 600 !important;
            border-bottom: 2px solid rgba(255, 255, 255, 0.08) !important;
            padding: 0.75rem 1rem !important;
        }
        td {
            background-color: #0f172a !important;
            color: #cbd5e1 !important;
            border-bottom: 1px solid rgba(255, 255, 255, 0.06) !important;
            padding: 0.75rem 1rem !important;
        }
        tr:hover td {
            background-color: #1e293b !important;
        }

        /* General text readability improvements */
        h1, h2, h3, h4, h5, h6 {
            color: #ffffff !important;
            font-weight: 700 !important;
        }
        p, span, label, li, ul, ol {
            color: #cbd5e1 !important;
        }
        strong, b {
            color: #ffffff !important;
            font-weight: 700 !important;
        }
        </style>
        """
    else:
        # Light mode dashboard CSS
        dashboard_css = """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');

        /* Global theme variables overrides */
        :root, .stApp {
            --primary-color: #4f46e5 !important;
            --background-color: #f8fafc !important;
            --secondary-background-color: #ffffff !important;
            --text-color: #0f172a !important;
            font-family: 'Plus Jakarta Sans', sans-serif !important;
        }

        [data-testid="stHeader"] {
            background-color: rgba(248, 250, 252, 0.8) !important;
            backdrop-filter: blur(12px) !important;
            -webkit-backdrop-filter: blur(12px) !important;
            border-bottom: 1px solid rgba(15, 23, 42, 0.05) !important;
        }

        footer, [data-testid="stDecoration"] {
            display: none !important;
        }

        /* Page background colors - light mode */
        .stApp, [data-testid="stAppViewContainer"], section.main, .main {
            background-color: #f8fafc !important;
            background-image: 
                radial-gradient(at 0% 0%, rgba(99, 102, 241, 0.04) 0px, transparent 40%),
                radial-gradient(at 100% 100%, rgba(139, 92, 246, 0.03) 0px, transparent 40%) !important;
            background-size: cover !important;
            min-height: 100vh !important;
        }

        [data-testid="stSidebar"], [data-testid="stSidebar"] > div {
            background-color: #ffffff !important;
            border-right: 1px solid rgba(15, 23, 42, 0.06) !important;
        }

        [data-testid="stBlockContainer"],
        [data-testid="stAppViewBlockContainer"],
        .block-container {
            max-width: 100% !important;
            padding: 3rem 4rem !important;
        }

        /* Style Metric Cards */
        [data-testid="stMetric"] {
            background-color: #ffffff !important;
            border: 1px solid rgba(15, 23, 42, 0.08) !important;
            border-radius: 16px !important;
            padding: 1.25rem 1.5rem !important;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05) !important;
            transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out !important;
        }
        [data-testid="stMetric"]:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 8px 12px -3px rgba(0, 0, 0, 0.1) !important;
            border-color: rgba(79, 70, 229, 0.3) !important;
        }
        [data-testid="stMetricLabel"] p {
            color: #475569 !important;
            font-size: 0.8rem !important;
            font-weight: 600 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.05em !important;
        }
        [data-testid="stMetricValue"] {
            color: #0f172a !important;
            font-size: 1.75rem !important;
            font-weight: 700 !important;
        }

        /* Style Cards / Containers */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background-color: #ffffff !important;
            border: 1px solid rgba(15, 23, 42, 0.08) !important;
            border-radius: 16px !important;
            padding: 1.75rem !important;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05) !important;
        }

        /* Style Labels */
        [data-testid="stWidgetLabel"] p {
            color: #475569 !important;
            font-weight: 600 !important;
            font-size: 0.75rem !important;
            letter-spacing: 0.05em !important;
            text-transform: uppercase !important;
            margin-bottom: 0.35rem !important;
        }

        /* Style Inputs (Selectbox, Text, Number, Date, Textarea) - Light */
        div[data-baseweb="input"],
        div[data-baseweb="textarea"],
        div[data-baseweb="select"] {
            background-color: #ffffff !important;
            border: 1px solid rgba(15, 23, 42, 0.12) !important;
            border-radius: 10px !important;
        }
        div[data-baseweb="input"] *,
        div[data-baseweb="textarea"] *,
        div[data-baseweb="select"] * {
            color: #0f172a !important;
            background-color: transparent !important;
        }
        input, select, textarea {
            color: #0f172a !important;
            background-color: #ffffff !important;
        }
        div[data-baseweb="input"]:focus-within,
        div[data-baseweb="textarea"]:focus-within,
        div[data-baseweb="select"]:focus-within {
            border-color: #4f46e5 !important;
            box-shadow: 0 0 0 2px rgba(79, 70, 229, 0.2) !important;
        }

        /* Input SVGs / Icons */
        div[data-baseweb="select"] svg,
        div[data-baseweb="input"] svg {
            fill: #475569 !important;
            color: #475569 !important;
        }

        /* Input buttons (number input step controls) */
        div[data-baseweb="input"] button {
            background-color: #f1f5f9 !important;
            color: #334155 !important;
            border: none !important;
        }
        div[data-baseweb="input"] button:hover {
            background-color: #e2e8f0 !important;
            color: #0f172a !important;
        }

        /* Disabled state */
        div[data-baseweb="input"] input:disabled,
        div[data-baseweb="input"] input[disabled],
        input:disabled, textarea:disabled {
            background-color: #f1f5f9 !important;
            color: #94a3b8 !important;
            cursor: not-allowed !important;
        }
        
        /* Popovers, calendars, and listbox menus */
        div[data-baseweb="popover"],
        div[role="dialog"],
        ul[role="listbox"],
        li[role="option"] {
            background-color: #ffffff !important;
            border-color: rgba(15, 23, 42, 0.1) !important;
            color: #0f172a !important;
        }

        /* Dropdown options text color */
        li[role="option"] {
            color: #0f172a !important;
            background-color: #ffffff !important;
            transition: background-color 0.15s ease !important;
        }
        li[role="option"]:hover,
        li[role="option"][aria-selected="true"] {
            background-color: #f1f5f9 !important;
            color: #0f172a !important;
        }

        /* Target Date Picker calendar container styling */
        div[data-baseweb="calendar"] {
            background-color: #ffffff !important;
            border: 1px solid rgba(15, 23, 42, 0.1) !important;
        }
        div[data-baseweb="calendar"] * {
            background-color: transparent !important;
            color: #334155 !important;
        }
        div[data-baseweb="calendar"] select {
            background-color: #f1f5f9 !important;
            color: #0f172a !important;
            border: 1px solid rgba(15, 23, 42, 0.1) !important;
            border-radius: 6px !important;
        }
        div[data-baseweb="calendar"] [role="gridcell"] {
            transition: all 0.15s ease !important;
        }
        div[data-baseweb="calendar"] [role="gridcell"]:hover,
        div[data-baseweb="calendar"] [role="gridcell"]:hover * {
            background-color: #f1f5f9 !important;
            color: #0f172a !important;
        }
        div[data-baseweb="calendar"] [aria-selected="true"],
        div[data-baseweb="calendar"] [aria-selected="true"] * {
            background-color: #4f46e5 !important;
            color: #ffffff !important;
            border-radius: 50% !important;
        }
        div[data-baseweb="calendar"] [role="gridcell"][aria-disabled="true"],
        div[data-baseweb="calendar"] [role="gridcell"][aria-disabled="true"] * {
            color: #94a3b8 !important;
        }
        div[data-baseweb="calendar"] button {
            color: #475569 !important;
        }
        div[data-baseweb="calendar"] button:hover {
            background-color: #f1f5f9 !important;
            color: #0f172a !important;
        }

        /* Style Buttons */
        [data-testid="stBaseButton-secondary"] button,
        button[data-testid="stBaseButton-secondary"] {
            background-color: #f1f5f9 !important;
            color: #334155 !important;
            border: 1px solid rgba(15, 23, 42, 0.08) !important;
            border-radius: 10px !important;
            font-weight: 500 !important;
            padding: 0.5rem 1rem !important;
            transition: all 0.2s ease-in-out !important;
            width: 100% !important;
        }
        [data-testid="stBaseButton-secondary"] button:hover,
        button[data-testid="stBaseButton-secondary"]:hover {
            background-color: #e2e8f0 !important;
            color: #0f172a !important;
        }

        [data-testid="stBaseButton-primary"] button,
        button[data-testid="stBaseButton-primary"] {
            background: linear-gradient(90deg, #4f46e5 0%, #7c3aed 100%) !important;
            color: #ffffff !important;
            border: none !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
            padding: 0.5rem 1rem !important;
            box-shadow: 0 4px 12px rgba(79, 70, 229, 0.2) !important;
            transition: all 0.2s ease-in-out !important;
            width: 100% !important;
        }
        [data-testid="stBaseButton-primary"] button:hover,
        button[data-testid="stBaseButton-primary"]:hover {
            background: linear-gradient(90deg, #4338ca 0%, #6d28d9 100%) !important;
            box-shadow: 0 6px 16px rgba(79, 70, 229, 0.3) !important;
            transform: translateY(-1px) !important;
        }

        /* Sidebar Cerrar Sesión Button */
        [data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"]:nth-last-child(1) {
            background-color: rgba(239, 68, 68, 0.04) !important;
            color: #ef4444 !important;
            border: 1px solid rgba(239, 68, 68, 0.15) !important;
            border-radius: 10px !important;
        }
        [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:nth-last-child(1) button:hover {
            background-color: rgba(239, 68, 68, 0.12) !important;
            border-color: rgba(239, 68, 68, 0.3) !important;
            color: #ef4444 !important;
        }

        /* Expanders styling */
        [data-testid="stExpander"] {
            background-color: #ffffff !important;
            border: 1px solid rgba(15, 23, 42, 0.08) !important;
            border-radius: 12px !important;
        }
        [data-testid="stExpander"] summary {
            color: #0f172a !important;
            font-weight: 600 !important;
        }

        /* Preformatted Text blocks (st.text) */
        pre, code, [data-testid="stText"] {
            background-color: #f1f5f9 !important;
            color: #0f172a !important;
            border: 1px solid rgba(15, 23, 42, 0.08) !important;
            border-radius: 8px !important;
            padding: 1rem !important;
        }

        /* HTML Tables styling */
        table {
            background-color: #ffffff !important;
            color: #0f172a !important;
            border-collapse: collapse !important;
            width: 100% !important;
        }
        th {
            background-color: #f1f5f9 !important;
            color: #0f172a !important;
            font-weight: 600 !important;
            border-bottom: 2px solid rgba(15, 23, 42, 0.08) !important;
            padding: 0.75rem 1rem !important;
        }
        td {
            background-color: #ffffff !important;
            color: #334155 !important;
            border-bottom: 1px solid rgba(15, 23, 42, 0.06) !important;
            padding: 0.75rem 1rem !important;
        }
        tr:hover td {
            background-color: #f8fafc !important;
        }

        /* Ensure alert box texts are readable */
        [data-testid="stNotification"] * {
            color: inherit !important;
        }

        /* General text readability improvements */
        h1, h2, h3, h4, h5, h6 {
            color: #0f172a !important;
            font-weight: 700 !important;
            margin: 0 !important;
        }
        p, span, label, li, ul, ol {
            color: #334155 !important;
        }
        strong, b {
            color: #0f172a !important;
            font-weight: 700 !important;
        }
        </style>
        """
    st.markdown(dashboard_css, unsafe_allow_html=True)

    col_h1, col_h2 = st.columns([5, 1])
    with col_h1:
        st.markdown(
            f"""<h2 style='margin: 0; font-weight: 700; font-size: 1.75rem; color: {"#ffffff" if st.session_state.tema_oscuro else "#0f172a"};'>⚡ Panel de Control</h2>""", 
            unsafe_allow_html=True
        )
    with col_h2:
        tema_sel = st.toggle("🌙 Oscuro", value=st.session_state.tema_oscuro, key="toggle_tema_top")
        if tema_sel != st.session_state.tema_oscuro:
            st.session_state.tema_oscuro = tema_sel
            st.rerun()

    if st.session_state.tema_oscuro:
        card_bg = "rgba(30, 41, 59, 0.45)"
        card_border = "rgba(255, 255, 255, 0.06)"
        text_val_color = "#f8fafc"
        badge_bg = "rgba(99, 102, 241, 0.15)"
        badge_border = "rgba(99, 102, 241, 0.25)"
        badge_text = "#a5b4fc"
    else:
        card_bg = "#f1f5f9"
        card_border = "rgba(15, 23, 42, 0.08)"
        text_val_color = "#0f172a"
        badge_bg = "rgba(79, 70, 229, 0.1)"
        badge_border = "rgba(79, 70, 229, 0.2)"
        badge_text = "#4f46e5"

    opciones = ["Carga de Ventas", "Tickets Premiados", "Gestión de Gastos", "Gestión de Pagos", "Reporte Diario", "Reporte por Rango", "Cierre Diario"]

    opcion = st.selectbox("📍 Seleccione operación:", opciones, key="opcion_operacion_main")

    with st.sidebar:
        sidebar_info = f"""<div style="background-color: {card_bg}; border: 1px solid {card_border}; padding: 1.25rem; border-radius: 16px; margin-bottom: 1.5rem;">
<div style="font-size: 0.75rem; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.25rem;">Terminal</div>
<div style="font-size: 1.1rem; font-weight: 700; color: {text_val_color}; margin-bottom: 0.75rem;">🏢 {ag['nombre_agencia'].upper()}</div>
<div style="font-size: 0.75rem; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.25rem;">Usuario</div>
<div style="font-size: 0.95rem; font-weight: 600; color: {text_val_color}; margin-bottom: 0.75rem;">👤 {(cajero.get('nombre') or cajero.get('usuario') or 'USUARIO').upper()}</div>
<div style="font-size: 0.75rem; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.25rem;">Rol</div>
<div style="display: inline-block; background-color: {badge_bg}; border: 1px solid {badge_border}; color: {badge_text}; font-size: 0.75rem; font-weight: 700; padding: 0.2rem 0.5rem; border-radius: 6px; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.75rem;">{cajero['rol'].upper()}</div>
<div style="font-size: 0.75rem; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.25rem;">Último Cierre</div>
<div style="font-size: 0.9rem; font-weight: 500; color: { '#34d399' if ultimo_cierre else '#fb7185' }; font-family: inherit;">📅 {ultimo_cierre if ultimo_cierre else 'Sin cierres registrados'}</div>
</div>"""
        st.markdown(sidebar_info, unsafe_allow_html=True)
        st.divider()
        if st.button("🚪 Cerrar Sesión", use_container_width=True, key="btn_logout_sidebar"):
            st.session_state.taquilla_autenticada = False; st.rerun()

    if opcion == "Carga de Ventas": modulo_registro_taquilla(ag)
    elif opcion == "Gestión de Gastos": modulo_gastos(ag)
    elif opcion == "Gestión de Pagos": modulo_pagos(ag)
    elif opcion == "Reporte por Rango": modulo_reporte_rango(ag)
    elif opcion == "Tickets Premiados": modulo_premios_tickets(ag)
    elif opcion == "Cierre Diario": modulo_cierre_diario(ag)
    elif opcion == "Reporte Diario": modulo_reporte_diario(ag)
