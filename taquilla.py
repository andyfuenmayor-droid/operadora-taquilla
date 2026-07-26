import streamlit as st
import pandas as pd
import time
import urllib.parse
from utils import supabase
from datetime import datetime, timedelta, timezone

def obtener_hora_local():
    """Retorna la fecha y hora actual ajustada a la zona horaria local (UTC-4)."""
    return datetime.now(timezone(timedelta(hours=-4)))

user_agent = st.context.headers.get("User-Agent", "").lower()
if "ipad" in user_agent or ("android" in user_agent and "mobile" not in user_agent):
    st.session_state["dispositivo"] = "Tablet"
elif any(word in user_agent for word in ["iphone", "android", "blackberry", "opera mini"]):
    st.session_state["dispositivo"] = "Teléfono"
else:
    st.session_state["dispositivo"] = "Escritorio"

def obtener_nombre_banco(alias, c_asoc=""):
    alias_upper = str(alias).upper().strip()
    c_asoc_upper = str(c_asoc).upper().strip() if c_asoc else ""
    
    # 1. Si la cuenta asociada tiene formato BANCO | TITULAR, extraemos la primera parte
    if c_asoc_upper and "|" in c_asoc_upper and "SIN CUENTA" not in c_asoc_upper:
        return c_asoc.split("|")[0].strip().upper()
        
    # 2. Si no, buscamos un banco común en el alias o cuenta asociada
    bancos_comunes = ["BANCOLOMBIA", "BANESCO", "BANCAMIGA", "CITI BANK", "MERCANTIL", "PROVINCIAL", "VENEZUELA", "BOD", "BNC", "ZELLE", "BINANCE", "PAYPAL"]
    for b in bancos_comunes:
        if b in alias_upper:
            return b
        if b in c_asoc_upper:
            return b
            
    # 3. Limpieza de palabras clave comunes
    cleaned = alias_upper
    for word in ["POS", "BIOPAGO", "DISPOSITIVO", "GLO", "PUNTO DE VENTA", "PUNTO"]:
        cleaned = cleaned.replace(word, "")
    cleaned = cleaned.strip()
    return cleaned if cleaned else alias

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
        var V = "2026.07.24-v3.2.0";
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
    /* Tarjeta Form Estándar */
    [data-testid="stForm"] {
        background-color: rgba(13, 27, 34, 0.75) !important;
        backdrop-filter: blur(24px) !important;
        -webkit-backdrop-filter: blur(24px) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 24px !important;
        padding: 2.5rem 2rem !important;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.6) !important;
        width: 100% !important;
        max-width: 100% !important;
        margin: 0 !important;
    }
    [data-testid="stForm"] form {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
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
        background-color: #0d1b22 !important;
        color: #f8fafc !important;
        border-color: rgba(255, 255, 255, 0.08) !important;
        border-radius: 10px !important;
    }
    div[data-baseweb="input"]:focus-within {
        border-color: #00c853 !important;
    }
    input {
        color: #f8fafc !important;
        font-size: 0.95rem !important;
    }
    [data-testid="stFormSubmitButton"] button {
        width: 100% !important;
        background: linear-gradient(90deg, #00c853 0%, #00e676 100%) !important;
        color: #ffffff !important;
        border: none !important;
        padding: 0.75rem 1.5rem !important;
        border-radius: 12px !important;
        font-size: 0.95rem !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 12px rgba(0, 200, 83, 0.35) !important;
        margin-top: 0.5rem !important;
    }
    [data-testid="collapsedControl"] {
        display: flex !important;
        visibility: visible !important;
        z-index: 999999 !important;
        position: fixed !important;
        top: 10px !important;
        left: 10px !important;
        background-color: #0d1b22 !important;
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
""", 
unsafe_allow_html=True)


if "tema_oscuro" not in st.session_state:
    st.session_state.tema_oscuro = True

def render_encabezado_principal(texto):
    is_dark = st.session_state.get("tema_oscuro", True)
    color = "#ffffff" if is_dark else "#0f172a"
    st.markdown(f"<h2 style='margin: 0 0 4px 0; font-size: 20px; font-weight: 700; color: {color};'>{texto}</h2>", unsafe_allow_html=True)

def render_subtitulo_terminal(nombre_agencia):
    is_dark = st.session_state.get("tema_oscuro", True)
    color = "#94a3b8" if is_dark else "#475569"
    st.markdown(f"<div style='font-size: 14px; font-weight: 600; color: {color}; margin-bottom: 12px;'>Terminal: <b>{nombre_agencia}</b></div>", unsafe_allow_html=True)

def render_titulo_seccion(texto):
    st.markdown(f"<div style='font-size: 14px; font-weight: 700; color: #38bdf8; margin: 12px 0 8px 0;'>{texto}</div>", unsafe_allow_html=True)

def render_tarjetas_metricas(t_venta, t_comis, t_premios, t_gastos, t_pagos, t_saldo):
    is_dark = st.session_state.get("tema_oscuro", True)
    bg_color = "rgba(30, 41, 59, 0.6)" if is_dark else "#f8fafc"
    border_color = "rgba(255, 255, 255, 0.08)" if is_dark else "#e2e8f0"
    title_color = "#94a3b8" if is_dark else "#64748b"
    val_color = "#f8fafc" if is_dark else "#0f172a"

    items = [
        ("Ventas", f"${t_venta:,.2f}"),
        ("Comision", f"${t_comis:,.2f}"),
        ("Premios", f"${t_premios:,.2f}"),
        ("Gastos", f"${t_gastos:,.2f}"),
        ("Pagos", f"${t_pagos:,.2f}"),
        ("Saldo", f"${t_saldo:,.2f}"),
    ]

    cols = st.columns(6)
    for idx, (title, val) in enumerate(items):
        if title == "Saldo":
            if t_saldo > 0:
                cur_val_color = "#34d399" if is_dark else "#16a34a"
            elif t_saldo < 0:
                cur_val_color = "#f87171" if is_dark else "#dc2626"
            else:
                cur_val_color = val_color
        else:
            cur_val_color = val_color

        card_html = f"""<div style="background: {bg_color}; border: 1px solid {border_color}; border-radius: 8px; padding: 6px 8px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
<div style="font-size: 9px; font-weight: 700; color: {title_color}; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{title}</div>
<div style="font-size: 12px; font-weight: 700; color: {cur_val_color}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{val}</div>
</div>"""
        cols[idx].markdown(card_html, unsafe_allow_html=True)


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

def dia_esta_cerrado(agencia_nombre, fecha, cajero_id=None):
    """Retorna True si el día ya fue cerrado para esta agencia (y cajero opcional)."""
    try:
        q = supabase.table("cda_reportes_diarios")\
            .select("cerrado")\
            .eq("nombre_agency", agencia_nombre)\
            .eq("fecha", str(fecha))\
            .eq("cerrado", True)
        if cajero_id:
            q = q.eq("cajero_id", str(cajero_id))
        res = q.limit(1).execute()
        return len(res.data or []) > 0
    except Exception:
        return False

def cerrar_dia(agencia_nombre, fecha, cajero_id=None):
    """Marca las filas del día como cerrado=True."""
    try:
        q = supabase.table("cda_reportes_diarios")\
            .update({"cerrado": True})\
            .eq("nombre_agency", agencia_nombre)\
            .eq("fecha", str(fecha))
        if cajero_id:
            q = q.eq("cajero_id", str(cajero_id))
        q.execute()
        return True
    except Exception as e:
        st.error(f"Error al cerrar el día: {e}")
        return False

def reabrir_dia(agencia_nombre, fecha, cajero_id=None):
    """Marca las filas del día como cerrado=False (supervisor)."""
    try:
        q = supabase.table("cda_reportes_diarios")\
            .update({"cerrado": False})\
            .eq("nombre_agency", agencia_nombre)\
            .eq("fecha", str(fecha))
        if cajero_id:
            q = q.eq("cajero_id", str(cajero_id))
        q.execute()
        try:
            q_s = supabase.table("saldo_taquilla")\
                .delete()\
                .eq("nombre_agency", agencia_nombre)\
                .eq("fecha", str(fecha))
            if cajero_id:
                q_s = q_s.eq("cajero_id", str(cajero_id))
            q_s.execute()
        except Exception:
            pass
        return True
    except Exception as e:
        st.error(f"Error al reabrir el día: {e}")
        return False

def obtener_ultimo_dia_cerrado(agencia_nombre, cajero_id=None):
    """Retorna la última fecha cerrada, o None si no hay ninguna."""
    try:
        q = supabase.table("cda_reportes_diarios")\
            .select("fecha")\
            .eq("nombre_agency", agencia_nombre)\
            .eq("cerrado", True)
        if cajero_id:
            q = q.eq("cajero_id", str(cajero_id))
        res = q.order("fecha", desc=True)\
            .limit(1)\
            .execute()
        if res.data:
            fecha = res.data[0]["fecha"]
            return pd.to_datetime(fecha).date()
    except Exception:
        pass
    return None

def _check_saldo_taquilla_table():
    """Verifica que la tabla `saldo_taquilla` exista en Supabase; de lo contrario, muestra una advertencia con el SQL para crearla."""
    if "check_saldo_ok" not in st.session_state:
        try:
            supabase.table("saldo_taquilla").select("id").limit(1).execute()
            st.session_state["check_saldo_ok"] = True
        except Exception:
            st.session_state["check_saldo_ok"] = False
            st.warning(
                "⚠️ La tabla `saldo_taquilla` NO existe en Supabase. "
                "Ejecuta este SQL en el Editor SQL de Supabase para crearla:\n\n"
                "```sql\n"
                "CREATE TABLE IF NOT EXISTS saldo_taquilla (\n"
                "    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,\n"
                "    nombre_agency TEXT NOT NULL,\n"
                "    fecha DATE NOT NULL,\n"
                "    saldo_restante NUMERIC(20,2) NOT NULL DEFAULT 0.00,\n"
                "    cajero_id BIGINT,\n"
                "    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,\n"
                "    UNIQUE(nombre_agency, fecha)\n"
                ");\n"
                "```"
            )
    return st.session_state["check_saldo_ok"]

def obtener_saldo_anterior(agencia_nombre, fecha_sel, cajero_id=None):
    """Retorna el saldo restante del último día cerrado anterior a fecha_sel."""
    try:
        q = supabase.table("saldo_taquilla")\
            .select("saldo_restante")\
            .eq("nombre_agency", agencia_nombre)\
            .lt("fecha", str(fecha_sel))
        if cajero_id is not None:
            q = q.eq("cajero_id", cajero_id)
        res = q.order("fecha", desc=True).limit(1).execute()
        if res.data:
            return float(res.data[0]["saldo_restante"])
    except Exception:
        pass
    return 0.0


# �?� módulos de la taquilla �?�
def modulo_registro_taquilla(agencia_data):
    render_encabezado_principal(f"🎰 Carga de Ventas: {agencia_data['nombre_agencia']}")
    cajero_info = st.session_state.get("cajero_actual", {})
    rol_usuario = cajero_info.get("rol", "cajero")
    cajero_id = cajero_info.get("id")
    es_supervisor = (rol_usuario == 'supervisor')
    sistemas_lista = [s.strip() for s in str(agencia_data.get("sistemas", "BETM3")).split(",")]

    if "fecha_carga_actual" not in st.session_state:
        st.session_state["fecha_carga_actual"] = datetime.now().date()

    col_f, _ = st.columns([2, 2])
    with col_f:
        fecha_seleccionada = st.date_input(
            "📅 Seleccione el día a cargar:",
            value=st.session_state["fecha_carga_actual"],
            key="fecha_carga_input",
            on_change=lambda: setattr(st.session_state, 'fecha_carga_actual', st.session_state["fecha_carga_input"])
        )
    fecha_carga_iso = str(fecha_seleccionada)

    cerrado = dia_esta_cerrado(agencia_data['nombre_agencia'], fecha_carga_iso, cajero_id=cajero_id if not es_supervisor else None)
    if cerrado:
        if es_supervisor:
            st.warning(f"🔒 El día {fecha_carga_iso} está **cerrado**. Solo un supervisor puede reabrirlo.")
        else:
            st.error(f"🔒 Tu jornada del día {fecha_carga_iso} ya fue cerrada. Contacta al supervisor para modificarla.")
            return

    try:
        query_v = supabase.table("cda_reportes_diarios")\
            .select("*")\
            .eq("nombre_agency", agencia_data['nombre_agencia'])\
            .eq("fecha", fecha_carga_iso)
        if not es_supervisor and cajero_id:
            query_v = query_v.eq("cajero_id", cajero_id)
        res_existentes = query_v.execute()
        df_existentes = pd.DataFrame(res_existentes.data or [])
        if not df_existentes.empty:
            df_existentes.columns = [c.lower() for c in df_existentes.columns]
    except Exception:
        df_existentes = pd.DataFrame()

    st.info("🎟️ Los premios se registran exclusivamente en el módulo **Tickets Premiados**.")

    for sist in sistemas_lista:
        with st.container(border=True):
            render_titulo_seccion(f"📍 Sistema: {sist}")
            existe_en_db = False
            v_val, c_val, p_val = 0.0, 0.0, 0.0
            if not df_existentes.empty:
                if not es_supervisor and cajero_id and "cajero_id" in df_existentes.columns:
                    match = df_existentes[(df_existentes["sistema"] == sist) & (df_existentes["cajero_id"].astype(str) == str(cajero_id))]
                else:
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
                        "cajero_id": cajero_id
                    }
                    if existe_en_db and not match.empty and "id" in match.iloc[0]:
                        row_id = match.iloc[0]["id"]
                        supabase.table("cda_reportes_diarios").update(data).eq("id", row_id).execute()
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
    render_encabezado_principal("💸 Gestión de Gastos")
    u_id = agencia_data['user_id']
    ag_nombre = agencia_data['nombre_agencia']
    cajero_info = st.session_state.get("cajero_actual", {})
    rol_usuario = cajero_info.get("rol", "cajero")
    cajero_id = cajero_info.get("id")
    es_supervisor = (rol_usuario == 'supervisor')

    if "fecha_gasto_filtro" not in st.session_state:
        st.session_state["fecha_gasto_filtro"] = datetime.now().date()

    col_f, _ = st.columns([2, 2])
    with col_f:
        fecha_filtro = st.date_input(
            "📅 Ver gastos del día:",
            value=st.session_state["fecha_gasto_filtro"],
            key="fecha_gasto_filtro_input"
        )

    cerrado = dia_esta_cerrado(ag_nombre, fecha_filtro, cajero_id=cajero_id if not es_supervisor else None)
    if cerrado:
        st.info(f"🔒 El día {fecha_filtro} está cerrado para tu usuario. No se pueden registrar nuevos gastos.")

    try:
        res_g = supabase.table("cda_gastos_diarios").select("*").eq("fecha", str(fecha_filtro)).execute()
        df_g = pd.DataFrame(res_g.data or [])
        if not df_g.empty:
            df_g.columns = [c.lower() for c in df_g.columns]
            if not es_supervisor and cajero_id:
                col_g = "cajero_id" if "cajero_id" in df_g.columns else ("user_id" if "user_id" in df_g.columns else None)
                if col_g and col_g in df_g.columns:
                    df_g = df_g[df_g[col_g].astype(str) == str(cajero_id)]
    except Exception:
        df_g = pd.DataFrame()

    if not df_g.empty:
        render_titulo_seccion("📋 Gastos del Día")
        cols_orden = ["id", "agencia", "moneda", "monto", "concepto", "fecha", "created_at", "user_id"]
        cols_existentes = [c for c in cols_orden if c in df_g.columns]
        st.dataframe(df_g[cols_existentes], use_container_width=True, hide_index=True)
    else:
        st.info("ℹ️ No hay gastos en este día.")

    if not cerrado:
        with st.form("form_g", clear_on_submit=True):
            render_titulo_seccion("📝 Registrar Nuevo Gasto")
            c1, c2, c3 = st.columns([2, 2, 3])
            fecha_g = c1.date_input("Fecha", value=fecha_filtro)
            moneda_g = c2.selectbox("Moneda", ["COP", "USD", "BS"], index=0)
            monto_g = c3.number_input("Monto", min_value=0.0, format="%.2f")
            concepto_g = st.text_input("Concepto:", placeholder="Ej. Pago de servicios, papelería, mantenimiento...")
            if st.form_submit_button("💾 GUARDAR GASTO", use_container_width=True):
                if not concepto_g.strip() or monto_g <= 0:
                    st.error("Complete el concepto y un monto mayor a cero.")
                else:
                    supabase.table("cda_gastos_diarios").insert({
                        "fecha": str(fecha_g), "agencia": ag_nombre,
                        "concepto": concepto_g.upper().strip(),
                        "monto": round(float(monto_g), 2),
                        "moneda": moneda_g, "user_id": u_id,
                        "cajero_id": cajero_id
                    }).execute()
                    st.success("✅ Gasto guardado exitosamente!"); time.sleep(1); st.rerun()


def modulo_pagos(agencia_data):
    render_encabezado_principal("💰 Recepción de Pagos")
    u_id = agencia_data['user_id']
    ag_nombre = agencia_data['nombre_agencia']
    cajero_info = st.session_state.get("cajero_actual", {})
    rol_usuario = cajero_info.get("rol", "cajero")
    cajero_id = cajero_info.get("id")
    es_supervisor = (rol_usuario == 'supervisor')

    if "fecha_pago_filtro" not in st.session_state:
        st.session_state["fecha_pago_filtro"] = datetime.now().date()

    col_f, _ = st.columns([2, 2])
    with col_f:
        fecha_filtro = st.date_input(
            "📅 Ver pagos del día:",
            value=st.session_state["fecha_pago_filtro"],
            key="fecha_pago_filtro_input"
        )

    cerrado = dia_esta_cerrado(ag_nombre, fecha_filtro, cajero_id=cajero_id if not es_supervisor else None)
    if cerrado:
        st.info(f"🔒 El día {fecha_filtro} está cerrado para tu usuario. No se pueden registrar nuevos pagos.")

    try:
        res_p = supabase.table("cda_pagos_diarios").select("*").eq("fecha", str(fecha_filtro)).execute()
        df_p = pd.DataFrame(res_p.data or [])
        if not df_p.empty:
            df_p.columns = [c.lower() for c in df_p.columns]
            if not es_supervisor and cajero_id:
                col_p = "cajero_id" if "cajero_id" in df_p.columns else ("user_id" if "user_id" in df_p.columns else None)
                if col_p and col_p in df_p.columns:
                    df_p = df_p[df_p[col_p].astype(str) == str(cajero_id)]
    except Exception:
        df_p = pd.DataFrame()

    if not df_p.empty:
        render_titulo_seccion("📋 Pagos del Día")
        cols_p = ["id", "agencia", "sistema", "moneda", "monto", "estado", "fecha", "created_at", "user_id"]
        cols_p = [c for c in cols_p if c in df_p.columns]
        st.dataframe(df_p[cols_p], use_container_width=True, hide_index=True)
    else:
        st.info("ℹ️ No hay pagos en este día.")

    if not cerrado:
        with st.form("form_p", clear_on_submit=True):
            render_titulo_seccion("📝 Registrar Nuevo Pago")
            c1, c2, c3, c4 = st.columns([2, 2, 3, 3])
            fecha_pg = c1.date_input("Fecha", value=fecha_filtro)
            moneda_pg = c2.selectbox("Moneda", ["COP", "USD", "BS"], index=0)
            monto_pg = c3.number_input("Monto", min_value=0.0, format="%.2f")
            tipo_pg = c4.selectbox("Tipo Pago", ["Efectivo"])
            if st.form_submit_button("💾 GUARDAR PAGO", use_container_width=True):
                if monto_pg <= 0:
                    st.error("Ingrese un monto válido mayor a cero.")
                else:
                    supabase.table("cda_pagos_diarios").insert({
                        "fecha": str(fecha_pg), "agencia": ag_nombre,
                        "tipo_pago": tipo_pg, "monto": round(float(monto_pg), 2),
                        "moneda": moneda_pg, "user_id": u_id,
                        "cajero_id": cajero_id
                    }).execute()
                    st.success("✅ Pago guardado exitosamente!"); time.sleep(1); st.rerun()


def modulo_gestion_bancaria(agencia_data):
    render_encabezado_principal("🏛️ Gestión Bancaria")
    render_subtitulo_terminal(agencia_data['nombre_agencia'])
    u_id = str(agencia_data['user_id']).strip()
    ag_nombre = str(agencia_data['nombre_agencia']).strip()

    tab1, tab2, tab3, tab4 = st.tabs([
        "🏦 Cuentas Bancarias", 
        "📟 Dispositivos de Pago (POS / Biopago)", 
        "💸 Registrar Pago", 
        "📊 Historial y Resumen"
    ])

    # ---------------------------------------------------------
    # 1. OBTENER CUENTAS ASIGNADAS Y DISPOSITIVOS DE PAGO DESDE SUPABASE
    # ---------------------------------------------------------
    cuentas_ids_asignadas = []
    try:
        res_ag_asig = supabase.table("agencias").select("cuentas_asignadas").eq("nombre_agencia", ag_nombre).execute()
        if res_ag_asig.data:
            c_asig_txt = str(res_ag_asig.data[0].get("cuentas_asignadas", ""))
            for item in c_asig_txt.split(","):
                item_str = item.strip()
                if item_str:
                    try:
                        c_id_parsed = int(item_str.split(" - ")[0])
                        cuentas_ids_asignadas.append(c_id_parsed)
                    except Exception:
                        pass
    except Exception:
        pass

    # A) CARGA DE CUENTAS BANCARIAS
    df_cuentas = pd.DataFrame()
    try:
        res_c = supabase.table("cuentas_bancarias").select("*").execute()
        df_cuentas_all = pd.DataFrame(res_c.data or [])
        if not df_cuentas_all.empty:
            df_cuentas_all.columns = [c.lower().strip() for c in df_cuentas_all.columns]
            
            # Excluir registros que sean dispositivos de pago en fallback
            if "tipo_cuenta" in df_cuentas_all.columns:
                df_c_only = df_cuentas_all[df_cuentas_all["tipo_cuenta"].astype(str).str.upper() != "DISPOSITIVO DE PAGO"].copy()
            else:
                df_c_only = df_cuentas_all.copy()

            cond_ag = pd.Series(False, index=df_c_only.index)
            if "agencia_asignada" in df_c_only.columns:
                ag_col = df_c_only["agencia_asignada"].astype(str).str.upper().str.strip()
                cond_ag = ag_col.isin([ag_nombre.upper(), "TODAS", "TODOS", "GENERAL", "DISPONIBLE"])
            elif "metodos_aceptados" in df_c_only.columns:
                met_col = df_c_only["metodos_aceptados"].astype(str).str.upper().str.strip()
                cond_ag = met_col.str.contains(ag_nombre.upper(), na=False)

            cond_id = df_c_only["id"].astype(int).isin(cuentas_ids_asignadas) if ("id" in df_c_only.columns and cuentas_ids_asignadas) else pd.Series(False, index=df_c_only.index)

            df_cuentas = df_c_only[cond_ag | cond_id].copy()

            if df_cuentas.empty and not cuentas_ids_asignadas:
                if "user_id" in df_c_only.columns:
                    df_cuentas = df_c_only[df_c_only["user_id"].astype(str).str.strip() == u_id].copy()
                else:
                    df_cuentas = df_c_only.copy()

            if not df_cuentas.empty:
                if "id" in df_cuentas.columns:
                    df_cuentas["id"] = pd.to_numeric(df_cuentas["id"], errors="coerce")
                    df_cuentas = df_cuentas.sort_values("id")
    except Exception as e:
        df_cuentas = pd.DataFrame()

    # Normalización de columnas para la tabla Cuentas Bancarias
    if not df_cuentas.empty:
        if "estatus" not in df_cuentas.columns:
            df_cuentas["estatus"] = df_cuentas.get("estado", "ACTIVA")
        if "saldo_inicial" not in df_cuentas.columns:
            df_cuentas["saldo_inicial"] = 0.0
        if "agencia_asignada" not in df_cuentas.columns:
            df_cuentas["agencia_asignada"] = ag_nombre
        if "tipo_cuenta" not in df_cuentas.columns:
            df_cuentas["tipo_cuenta"] = "CORRIENTE"
        if "numero_cuenta" not in df_cuentas.columns:
            df_cuentas["numero_cuenta"] = df_cuentas.get("identificador", df_cuentas.get("email", "N/A"))

    # B) CARGA DE DISPOSITIVOS DE PAGO (POS / BIOPAGO)
    df_dispositivos = pd.DataFrame()
    try:
        if not df_cuentas_all.empty:
            cond_tipo_disp = pd.Series(False, index=df_cuentas_all.index)
            if "tipo_cuenta" in df_cuentas_all.columns:
                cond_tipo_disp = cond_tipo_disp | (df_cuentas_all["tipo_cuenta"].astype(str).str.upper().str.strip() == "DISPOSITIVO DE PAGO")
            if "banco" in df_cuentas_all.columns:
                cond_tipo_disp = cond_tipo_disp | (df_cuentas_all["banco"].astype(str).str.upper().str.strip().str.startswith("DISPOSITIVO"))
            
            df_disp_cb = df_cuentas_all[cond_tipo_disp].copy()

            if not df_disp_cb.empty:
                cond_d_ag = pd.Series(False, index=df_disp_cb.index)
                if "agencia_asignada" in df_disp_cb.columns:
                    d_ag_col = df_disp_cb["agencia_asignada"].astype(str).str.upper().str.strip()
                    cond_d_ag = cond_d_ag | d_ag_col.isin([ag_nombre.upper(), "TODAS", "TODOS", "GENERAL", "DISPONIBLE"])
                
                if "metodos_aceptados" in df_disp_cb.columns:
                    met_col = df_disp_cb["metodos_aceptados"].astype(str).str.upper().str.strip()
                    cond_d_ag = cond_d_ag | met_col.str.contains(ag_nombre.upper(), na=False)

                if "id" in df_disp_cb.columns and cuentas_ids_asignadas:
                    cond_d_id = df_disp_cb["id"].astype(int).isin(cuentas_ids_asignadas)
                    cond_d_ag = cond_d_ag | cond_d_id

                cond_d_uid = pd.Series(False, index=df_disp_cb.index)
                if "user_id" in df_disp_cb.columns and not cuentas_ids_asignadas:
                    cond_d_uid = df_disp_cb["user_id"].astype(str).str.strip() == u_id

                df_dispositivos = df_disp_cb[cond_d_ag | cond_d_uid].copy()
    except Exception:
        df_dispositivos = pd.DataFrame()

    # Complementar con dispositivos_pago o puntos_venta si existen datos
    try:
        res_disp = supabase.table("dispositivos_pago").select("*").execute()
        df_disp_legacy = pd.DataFrame(res_disp.data or [])
        if not df_disp_legacy.empty:
            df_disp_legacy.columns = [c.lower().strip() for c in df_disp_legacy.columns]
            cond_d_ag_leg = pd.Series(False, index=df_disp_legacy.index)
            if "agencia_asignada" in df_disp_legacy.columns:
                d_ag_col = df_disp_legacy["agencia_asignada"].astype(str).str.upper().str.strip()
                cond_d_ag_leg = d_ag_col.isin([ag_nombre.upper(), "TODAS", "TODOS", "GENERAL", "DISPONIBLE"])
            elif "agencia" in df_disp_legacy.columns:
                d_ag_col = df_disp_legacy["agencia"].astype(str).str.upper().str.strip()
                cond_d_ag_leg = d_ag_col.isin([ag_nombre.upper(), "TODAS", "TODOS", "GENERAL", "DISPONIBLE"])

            cond_d_uid_leg = df_disp_legacy["user_id"].astype(str).str.strip() == u_id if "user_id" in df_disp_legacy.columns else pd.Series(False, index=df_disp_legacy.index)
            df_disp_legacy_filt = df_disp_legacy[cond_d_ag_leg | cond_d_uid_leg].copy()
            if not df_disp_legacy_filt.empty:
                if df_dispositivos.empty:
                    df_dispositivos = df_disp_legacy_filt
                else:
                    df_dispositivos = pd.concat([df_dispositivos, df_disp_legacy_filt], ignore_index=True)
    except Exception:
        pass

    try:
        res_pv = supabase.table("puntos_venta").select("*").execute()
        df_pv_all = pd.DataFrame(res_pv.data or [])
        if not df_pv_all.empty:
            df_pv_all.columns = [c.lower().strip() for c in df_pv_all.columns]
            cond_pv = df_pv_all["agencia"].astype(str).str.upper().str.strip().isin([ag_nombre.upper(), "TODAS", "TODOS", "GENERAL"]) if "agencia" in df_pv_all.columns else pd.Series(True, index=df_pv_all.index)
            df_pv_filtrado = df_pv_all[cond_pv].copy()
            if not df_pv_filtrado.empty:
                if df_dispositivos.empty:
                    df_dispositivos = df_pv_filtrado
                else:
                    df_dispositivos = pd.concat([df_dispositivos, df_pv_filtrado], ignore_index=True)
    except Exception:
        pass

    if not df_dispositivos.empty and "id" in df_dispositivos.columns:
        df_dispositivos = df_dispositivos.drop_duplicates(subset=["id"])

    # Normalización de columnas para la tabla Dispositivos de Pago
    if not df_dispositivos.empty:
        if "alias_nombre" not in df_dispositivos.columns:
            df_dispositivos["alias_nombre"] = df_dispositivos.get("nombre_dispositivo", df_dispositivos.get("nombre_pos", df_dispositivos.get("titular", "POS TAQUILLA")))
        if "cuenta_asociada" not in df_dispositivos.columns:
            df_dispositivos["cuenta_asociada"] = df_dispositivos.get("cuenta_banco", df_dispositivos.get("cuenta_resumen", df_dispositivos.get("documento_titular", "SIN CUENTA")))
        
        # Clean alias_nombre to keep only the bank name
        def clean_alias_to_bank(row):
            alias = str(row.get("alias_nombre", "")).strip()
            c_asoc = str(row.get("cuenta_asociada", "")).strip()
            return obtener_nombre_banco(alias, c_asoc)
        df_dispositivos["alias_nombre"] = df_dispositivos.apply(clean_alias_to_bank, axis=1)

        if "tipo_dispositivo" not in df_dispositivos.columns:
            df_dispositivos["tipo_dispositivo"] = df_dispositivos.get("banco", "PUNTO DE VENTA (POS)")
        if "tipo_dispositivo" in df_dispositivos.columns:
            df_dispositivos["tipo_dispositivo"] = df_dispositivos["tipo_dispositivo"].astype(str).str.replace("DISPOSITIVO: ", "", regex=False)
        if "serial_tid" not in df_dispositivos.columns:
            df_dispositivos["serial_tid"] = df_dispositivos.get("serial_pos", df_dispositivos.get("numero_cuenta", "S/N"))
        if "agencia_asignada" not in df_dispositivos.columns:
            df_dispositivos["agencia_asignada"] = df_dispositivos.get("agencia", ag_nombre)
        if "moneda" not in df_dispositivos.columns:
            df_dispositivos["moneda"] = "USD"
        if "estatus" not in df_dispositivos.columns:
            df_dispositivos["estatus"] = df_dispositivos.get("estado", "ACTIVO")
        if "notas" not in df_dispositivos.columns:
            df_dispositivos["notas"] = ""

        if "id" in df_dispositivos.columns:
            df_dispositivos["id"] = pd.to_numeric(df_dispositivos["id"], errors="coerce")
            df_dispositivos = df_dispositivos.sort_values("id")

    # ==================== TAB 1: CUENTAS BANCARIAS ====================
    with tab1:
        st.subheader("🏦 Cuentas Bancarias Asignadas")
        st.caption("Consulta de cuentas bancarias registradas por el administrador y asignadas a esta taquilla.")
        
        total_cuentas = len(df_cuentas) if not df_cuentas.empty else 0
        cuentas_activas = len(df_cuentas[df_cuentas['estatus'].astype(str).str.upper() == 'ACTIVA']) if (not df_cuentas.empty and 'estatus' in df_cuentas.columns) else total_cuentas
        monedas_sop = len(df_cuentas['moneda'].unique()) if (not df_cuentas.empty and 'moneda' in df_cuentas.columns) else 0

        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.metric("Total Cuentas Asignadas", total_cuentas)
        with col_m2:
            st.metric("Cuentas Activas", cuentas_activas)
        with col_m3:
            st.metric("Monedas Soportadas", monedas_sop)

        st.markdown("---")
        st.markdown("##### 📜 Cuentas Bancarias Registradas")

        if not df_cuentas.empty:
            columnas_mostrar_c = ["id", "banco", "titular", "numero_cuenta", "moneda", "tipo_cuenta", "agencia_asignada", "saldo_inicial", "estatus"]
            cols_existentes_c = [c for c in columnas_mostrar_c if c in df_cuentas.columns]

            st.dataframe(
                df_cuentas[cols_existentes_c],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "id": st.column_config.NumberColumn("Nº", format="%d"),
                    "banco": "Banco / Entidad",
                    "titular": "Titular",
                    "numero_cuenta": "N° Cuenta / Tel / Email",
                    "moneda": "Moneda",
                    "tipo_cuenta": "Tipo",
                    "agencia_asignada": "Agencia Asignada",
                    "saldo_inicial": st.column_config.NumberColumn("Saldo Inicial", format="%.2f"),
                    "estatus": "Estatus"
                }
            )
        else:
            st.info("ℹ️ No hay cuentas bancarias asignadas a esta taquilla por la administración.")

    # ==================== TAB 2: DISPOSITIVOS DE PAGO (POS / BIOPAGO) ====================
    with tab2:
        st.subheader("📟 Dispositivos de Pago Asignados (POS / Biopago)")
        st.caption("Puntos de Venta (POS) y dispositivos de cobro asignados a esta taquilla por la administración.")

        total_disp = len(df_dispositivos) if not df_dispositivos.empty else 0
        disp_activos = len(df_dispositivos[df_dispositivos['estatus'].astype(str).str.upper().isin(['ACTIVO', 'ACTIVA'])]) if (not df_dispositivos.empty and 'estatus' in df_dispositivos.columns) else total_disp

        col_d1, col_d2, col_d3 = st.columns(3)
        with col_d1:
            st.metric("Total Dispositivos", total_disp)
        with col_d2:
            st.metric("Dispositivos Activos", disp_activos)
        with col_d3:
            st.metric("Tipos Soportados", "POS / Biopago / QR / Datáfono")

        st.markdown("---")
        st.markdown("##### 📜 Dispositivos de Pago Registrados")

        if not df_dispositivos.empty:
            columnas_mostrar_d = ["id", "alias_nombre", "tipo_dispositivo", "serial_tid", "cuenta_asociada", "agencia_asignada", "moneda", "estatus", "notas"]
            cols_existentes_d = [c for c in columnas_mostrar_d if c in df_dispositivos.columns]

            st.dataframe(
                df_dispositivos[cols_existentes_d],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "id": st.column_config.NumberColumn("Nº", format="%d"),
                    "alias_nombre": "Alias / Nombre",
                    "tipo_dispositivo": "Tipo Dispositivo",
                    "serial_tid": "Serial / TID",
                    "cuenta_asociada": "Cuenta Asociada",
                    "agencia_asignada": "Agencia Asignada",
                    "moneda": "Moneda",
                    "estatus": "Estatus",
                    "notas": "Notas"
                }
            )
        else:
            st.info("ℹ️ No hay dispositivos de pago (POS / Biopago) asignados a esta taquilla.")

    # ==================== TAB 3: REGISTRAR PAGO ====================
    with tab3:
        render_titulo_seccion("💸 Registrar Pago Recibido")

        fecha_hoy = datetime.now().date()
        cerrado = dia_esta_cerrado(ag_nombre, fecha_hoy)
        if cerrado:
            st.warning(f"🔒 El día {fecha_hoy} está cerrado. Los registros se guardarán con la fecha actual.")

        metodos_bancarios_opciones = [
            "Punto de Venta", 
            "BioPago", 
            "Pago Móvil", 
            "Zelle", 
            "Transferencia Bancaria", 
            "Depósito Bancario", 
            "Binance / Cripto", 
            "PayPal", 
            "Otro (Cuenta Admin)"
        ]

        # Construir lista unificada de todos los dispositivos y cuentas asignadas
        mapa_destinos = {}
        lista_opciones_destino = []

        # 1. Cargar Dispositivos de Pago (POS / BioPago)
        if not df_dispositivos.empty:
            df_disp_activos = df_dispositivos[df_dispositivos["estatus"].astype(str).str.upper().isin(["ACTIVO", "ACTIVA"])] if "estatus" in df_dispositivos.columns else df_dispositivos
            if df_disp_activos.empty:
                df_disp_activos = df_dispositivos
            for _, r_disp in df_disp_activos.iterrows():
                alias = str(r_disp.get("alias_nombre", "")).strip()
                tipo = str(r_disp.get("tipo_dispositivo", "PUNTO DE VENTA (POS)")).strip()
                s_tid = str(r_disp.get("serial_tid", "")).strip()
                c_asoc = str(r_disp.get("cuenta_asociada", "")).strip()
                mon_item = str(r_disp.get("moneda", "USD")).strip().upper() or "USD"

                # Keep only the bank name as the selectbox label
                base_lbl = alias
                lbl = base_lbl
                counter = 1
                while lbl in mapa_destinos:
                    lbl = f"{base_lbl} #{counter}"
                    counter += 1

                tipo_u = tipo.upper()
                met_impl = "BioPago" if "BIOPAGO" in tipo_u else "Punto de Venta"

                lista_opciones_destino.append(lbl)
                mapa_destinos[lbl] = {"moneda": mon_item, "metodo": met_impl}

        # 2. Cargar Cuentas Bancarias Asignadas
        if not df_cuentas.empty:
            for _, r in df_cuentas.iterrows():
                b_name = str(r.get("banco", "Banco")).strip().upper()
                tit = str(r.get("titular", "")).strip()
                n_acc = str(r.get("numero_cuenta") or r.get("identificador") or r.get("email") or "").strip()
                mon_item = str(r.get("moneda", "USD")).strip().upper() or "USD"
                tipo_c = str(r.get("tipo_cuenta", "")).strip()

                desc = f"{b_name} | {tit}"
                if n_acc and n_acc != "N/A":
                    desc += f" - N°: {n_acc}"
                if mon_item:
                    desc += f" ({mon_item})"
                if tipo_c:
                    desc += f" [{tipo_c}]"

                tc_u = tipo_c.upper()
                bn_u = b_name.upper()
                if "PAGO MÓVIL" in tc_u or "PAGO MOVIL" in tc_u or "PAGO MÓVIL" in bn_u or "PAGO MOVIL" in bn_u:
                    met_impl = "Pago Móvil"
                elif "ZELLE" in tc_u or "ZELLE" in bn_u:
                    met_impl = "Zelle"
                elif "BINANCE" in tc_u or "CRIPTO" in tc_u or "BINANCE" in bn_u:
                    met_impl = "Binance / Cripto"
                elif "PAYPAL" in tc_u or "PAYPAL" in bn_u:
                    met_impl = "PayPal"
                elif "DEPÓSITO" in tc_u or "DEPOSITO" in tc_u:
                    met_impl = "Depósito Bancario"
                elif "TRANSFERENCIA" in tc_u or "CORRIENTE" in tc_u or "AHORRO" in tc_u:
                    met_impl = "Transferencia Bancaria"
                else:
                    met_impl = "Otro (Cuenta Admin)"

                lista_opciones_destino.append(desc)
                mapa_destinos[desc] = {"moneda": mon_item, "metodo": met_impl}

        if not lista_opciones_destino:
            lbl_def = "POS / Cuenta Taquilla General (USD)"
            lista_opciones_destino = [lbl_def]
            mapa_destinos[lbl_def] = {"moneda": "USD", "metodo": "Punto de Venta"}

        col_top1, col_top2 = st.columns([2, 4])
        fecha_pago = col_top1.date_input("Fecha de Operación", value=fecha_hoy, key="reg_fecha_pago")
        pos_o_cuenta = col_top2.selectbox("Seleccione Dispositivo / Cuenta de Pago Asignado*", lista_opciones_destino, key="reg_destino_unificado")

        # Auto-detectar la moneda y el método según la cuenta/dispositivo seleccionado (sin permitir cambio manual)
        meta_sel = mapa_destinos.get(pos_o_cuenta, {"moneda": "USD", "metodo": "Punto de Venta"})
        moneda_pago = meta_sel.get("moneda", "USD")
        metodo_pago = meta_sel.get("metodo", "Punto de Venta")

        if moneda_pago not in ["USD", "BS", "COP"]:
            if "BS" in moneda_pago or "VES" in moneda_pago:
                moneda_pago = "BS"
            elif "COP" in moneda_pago:
                moneda_pago = "COP"
            else:
                moneda_pago = "USD"

        col_inf1, col_inf2 = st.columns([3, 3])
        col_inf1.text_input("Moneda (Definida por la cuenta/dispositivo)*", value=moneda_pago, disabled=True, key=f"dis_mon_{pos_o_cuenta}")
        col_inf2.text_input("Método de Pago Asignado*", value=metodo_pago, disabled=True, key=f"dis_met_{pos_o_cuenta}")

        # Campos de Pago (Monto primero, luego Concepto)
        col_v1, col_v2 = st.columns([2, 4])
        monto_pago = col_v1.number_input("Monto Recibido*", min_value=0.0, format="%.2f", key="reg_monto_pago")
        concepto = col_v2.selectbox("Concepto de Operación*", ["Compra de Tickets", "Recibos Punto Venta"], key="reg_concepto_pago")

        # Campos dinámicos según el concepto seleccionado
        if concepto == "Compra de Tickets":
            col_f1, col_f2 = st.columns([3, 3])
            referencia = col_f1.text_input("Número de Referencia / Comprobante*", placeholder="Ej: 987654 / Últimos 6 dígitos", key="reg_ref_pago")
            datos_cliente = col_f2.text_input("Datos del Pagador / Titular", placeholder="Ej: V-14567890 / Pedro Pérez", key="reg_datos_cliente")
        else:
            referencia = st.text_input("Número de Referencia / Comprobante*", placeholder="Ej: 987654 / Últimos 6 dígitos", key="reg_ref_pago")
            datos_cliente = ""

        # Botón de envío
        if st.button("💾 REGISTRAR PAGO BANCARIO", use_container_width=True, type="primary"):
            if monto_pago <= 0:
                st.error("Ingrese un monto válido mayor a cero.")
            elif not referencia.strip():
                st.error("Debe proporcionar un número de referencia o comprobante.")
            else:
                try:
                    cajero_id_b = st.session_state.get("cajero_actual", {}).get("id")
                    # 1. Guardar en tabla cda_pagos_bancarios
                    data_bancaria = {
                        "fecha": str(fecha_pago),
                        "agencia": ag_nombre,
                        "metodo_pago": metodo_pago,
                        "monto": round(float(monto_pago), 2),
                        "moneda": moneda_pago,
                        "referencia": referencia.strip().upper(),
                        "concepto": concepto,
                        "datos_pagador": datos_cliente.strip().upper() if datos_cliente else "N/A",
                        "pos_o_cuenta": pos_o_cuenta,
                        "user_id": u_id,
                        "cajero_id": cajero_id_b,
                        "created_at": datetime.now().isoformat()
                    }
                    supabase.table("cda_pagos_bancarios").insert(data_bancaria).execute()

                    # 2. Registrar en cda_pagos_diarios para mantener unificados los reportes diarios
                    supabase.table("cda_pagos_diarios").insert({
                        "fecha": str(fecha_pago),
                        "agencia": ag_nombre,
                        "tipo_pago": f"{metodo_pago} (Ref: {referencia.strip().upper()})",
                        "monto": round(float(monto_pago), 2),
                        "moneda": moneda_pago,
                        "user_id": u_id,
                        "cajero_id": cajero_id_b
                    }).execute()

                    st.success(f"✅ Pago por {metodo_pago} (Ref: {referencia}) registrado exitosamente!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar transacción: {e}")

    # ==================== TAB 4: HISTORIAL Y RESUMEN ====================
    with tab4:
        render_titulo_seccion("📊 Historial de Transacciones Bancarias")

        c_f1, _ = st.columns([2, 2])
        fecha_hist = c_f1.date_input("📅 Filtrar por Fecha:", value=datetime.now().date(), key="fecha_hist_bancaria")

        cajero_info_b = st.session_state.get("cajero_actual", {})
        rol_usuario_b = cajero_info_b.get("rol", "cajero")
        cajero_id_b = cajero_info_b.get("id")
        es_supervisor_b = (rol_usuario_b == 'supervisor')

        try:
            res_pb = supabase.table("cda_pagos_bancarios").select("*").eq("fecha", str(fecha_hist)).execute()
            df_pb = pd.DataFrame(res_pb.data or [])
            if not df_pb.empty:
                df_pb.columns = [c.lower() for c in df_pb.columns]
                if not es_supervisor_b and cajero_id_b:
                    col_pb = "cajero_id" if "cajero_id" in df_pb.columns else ("user_id" if "user_id" in df_pb.columns else None)
                    if col_pb and col_pb in df_pb.columns:
                        df_pb = df_pb[df_pb[col_pb].astype(str) == str(cajero_id_b)]
        except Exception:
            df_pb = pd.DataFrame()

        if not df_pb.empty:
            met_col = df_pb["metodo_pago"].astype(str).str.upper()
            df_pos_m = df_pb[met_col == "PUNTO DE VENTA"]
            df_biopago_m = df_pb[met_col == "BIOPAGO"]
            df_pm_m = df_pb[met_col == "PAGO MÓVIL"]
            df_zelle_m = df_pb[met_col == "ZELLE"]
            df_transf_m = df_pb[met_col.str.contains("TRANSFERENCIA|DEPÓSITO|DEPOSITO", regex=True, na=False)]
            df_efectivo_m = df_pb[met_col.str.contains("EFECTIVO", regex=True, na=False)]
            df_otros_m = df_pb[
                ~met_col.isin(["PUNTO DE VENTA", "BIOPAGO", "PAGO MÓVIL", "ZELLE"]) &
                ~met_col.str.contains("TRANSFERENCIA|DEPÓSITO|DEPOSITO|EFECTIVO", regex=True, na=False)
            ]

            tot_pos = float(df_pos_m["monto"].sum()) if not df_pos_m.empty else 0.0
            tot_biopago = float(df_biopago_m["monto"].sum()) if not df_biopago_m.empty else 0.0
            tot_pm = float(df_pm_m["monto"].sum()) if not df_pm_m.empty else 0.0
            tot_zelle = float(df_zelle_m["monto"].sum()) if not df_zelle_m.empty else 0.0
            tot_transf = float(df_transf_m["monto"].sum()) if not df_transf_m.empty else 0.0
            tot_efectivo = float(df_efectivo_m["monto"].sum()) if not df_efectivo_m.empty else 0.0
            tot_otros = float(df_otros_m["monto"].sum()) if not df_otros_m.empty else 0.0
            tot_total = float(df_pb["monto"].sum())

            is_dark = st.session_state.get("tema_oscuro", True)
            bg_card = "rgba(30, 41, 59, 0.6)" if is_dark else "#f8fafc"
            border_card = "rgba(255, 255, 255, 0.08)" if is_dark else "#e2e8f0"
            txt_label = "#94a3b8" if is_dark else "#64748b"
            txt_val = "#f8fafc" if is_dark else "#0f172a"

            cols_m = st.columns(7)
            met_cards = [
                ("📟 POS", f"${tot_pos:,.2f}"),
                ("👆 BioPago", f"${tot_biopago:,.2f}"),
                ("📲 Pago Móvil", f"${tot_pm:,.2f}"),
                ("💵 Zelle", f"${tot_zelle:,.2f}"),
                ("🏦 Transf/Dep", f"${tot_transf:,.2f}"),
                ("💵 Efectivo (Por Cobrar)", f"${tot_efectivo:,.2f}"),
                ("🏛️ Total General", f"${tot_total:,.2f}")
            ]

            for i, (l_title, l_val) in enumerate(met_cards):
                card_h = f"""<div style="background: {bg_card}; border: 1px solid {border_card}; border-radius: 8px; padding: 8px; text-align: center;">
                <div style="font-size: 10px; font-weight: 700; color: {txt_label}; text-transform: uppercase;">{l_title}</div>
                <div style="font-size: 13px; font-weight: 700; color: { '#34d399' if 'Total' in l_title else txt_val };">{l_val}</div>
                </div>"""
                cols_m[i].markdown(card_h, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            cols_show_pb = [c for c in ["fecha", "metodo_pago", "monto", "moneda", "referencia", "pos_o_cuenta", "concepto", "datos_pagador", "created_at"] if c in df_pb.columns]
            st.dataframe(df_pb[cols_show_pb], use_container_width=True, hide_index=True)
        else:
            st.info(f"ℹ️ No hay transacciones bancarias registradas el día {fecha_hist}.")


def modulo_reporte_rango(agencia_data):
    render_encabezado_principal("📊 Reporte por Rango de Fechas")
    render_subtitulo_terminal(agencia_data['nombre_agencia'])
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

        cajero_info = st.session_state.get("cajero_actual", {})
        rol_usuario = cajero_info.get("rol", "cajero")
        cajero_id = cajero_info.get("id")
        es_supervisor = (rol_usuario == 'supervisor')

        if not es_supervisor and cajero_id:
            if not df_v.empty and "cajero_id" in df_v.columns:
                df_v = df_v[df_v["cajero_id"].astype(str) == str(cajero_id)]
            if not df_t.empty:
                col_t = "cajero_id" if "cajero_id" in df_t.columns else ("user_id" if "user_id" in df_t.columns else None)
                if col_t and col_t in df_t.columns: df_t = df_t[df_t[col_t].astype(str) == str(cajero_id)]
            if not df_g.empty:
                col_g = "cajero_id" if "cajero_id" in df_g.columns else ("user_id" if "user_id" in df_g.columns else None)
                if col_g and col_g in df_g.columns: df_g = df_g[df_g[col_g].astype(str) == str(cajero_id)]
            if not df_p.empty:
                col_p = "cajero_id" if "cajero_id" in df_p.columns else ("user_id" if "user_id" in df_p.columns else None)
                if col_p and col_p in df_p.columns: df_p = df_p[df_p[col_p].astype(str) == str(cajero_id)]
    except Exception as e:
        st.error(f"Error: {e}"); return

    render_titulo_seccion("📈 Resumen General")
    tv = float(df_v['monto_venta'].sum()) if not df_v.empty else 0
    tc = float(df_v['comision'].sum()) if not df_v.empty else 0
    tp = float(df_v['monto_premios'].sum()) if not df_v.empty else 0
    tg = float(df_g['monto'].sum()) if not df_g.empty else 0
    tpg = float(df_p['monto'].sum()) if not df_p.empty else 0
    saldo_calculado = tv - tc - tp - tg - tpg

    # Calcular Saldo Anterior y Saldo Final
    nom = agencia_data['nombre_agencia']
    saldo_ant = obtener_saldo_anterior(nom, d, cajero_id=cajero_id if not es_supervisor else None)
    t_saldo_final = saldo_ant + saldo_calculado

    render_tarjetas_metricas(tv, tc, tp, tg, tpg, saldo_calculado)

    st.markdown(
        f"""
        <div style="background-color: rgba(13, 27, 34, 0.4); padding: 1rem; border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.05); margin-top: 1rem; text-align: center;">
            <span style="font-size: 0.85rem; color: #94a3b8;">Saldo Anterior al {d}:</span> <b style="font-size: 1rem; color: #ffffff;">${saldo_ant:,.2f}</b>
            <span style="margin: 0 1rem; color: rgba(255,255,255,0.2);">|</span>
            <span style="font-size: 0.85rem; color: #94a3b8;">Resultado del Período:</span> <b style="font-size: 1rem; color: #ffffff;">${saldo_calculado:,.2f}</b>
            <span style="margin: 0 1rem; color: rgba(255,255,255,0.2);">|</span>
            <span style="font-size: 0.85rem; color: #94a3b8;">Saldo Final:</span> <b style="font-size: 1.1rem; color: #00c853;">${t_saldo_final:,.2f}</b>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.divider()

    render_titulo_seccion("📋 Detalle por Día")
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
        lines.append(f"  SALDO PERIODO:   ${saldo_calculado:>10,.2f}")
        lines.append(f"  SALDO ANTERIOR:  ${saldo_ant:>10,.2f}")
        lines.append(f"  SALDO FINAL:     ${t_saldo_final:>10,.2f}")
        lines.append("=" * 36)
        lines.append("  Generado: " + obtener_hora_local().strftime("%Y-%m-%d %H:%M"))
        lines.append("=" * 36)
        return "\n".join(lines)

    txt_r = txt_rango()
    st.text_area("📄 Vista previa", txt_r, height=200)
    wa_url = f"https://wa.me/?text={urllib.parse.quote(txt_r)}"
    st.link_button("📲 Compartir por WhatsApp", url=wa_url, use_container_width=True)


def modulo_cierre_diario(agencia_data):
    render_encabezado_principal("🔒 Cierre Diario")
    u_id = agencia_data['user_id']
    nom = agencia_data['nombre_agencia']
    cajero_info = st.session_state.get("cajero_actual", {})
    cajero_id = cajero_info.get("id")
    es_supervisor = (cajero_info.get("rol", "") == "supervisor")

    ult_fecha = obtener_ultimo_dia_cerrado(nom, cajero_id=cajero_id if not es_supervisor else None)
    fecha_defecto = ult_fecha if ult_fecha else datetime.now().date()

    if "fecha_cierre" not in st.session_state or st.session_state.get("last_cierre_cajero") != str(cajero_id):
        st.session_state["fecha_cierre"] = fecha_defecto
        st.session_state["last_cierre_cajero"] = str(cajero_id)

    fecha_sel = st.date_input(
        "📅 Seleccione el día a cerrar:",
        value=st.session_state["fecha_cierre"],
        key="fecha_cierre_input"
    )

    cerrado = dia_esta_cerrado(nom, fecha_sel, cajero_id=cajero_id if not es_supervisor else None)

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

        if not es_supervisor and cajero_id:
            if not df_v.empty and "cajero_id" in df_v.columns:
                df_v = df_v[df_v["cajero_id"].astype(str) == str(cajero_id)]
            if not df_g.empty:
                col_g = "cajero_id" if "cajero_id" in df_g.columns else ("user_id" if "user_id" in df_g.columns else None)
                if col_g and col_g in df_g.columns:
                    df_g = df_g[df_g[col_g].astype(str) == str(cajero_id)]
            if not df_pg.empty:
                col_p = "cajero_id" if "cajero_id" in df_pg.columns else ("user_id" if "user_id" in df_pg.columns else None)
                if col_p and col_p in df_pg.columns:
                    df_pg = df_pg[df_pg[col_p].astype(str) == str(cajero_id)]
    except Exception as e:
        st.error(f"Error: {e}"); return

    t_venta = float(df_v['monto_venta'].sum()) if not df_v.empty else 0
    t_comis = float(df_v['comision'].sum()) if not df_v.empty else 0
    t_premios = float(df_v['monto_premios'].sum()) if not df_v.empty else 0
    t_gastos = float(df_g['monto'].sum()) if not df_g.empty else 0
    t_pagos = float(df_pg['monto'].sum()) if not df_pg.empty else 0
    t_saldo_dia = t_venta - t_comis - t_premios - t_gastos - t_pagos

    # Calcular Saldo Anterior y Saldo Final
    saldo_ant = obtener_saldo_anterior(nom, fecha_sel, cajero_id=cajero_id if not es_supervisor else None)
    t_saldo_final = saldo_ant + t_saldo_dia

    if cerrado:
        try:
            q_hoy = supabase.table("saldo_taquilla").select("saldo_restante").eq("nombre_agency", nom).eq("fecha", str(fecha_sel))
            if not es_supervisor and cajero_id:
                q_hoy = q_hoy.eq("cajero_id", cajero_id)
            res_hoy = q_hoy.execute()
            if res_hoy.data:
                t_saldo_final = float(res_hoy.data[0]["saldo_restante"])
        except Exception:
            pass

    render_titulo_seccion(f"📊 Resumen del {fecha_sel}")
    
    render_tarjetas_metricas(t_venta, t_comis, t_premios, t_gastos, t_pagos, t_saldo_dia)

    st.markdown(
        f"""
        <div style="background-color: rgba(13, 27, 34, 0.4); padding: 1rem; border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.05); margin-top: 1rem; text-align: center;">
            <span style="font-size: 0.85rem; color: #94a3b8;">Saldo Anterior:</span> <b style="font-size: 1rem; color: #ffffff;">${saldo_ant:,.2f}</b>
            <span style="margin: 0 1rem; color: rgba(255,255,255,0.2);">|</span>
            <span style="font-size: 0.85rem; color: #94a3b8;">Resultado del Día:</span> <b style="font-size: 1rem; color: #ffffff;">${t_saldo_dia:,.2f}</b>
            <span style="margin: 0 1rem; color: rgba(255,255,255,0.2);">|</span>
            <span style="font-size: 0.85rem; color: #94a3b8;">Saldo Final:</span> <b style="font-size: 1.1rem; color: #00c853;">${t_saldo_final:,.2f}</b>
        </div>
        """,
        unsafe_allow_html=True
    )

    if not df_v.empty:
        render_titulo_seccion("📋 Detalle por Sistema y Cajero")
        with st.expander("📋 Ver Detalle por Sistema y Cajero", expanded=True):
            try:
                res_u = supabase.table("taquilla_usuarios").select("id, usuario, nombre_cajero").execute()
                u_map = {str(u["id"]): u.get("nombre_cajero") or u.get("usuario") for u in (res_u.data or [])}
                df_v_display = df_v.copy()
                if "cajero_id" in df_v_display.columns:
                    df_v_display["cajero"] = df_v_display["cajero_id"].astype(str).map(lambda x: u_map.get(x, f"ID {x}" if x != "None" and x != "nan" else "General"))
                    group_cols = ["sistema", "cajero"]
                else:
                    group_cols = ["sistema"]
                num_cols = [c for c in ["monto_venta", "comision", "monto_premios"] if c in df_v_display.columns]
                df_v_summary = df_v_display.groupby(group_cols, as_index=False)[num_cols].sum()
                st.dataframe(df_v_summary, use_container_width=True, hide_index=True)
            except Exception:
                num_cols = [c for c in ["monto_venta", "comision", "monto_premios"] if c in df_v.columns]
                df_v_summary = df_v.groupby("sistema", as_index=False)[num_cols].sum()
                st.dataframe(df_v_summary, use_container_width=True, hide_index=True)

    st.divider()

    if cerrado:
        st.success(f"✅ El día {fecha_sel} está **CERRADO**.")
        if es_supervisor:
            if st.button("🔓 Reabrir Día (solo supervisor)", type="secondary", use_container_width=True):
                if reabrir_dia(nom, fecha_sel, cajero_id=cajero_id if not es_supervisor else None):
                    st.success("✅ Día reabierto exitosamente por el supervisor."); time.sleep(1); st.rerun()
    else:
        if df_v.empty and df_g.empty and df_pg.empty:
            st.info("ℹ️ No hay datos registrados para este día. Carga al menos una venta antes de cerrar.")
        else:
            if st.button("🔒 Cerrar Día", type="primary", use_container_width=True):
                c_id_close = cajero_id if not es_supervisor else None
                if cerrar_dia(nom, fecha_sel, c_id_close):
                    try:
                        saldo_payload = {
                            "nombre_agency": nom,
                            "fecha": str(fecha_sel),
                            "saldo_restante": t_saldo_final,
                        }
                        if cajero_id:
                            saldo_payload["cajero_id"] = cajero_id
                        supabase.table("saldo_taquilla").upsert(saldo_payload).execute()
                        st.success("✅ Día cerrado y saldo guardado exitosamente.")
                    except Exception as e:
                        st.error(f"Error al guardar el saldo restante: {e}")
                    time.sleep(1); st.rerun()


def modulo_premios_tickets(agencia_data):
    render_encabezado_principal("🎟️ Tickets Premiados")
    rol_actual = st.session_state.get("cajero_actual", {}).get("rol", "cajero")
    es_supervisor = (rol_actual == "supervisor")
    u_id_real = str(st.session_state.get("cajero_actual", {}).get("id", agencia_data['user_id']))
    u_id_dueno = agencia_data['user_id']
    ag_nombre = agencia_data['nombre_agencia']

    if "fecha_ticket_filtro" not in st.session_state:
        st.session_state["fecha_ticket_filtro"] = datetime.now().date()

    col_f, _ = st.columns([2, 2])
    with col_f:
        fecha_filtro = st.date_input(
            "📅 Ver tickets del día:",
            value=st.session_state["fecha_ticket_filtro"],
            key="fecha_ticket_filtro_input"
        )

    try:
        query_t = supabase.table("cda_premios_tickets")\
            .select("*")\
            .eq("agencia", ag_nombre)\
            .eq("fecha", str(fecha_filtro))
        if not es_supervisor:
            query_t = query_t.eq("user_id", u_id_real)
        res = query_t.order("fecha", desc=False).execute()
        df_t = pd.DataFrame(res.data or [])
        if not df_t.empty:
            df_t.columns = [c.lower() for c in df_t.columns]
    except Exception as e:
        st.error(f"Error al cargar tickets: {e}")
        df_t = pd.DataFrame()

    if not df_t.empty:
        render_titulo_seccion("📋 Tickets Registrados")
        st.dataframe(df_t, use_container_width=True, hide_index=True)
    else:
        st.info("ℹ️ No hay tickets registrados por tu usuario para este día.")

    if es_supervisor:
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

    cerrado = dia_esta_cerrado(ag_nombre, fecha_filtro, cajero_id=u_id_real if not es_supervisor else None)
    if cerrado and not es_supervisor:
        st.warning(f"🔒 Tu jornada del día {fecha_filtro} está cerrada. No se pueden registrar nuevos tickets.")
    elif cerrado and es_supervisor:
        st.info(f"🔒 El día {fecha_filtro} está cerrado. Solo un supervisor puede registrar tickets.")

    permitir_nuevo = not cerrado or es_supervisor
    if permitir_nuevo:
        with st.container(border=True):
            render_titulo_seccion("📝 Registrar Nuevo Premio")
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
                                    .eq("nombre_agency", ag_nombre).eq("fecha", str(fecha_p)).eq("sistema", sistema_p).eq("cajero_id", u_id_real).execute()
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
                                    .eq("nombre_agency", ag_nombre).eq("fecha", str(fecha_p)).eq("sistema", sistema_p).eq("cajero_id", u_id_real).execute()
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
                                        .eq("nombre_agency", ag_nombre).eq("fecha", str(fecha_p)).eq("sistema", sistema_p).eq("cajero_id", u_id_real).execute()
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
    render_encabezado_principal("📆 Reporte Detallado por Día")
    render_subtitulo_terminal(agencia_data['nombre_agencia'])
    u_id = agencia_data['user_id']

    if "fecha_reporte_dia" not in st.session_state:
        st.session_state["fecha_reporte_dia"] = datetime.now().date()

    fecha_sel = st.date_input(
        "📅 Seleccione el día:",
        value=st.session_state["fecha_reporte_dia"],
        key="fecha_reporte_dia_input"
    )

    cajero_info = st.session_state.get("cajero_actual", {})
    rol_actual = cajero_info.get("rol", "cajero")
    cajero_id = cajero_info.get("id")
    es_supervisor = (rol_actual == "supervisor")

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

        if not es_supervisor and cajero_id:
            if not df_v.empty and "cajero_id" in df_v.columns:
                df_v = df_v[df_v["cajero_id"].astype(str) == str(cajero_id)]
            if not df_t.empty:
                col_t = "cajero_id" if "cajero_id" in df_t.columns else ("user_id" if "user_id" in df_t.columns else None)
                if col_t and col_t in df_t.columns: df_t = df_t[df_t[col_t].astype(str) == str(cajero_id)]
            if not df_g.empty:
                col_g = "cajero_id" if "cajero_id" in df_g.columns else ("user_id" if "user_id" in df_g.columns else None)
                if col_g and col_g in df_g.columns: df_g = df_g[df_g[col_g].astype(str) == str(cajero_id)]
            if not df_p.empty:
                col_p = "cajero_id" if "cajero_id" in df_p.columns else ("user_id" if "user_id" in df_p.columns else None)
                if col_p and col_p in df_p.columns: df_p = df_p[df_p[col_p].astype(str) == str(cajero_id)]
    except Exception as e:
        st.error(f"Error: {e}"); return

    t_venta = float(df_v['monto_venta'].sum()) if not df_v.empty else 0.0
    t_comis = float(df_v['comision'].sum()) if not df_v.empty else 0.0
    t_premios = float(df_v['monto_premios'].sum()) if not df_v.empty else 0.0
    t_gastos = float(df_g['monto'].sum()) if not df_g.empty else 0.0
    t_pagos = float(df_p['monto'].sum()) if not df_p.empty else 0.0
    t_saldo = t_venta - t_comis - t_premios - t_gastos - t_pagos

    # Calcular Saldo Anterior y Saldo Final
    nom = agencia_data['nombre_agencia']
    saldo_ant = obtener_saldo_anterior(nom, fecha_sel, cajero_id=cajero_id if not es_supervisor else None)
    t_saldo_final = saldo_ant + t_saldo

    render_tarjetas_metricas(t_venta, t_comis, t_premios, t_gastos, t_pagos, t_saldo)

    st.markdown(
        f"""
        <div style="background-color: rgba(13, 27, 34, 0.4); padding: 1rem; border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.05); margin-top: 1rem; text-align: center;">
            <span style="font-size: 0.85rem; color: #94a3b8;">Saldo Anterior:</span> <b style="font-size: 1rem; color: #ffffff;">${saldo_ant:,.2f}</b>
            <span style="margin: 0 1rem; color: rgba(255,255,255,0.2);">|</span>
            <span style="font-size: 0.85rem; color: #94a3b8;">Resultado del Día:</span> <b style="font-size: 1rem; color: #ffffff;">${t_saldo:,.2f}</b>
            <span style="margin: 0 1rem; color: rgba(255,255,255,0.2);">|</span>
            <span style="font-size: 0.85rem; color: #94a3b8;">Saldo Final:</span> <b style="font-size: 1.1rem; color: #00c853;">${t_saldo_final:,.2f}</b>
        </div>
        """,
        unsafe_allow_html=True
    )

    render_titulo_seccion("📋 Detalle por Sistema")
    with st.expander("📋 Ver Detalle por Sistema", expanded=True):
        if not df_v.empty:
            num_cols = [c for c in ["monto_venta", "comision", "monto_premios"] if c in df_v.columns]
            df_v_grouped = df_v.groupby("sistema", as_index=False)[num_cols].sum()
            st.dataframe(df_v_grouped, use_container_width=True, hide_index=True)
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
            num_cols = [c for c in ["monto_venta", "comision", "monto_premios"] if c in df_v.columns]
            df_v_print = df_v.groupby("sistema", as_index=False)[num_cols].sum()
            for _, r in df_v_print.iterrows():
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
        lines.append(f"  SALDO DEL DIA:   ${t_saldo:>10,.2f}")
        lines.append(f"  SALDO ANTERIOR:  ${saldo_ant:>10,.2f}")
        lines.append(f"  SALDO FINAL:     ${t_saldo_final:>10,.2f}")
        lines.append(line)

        if not df_t.empty:
            lines.append("  TICKETS PREMIADOS")
            lines.append("-" * 36)
            df_t_pago = df_t[df_t["estado"] == "RECLAMADO"] if "estado" in df_t.columns else df_t
            total_t_pago = 0.0
            for _, r in df_t_pago.iterrows():
                t_sis = r.get('sistema', '')
                t_mon = r.get('moneda', '')
                t_est = r.get('estado', '')
                t_est = "PAGO" if t_est == "RECLAMADO" else t_est
                monto_val = float(r.get('monto', 0))
                total_t_pago += monto_val
                lines.append(f"  {r.get('numero_ticket','?'):>8s}  {monto_val:>10,.2f}  {t_mon} {t_sis}  {t_est}")
            lines.append("-" * 36)
            lines.append(f"  TOTAL TICKETS:   ${total_t_pago:>10,.2f}")
            lines.append(line)

        if not df_g.empty:
            lines.append("  GASTOS")
            lines.append("-" * 36)
            for _, r in df_g.iterrows():
                lines.append(f"  {r.get('concepto','?')}  ${float(r['monto']):>10,.2f}")
            lines.append("-" * 36)
            lines.append(f"  TOTAL GASTOS:    ${t_gastos:>10,.2f}")
            lines.append(line)

        if not df_p.empty:
            lines.append("  PAGOS")
            lines.append("-" * 36)
            for _, r in df_p.iterrows():
                lines.append(f"  {r.get('tipo_pago','?')}  ${float(r['monto']):>10,.2f}")
            lines.append("-" * 36)
            lines.append(f"  TOTAL PAGOS:     ${t_pagos:>10,.2f}")
            lines.append(line)

        lines.append("  Generado: " + obtener_hora_local().strftime("%Y-%m-%d %H:%M"))
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
    _, col_login, _ = st.columns([1.3, 1.4, 1.3])
    with col_login:
        st.write("")
        with st.form("login_form", clear_on_submit=False):
            st.markdown(
                """
                <div style="text-align: center; margin-bottom: 1rem;">
                    <div style="font-size: 2.25rem; margin-bottom: 0.25rem;">🔐</div>
                    <h2 style="font-size: 1.4rem; font-weight: 700; margin: 0; letter-spacing: -0.02em; line-height: 1.2;">
                        Taquilla POS
                    </h2>
                    <p style="font-size: 0.8rem; margin-top: 0.2rem; font-weight: 400; opacity: 0.7;">
                        Acceso al sistema
                    </p>
                </div>
                """, 
                unsafe_allow_html=True
            )
            user_input = st.text_input("Usuario", placeholder="Ingresa tu usuario").strip()
            key_input = st.text_input("Clave", type="password", placeholder="Ingresa tu clave").strip()
            
            # Contenedor para spinner y mensajes de error dentro del formulario
            status_placeholder = st.empty()
            
            submitted = st.form_submit_button("Iniciar Sesión", use_container_width=True)

        if submitted:
            if not user_input or not key_input:
                status_placeholder.error("Por favor, ingrese usuario y clave.")
            else:
                with status_placeholder:
                    with st.spinner("Verificando usuario..."):
                        time.sleep(0.5)
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
                        status_placeholder.error("Agencia no encontrada.")
                else:
                    status_placeholder.error("Credenciales incorrectas.")
else:
    _check_cerrado_col()
    _check_saldo_taquilla_table()
    ag = st.session_state.agencia_actual
    cajero = st.session_state.cajero_actual
    cajero_id_sb = None if cajero.get('rol') == 'supervisor' else cajero.get('id')
    ultimo_cierre = obtener_ultimo_dia_cerrado(ag['nombre_agencia'], cajero_id=cajero_id_sb)

    if st.session_state.tema_oscuro:
        dashboard_css = """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');

        /* Global theme variables overrides */
        :root, .stApp {
            --primary-color: #00c853 !important;
            --background-color: #071217 !important;
            --secondary-background-color: #0d1b22 !important;
            --text-color: #f8fafc !important;
            font-family: 'Plus Jakarta Sans', sans-serif !important;
        }

        [data-testid="stHeader"] {
            background-color: rgba(7, 18, 23, 0.8) !important;
            backdrop-filter: blur(12px) !important;
            -webkit-backdrop-filter: blur(12px) !important;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05) !important;
        }

        footer, [data-testid="stDecoration"] {
            display: none !important;
        }

        /* Page background colors - dark mode */
        .stApp, [data-testid="stAppViewContainer"], section.main, .main {
            background-color: #071217 !important;
            background-image: 
                radial-gradient(at 0% 0%, rgba(0, 200, 83, 0.06) 0px, transparent 40%),
                radial-gradient(at 100% 100%, rgba(0, 210, 182, 0.04) 0px, transparent 40%) !important;
            background-size: cover !important;
            min-height: 100vh !important;
        }

        [data-testid="stSidebar"], [data-testid="stSidebar"] > div {
            background-color: #0d1b22 !important;
            border-right: 1px solid rgba(255, 255, 255, 0.06) !important;
        }

        [data-testid="stBlockContainer"],
        [data-testid="stAppViewBlockContainer"],
        .block-container {
            max-width: 100% !important;
            padding: 2rem 3rem !important;
        }

        /* Dashboard Forms - Full Responsive Width */
        [data-testid="stForm"] {
            background-color: rgba(13, 27, 34, 0.45) !important;
            backdrop-filter: blur(12px) !important;
            -webkit-backdrop-filter: blur(12px) !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            border-radius: 16px !important;
            padding: 1.5rem !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25) !important;
            width: 100% !important;
            max-width: 100% !important;
            margin: 0 0 1.5rem 0 !important;
        }

        @media (max-width: 768px) {
            [data-testid="stBlockContainer"],
            .block-container {
                padding: 1.25rem 1rem !important;
            }
            [data-testid="stForm"] {
                padding: 1rem !important;
            }
        }

        /* Style Metric Cards */
        [data-testid="stMetric"] {
            background-color: rgba(13, 27, 34, 0.45) !important;
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
            border-color: rgba(0, 200, 83, 0.25) !important;
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
            background-color: rgba(13, 27, 34, 0.35) !important;
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
            background-color: #0d1b22 !important;
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
            background-color: #0d1b22 !important;
        }
        div[data-baseweb="input"]:focus-within,
        div[data-baseweb="textarea"]:focus-within,
        div[data-baseweb="select"]:focus-within {
            border-color: #00c853 !important;
            box-shadow: 0 0 0 2px rgba(0, 200, 83, 0.25) !important;
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
            background-color: #0d1b22 !important;
            border-color: rgba(255, 255, 255, 0.1) !important;
            color: #f8fafc !important;
        }

        /* Dropdown options text color */
        li[role="option"] {
            color: #f8fafc !important;
            background-color: #0d1b22 !important;
            transition: background-color 0.15s ease !important;
        }
        li[role="option"]:hover,
        li[role="option"][aria-selected="true"] {
            background-color: #1e293b !important;
            color: #ffffff !important;
        }

        /* Target Date Picker calendar container styling */
        div[data-baseweb="calendar"] {
            background-color: #0d1b22 !important;
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
            background-color: #00c853 !important;
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
            background: linear-gradient(90deg, #00c853 0%, #00e676 100%) !important;
            color: #ffffff !important;
            border: none !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
            padding: 0.5rem 1rem !important;
            box-shadow: 0 4px 12px rgba(0, 200, 83, 0.3) !important;
            transition: all 0.2s ease-in-out !important;
            width: 100% !important;
        }
        [data-testid="stBaseButton-primary"] button:hover,
        button[data-testid="stBaseButton-primary"]:hover {
            background: linear-gradient(90deg, #00b24a 0%, #00c853 100%) !important;
            box-shadow: 0 6px 16px rgba(0, 200, 83, 0.4) !important;
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
            background-color: rgba(13, 27, 34, 0.25) !important;
            border: 1px solid rgba(255, 255, 255, 0.06) !important;
            border-radius: 12px !important;
        }
        [data-testid="stExpander"] summary {
            color: #f1f5f9 !important;
            font-weight: 600 !important;
        }

        /* Preformatted Text blocks (st.text) */
        pre, code, [data-testid="stText"] {
            background-color: #0d1b22 !important;
            color: #cbd5e1 !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            border-radius: 8px !important;
            padding: 1rem !important;
        }

        /* HTML Tables styling */
        table {
            background-color: #0d1b22 !important;
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
            background-color: #0d1b22 !important;
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
            --primary-color: #00c853 !important;
            --background-color: #f0f7f4 !important;
            --secondary-background-color: #ffffff !important;
            --text-color: #0f172a !important;
            font-family: 'Plus Jakarta Sans', sans-serif !important;
        }

        [data-testid="stHeader"] {
            background-color: rgba(240, 247, 244, 0.8) !important;
            backdrop-filter: blur(12px) !important;
            -webkit-backdrop-filter: blur(12px) !important;
            border-bottom: 1px solid rgba(15, 23, 42, 0.05) !important;
        }

        footer, [data-testid="stDecoration"] {
            display: none !important;
        }

        /* Page background colors - light mode */
        .stApp, [data-testid="stAppViewContainer"], section.main, .main {
            background-color: #f0f7f4 !important;
            background-image: 
                radial-gradient(at 0% 0%, rgba(0, 200, 83, 0.04) 0px, transparent 40%),
                radial-gradient(at 100% 100%, rgba(0, 210, 182, 0.03) 0px, transparent 40%) !important;
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
            padding: 2rem 3rem !important;
        }

        /* Dashboard Forms - Full Responsive Width */
        [data-testid="stForm"] {
            background-color: #ffffff !important;
            border: 1px solid rgba(15, 23, 42, 0.08) !important;
            border-radius: 16px !important;
            padding: 1.5rem !important;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05) !important;
            width: 100% !important;
            max-width: 100% !important;
            margin: 0 0 1.5rem 0 !important;
        }

        @media (max-width: 768px) {
            [data-testid="stBlockContainer"],
            .block-container {
                padding: 1.25rem 1rem !important;
            }
            [data-testid="stForm"] {
                padding: 1rem !important;
            }
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
            border-color: rgba(0, 200, 83, 0.3) !important;
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
            border-color: #00c853 !important;
            box-shadow: 0 0 0 2px rgba(0, 200, 83, 0.15) !important;
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
            background-color: #00c853 !important;
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
            background: linear-gradient(90deg, #00c853 0%, #00e676 100%) !important;
            color: #ffffff !important;
            border: none !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
            padding: 0.5rem 1rem !important;
            box-shadow: 0 4px 12px rgba(0, 200, 83, 0.2) !important;
            transition: all 0.2s ease-in-out !important;
            width: 100% !important;
        }
        [data-testid="stBaseButton-primary"] button:hover,
        button[data-testid="stBaseButton-primary"]:hover {
            background: linear-gradient(90deg, #00b24a 0%, #00c853 100%) !important;
            box-shadow: 0 6px 16px rgba(0, 200, 83, 0.3) !important;
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
        card_bg = "rgba(13, 27, 34, 0.45)"
        card_border = "rgba(255, 255, 255, 0.06)"
        text_val_color = "#f8fafc"
        badge_bg = "rgba(0, 200, 83, 0.15)"
        badge_border = "rgba(0, 200, 83, 0.25)"
        badge_text = "#69f0ae"
    else:
        card_bg = "#f1f5f9"
        card_border = "rgba(15, 23, 42, 0.08)"
        text_val_color = "#0f172a"
        badge_bg = "rgba(0, 200, 83, 0.1)"
        badge_border = "rgba(0, 200, 83, 0.2)"
        badge_text = "#00c853"

    opciones = ["Carga de Ventas", "Tickets Premiados", "Gestión de Gastos", "Gestión de Pagos", "Gestión Bancaria", "Reporte Diario", "Reporte por Rango", "Cierre Diario"]

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
    elif opcion == "Gestión Bancaria": modulo_gestion_bancaria(ag)
    elif opcion == "Reporte por Rango": modulo_reporte_rango(ag)
    elif opcion == "Tickets Premiados": modulo_premios_tickets(ag)
    elif opcion == "Cierre Diario": modulo_cierre_diario(ag)
    elif opcion == "Reporte Diario": modulo_reporte_diario(ag)
