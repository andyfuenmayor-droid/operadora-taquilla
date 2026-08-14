import streamlit as st
import pandas as pd
import time
import os
import urllib.parse
from utils import supabase, obtener_periodo_trabajo, obtener_whatsapp_agencia_local, obtener_pagos_locales_agencia, obtener_gastos_locales_agencia

from datetime import datetime, timedelta, timezone
from modulo_pizarra import modulo_pizarra

st.set_page_config(
    page_title="Taquilla POS",
    page_icon="assets/pos_icon.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

def obtener_hora_local():
    """Retorna la fecha y hora actual ajustada a la zona horaria local (UTC-4)."""
    return datetime.now(timezone(timedelta(hours=-4)))

try:
    headers = getattr(st.context, "headers", {}) or {}
    user_agent = str(headers.get("User-Agent", "") or headers.get("user-agent", "")).lower()
    if "ipad" in user_agent or ("android" in user_agent and "mobile" not in user_agent):
        st.session_state["dispositivo"] = "Tablet"
    elif any(word in user_agent for word in ["iphone", "android", "blackberry", "opera mini"]):
        st.session_state["dispositivo"] = "Teléfono"
    else:
        st.session_state["dispositivo"] = "Escritorio"
except Exception:
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

if "tema_oscuro" not in st.session_state:
    st.session_state.tema_oscuro = True

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
    /* 🟢 CONTROL Y BOTÓN DEL MENÚ LATERAL EN MÓVIL Y ESCRITORIO (STREAMLIT COMPATIBLE) 🟢 */
    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="stHeader"] button[aria-label*="sidebar" i],
    [data-testid="stHeader"] button[aria-label*="Sidebar" i],
    [data-testid="stSidebarCollapseButton"],
    button[data-testid="stSidebarCollapsedControl"] {
        display: flex !important;
        visibility: visible !important;
        opacity: 1 !important;
        z-index: 999999 !important;
        position: fixed !important;
        top: 10px !important;
        left: 10px !important;
        background-color: #0d1b22 !important;
        color: #ffffff !important;
        border: 1px solid rgba(0, 200, 83, 0.6) !important;
        border-radius: 8px !important;
        padding: 4px 8px !important;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.5) !important;
        pointer-events: auto !important;
    }

    [data-testid="collapsedControl"] svg,
    [data-testid="stSidebarCollapsedControl"] svg,
    [data-testid="stHeader"] button[aria-label*="sidebar" i] svg,
    [data-testid="stHeader"] button[aria-label*="Sidebar" i] svg,
    [data-testid="stSidebarCollapseButton"] svg {
        fill: #ffffff !important;
        color: #ffffff !important;
        stroke: #ffffff !important;
        width: 22px !important;
        height: 22px !important;
    }

    [data-testid="stHeader"] {
        background-color: transparent !important;
        z-index: 999990 !important;
        pointer-events: none !important;
    }
    [data-testid="stHeader"] * {
        pointer-events: auto !important;
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

def render_tarjetas_metricas(t_venta, t_comis, t_premios, t_gastos, t_pagos, t_saldo, t_pago_banco=None, solo_operativo=False, moneda="BS"):
    is_dark = st.session_state.get("tema_oscuro", True)
    bg_color = "rgba(30, 41, 59, 0.6)" if is_dark else "#f8fafc"
    border_color = "rgba(255, 255, 255, 0.08)" if is_dark else "#e2e8f0"
    title_color = "#94a3b8" if is_dark else "#64748b"
    val_color = "#f8fafc" if is_dark else "#0f172a"

    m_upper = str(moneda).strip().upper()
    sym = "Bs. " if m_upper == "BS" else ("$" if m_upper == "USD" else "COP$ ")

    if solo_operativo:
        saldo_op = t_venta - t_comis - t_premios
        items = [
            ("Ventas", f"{sym}{t_venta:,.2f}"),
            ("Comision", f"{sym}{t_comis:,.2f}"),
            ("Premios", f"{sym}{t_premios:,.2f}"),
            ("Saldo", f"{sym}{saldo_op:,.2f}"),
        ]
        cols = st.columns(4)
    elif t_pago_banco is not None:
        items = [
            ("Ventas", f"{sym}{t_venta:,.2f}"),
            ("Comision", f"{sym}{t_comis:,.2f}"),
            ("Premios", f"{sym}{t_premios:,.2f}"),
            ("Gastos", f"{sym}{t_gastos:,.2f}"),
            ("Pago Efectivo", f"{sym}{t_pagos:,.2f}"),
            ("Pagos Bancos", f"{sym}{t_pago_banco:,.2f}"),
            ("Saldo", f"{sym}{t_saldo:,.2f}"),
        ]
        cols = st.columns(7)
    else:
        items = [
            ("Ventas", f"{sym}{t_venta:,.2f}"),
            ("Comision", f"{sym}{t_comis:,.2f}"),
            ("Premios", f"{sym}{t_premios:,.2f}"),
            ("Gastos", f"{sym}{t_gastos:,.2f}"),
            ("Pagos", f"{sym}{t_pagos:,.2f}"),
            ("Saldo", f"{sym}{t_saldo:,.2f}"),
        ]
        cols = st.columns(6)

    for idx, (title, val) in enumerate(items):
        if title == "Saldo":
            val_num = (t_venta - t_comis - t_premios) if solo_operativo else t_saldo
            if val_num > 0:
                cur_val_color = "#34d399" if is_dark else "#16a34a"
            elif val_num < 0:
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

def cargar_datos_agencia_tabla(tabla, agencia_nombre, fecha=None, fecha_desde=None, fecha_hasta=None):
    """
    Carga registros de Supabase comprobando tanto 'agencia' como 'nombre_agency'
    y filtrando por fecha o rango de fechas.
    """
    try:
        q = supabase.table(tabla).select("*")
        if tabla != "pagos_semana":
            if fecha:
                q = q.eq("fecha", str(fecha))
            if fecha_desde:
                q = q.gte("fecha", str(fecha_desde))
            if fecha_hasta:
                q = q.lte("fecha", str(fecha_hasta))
            
        res = q.execute()
        df = pd.DataFrame(res.data or [])
        if df.empty:
            return df
            
        df.columns = [c.lower() for c in df.columns]
        ag_str = str(agencia_nombre).strip().upper()
        
        mask = pd.Series(False, index=df.index)
        found_col = False
        if "agencia" in df.columns:
            mask = mask | (df["agencia"].astype(str).str.strip().str.upper() == ag_str)
            found_col = True
        if "nombre_agency" in df.columns:
            mask = mask | (df["nombre_agency"].astype(str).str.strip().str.upper() == ag_str)
            found_col = True
            
        if found_col:
            df = df[mask]

        if tabla == "pagos_semana" and not df.empty and "fecha" in df.columns:
            fechas_str = df["fecha"].astype(str).str.slice(0, 10)
            if fecha_desde:
                df = df[fechas_str >= str(fecha_desde)]
            elif fecha:
                is_prem = pd.Series(False, index=df.index)
                if "tipo_pago" in df.columns:
                    is_prem = df["tipo_pago"].astype(str).str.upper().str.contains("PREMIO|PÉRDIDA|PERDIDA|ABONO|REPOSICION|REPOSICIÓN", regex=True)
                df = df[(fechas_str == str(fecha)) | is_prem]
            if fecha_hasta:
                df = df[fechas_str <= str(fecha_hasta)]

        return df
    except Exception as e:
        return pd.DataFrame()

def filtrar_df_por_cajero(df, target_cajero_id):
    """
    Filtra un DataFrame para incluir los registros del cajero indicado,
    coincidiendo por cajero_id, user_id, usuario o nombre, o incluyendo registros
    general de agencia sin cajero específico asignado o generados por Admin/Supervisor.
    """
    if df.empty or target_cajero_id is None:
        return df
    c_str = str(target_cajero_id).strip()
    if not c_str or c_str.lower() in ["none", "nan"]:
        return df

    # Identificadores de cajeros registrados
    cajeros_ids = set()
    try:
        res_u = supabase.table("taquilla_usuarios").select("id, usuario, nombre_cajero, rol").execute()
        for u in (res_u.data or []):
            if u.get("rol") == "cajero":
                for k in ["id", "usuario", "nombre_cajero"]:
                    val = str(u.get(k, "")).strip()
                    if val and val.lower() not in ["none", "nan", ""]:
                        cajeros_ids.add(val)
                        cajeros_ids.add(val.lower())
    except Exception:
        pass

    targets = {c_str, c_str.lower()}
    cajero_actual = st.session_state.get("cajero_actual", {})
    if str(cajero_actual.get("id")).strip() == c_str:
        for k in ["id", "usuario", "nombre"]:
            val = str(cajero_actual.get(k, "")).strip()
            if val and val.lower() not in ["none", "nan", ""]:
                targets.add(val)
                targets.add(val.lower())

    try:
        res_u = supabase.table("taquilla_usuarios").select("id, usuario, nombre_cajero").eq("id", c_str).execute()
        if res_u.data:
            u_info = res_u.data[0]
            for k in ["id", "usuario", "nombre_cajero"]:
                val = str(u_info.get(k, "")).strip()
                if val and val.lower() not in ["none", "nan", ""]:
                    targets.add(val)
                    targets.add(val.lower())
    except Exception:
        pass

    has_cajero = "cajero_id" in df.columns
    has_user = "user_id" in df.columns

    is_agency_payment = pd.Series(False, index=df.index)
    if "tipo_pago" in df.columns:
        is_agency_payment = df["tipo_pago"].astype(str).str.upper().str.contains("PREMIO|PÉRDIDA|PERDIDA|ABONO|REPOSICION|REPOSICIÓN|PAGO", regex=True)

    if not has_cajero and not has_user:
        return df

    c_col = df["cajero_id"].fillna("").astype(str).str.strip() if has_cajero else pd.Series("", index=df.index)
    u_col = df["user_id"].fillna("").astype(str).str.strip() if has_user else pd.Series("", index=df.index)

    c_unassigned = c_col.str.lower().isin(["", "none", "nan", "null", "<na>"])
    u_unassigned = u_col.str.lower().isin(["", "none", "nan", "null", "<na>"])

    is_matched = (c_col.isin(targets) | c_col.str.lower().isin(targets)) | (u_col.isin(targets) | u_col.str.lower().isin(targets))
    is_general = c_unassigned & u_unassigned
    
    # Registros creados por Admin/Supervisor
    is_admin_registered = (~c_col.isin(cajeros_ids) & ~c_col.str.lower().isin(cajeros_ids)) & (~u_col.isin(cajeros_ids) & ~u_col.str.lower().isin(cajeros_ids))

    mask = is_matched | is_general | is_agency_payment | is_admin_registered
    return df[mask]

def enriquecer_columna_cajero(df):
    """Añade o formatea la columna `cajero` traduciendo cajero_id/user_id al nombre del cajero."""
    if df.empty:
        return df
    df = df.copy()

    mapa_cajeros = {}
    try:
        res_u = supabase.table("taquilla_usuarios").select("id, usuario, nombre_cajero").execute()
        for u in (res_u.data or []):
            nom = u.get("nombre_cajero") or u.get("usuario") or ""
            if u.get("id"):
                mapa_cajeros[str(u["id"]).strip()] = nom
            if u.get("usuario"):
                mapa_cajeros[str(u["usuario"]).strip()] = nom
    except Exception:
        pass

    cajero_actual = st.session_state.get("cajero_actual", {})
    if cajero_actual.get("id"):
        nom_act = cajero_actual.get("nombre") or cajero_actual.get("usuario")
        if nom_act:
            mapa_cajeros[str(cajero_actual["id"]).strip()] = nom_act
            if cajero_actual.get("usuario"):
                mapa_cajeros[str(cajero_actual["usuario"]).strip()] = nom_act

    def resolver_cajero(row):
        for c in ["cajero", "nombre_cajero"]:
            val = str(row.get(c, "")).strip() if pd.notna(row.get(c)) else ""
            if val and val.lower() not in ["none", "nan", ""]:
                if len(val) == 36 and "-" in val:
                    if val in mapa_cajeros:
                        return mapa_cajeros[val]
                    return "AGENCIA"
                return val
        for c in ["cajero_id", "user_id", "usuario"]:
            val = str(row.get(c, "")).strip() if pd.notna(row.get(c)) else ""
            if val in mapa_cajeros:
                return mapa_cajeros[val]
            elif val and val.lower() not in ["none", "nan", ""]:
                if len(val) == 36 and "-" in val:
                    return "AGENCIA"
                return val
        return "AGENCIA"

    df["cajero"] = df.apply(resolver_cajero, axis=1)
    return df

def sincronizar_confirmaciones_pagos(df_p, df_pb=None, ag_nombre=None):
    """
    Sincroniza el estado 'confirmado' de df_p cruzando con df_pb (cda_pagos_bancarios).
    Cualquier pago en df_p cuya referencia (Ref: XXXX) aparezca confirmada en cda_pagos_bancarios
    (o presente en la tabla bancaria como confirmada) actualizará su estado a confirmado = True.
    """
    if df_p.empty:
        return df_p

    df_p = df_p.copy()
    if "confirmado" not in df_p.columns:
        df_p["confirmado"] = False

    if df_pb is None or (isinstance(df_pb, pd.DataFrame) and df_pb.empty):
        try:
            q = supabase.table("cda_pagos_bancarios").select("referencia, confirmado")
            if ag_nombre:
                q = q.eq("agencia", ag_nombre)
            res_pb = q.execute()
            df_pb = pd.DataFrame(res_pb.data or [])
        except Exception:
            df_pb = pd.DataFrame()

    if df_pb is None or df_pb.empty:
        return df_p

    refs_confirmadas = set()
    for _, r in df_pb.iterrows():
        ref_val = str(r.get("referencia", "")).strip().upper()
        conf_val = bool(r.get("confirmado", True))
        if ref_val and conf_val:
            refs_confirmadas.add(ref_val)

    for idx, row in df_p.iterrows():
        tipo_str = str(row.get("tipo_pago", "")).upper()
        if "REF:" in tipo_str:
            partes = tipo_str.split("REF:")
            if len(partes) > 1:
                ref_pago = partes[1].replace(")", "").strip()
                if ref_pago in refs_confirmadas:
                    df_p.at[idx, "confirmado"] = True

    return df_p

def obtener_pagos_unificados(agencia_nombre, fecha=None, fecha_desde=None, fecha_hasta=None, cajero_id=None, es_supervisor=False):
    """
    Retorna tuple: (df_p_total, df_pb)
    """
    df_p = cargar_datos_agencia_tabla("cda_pagos_diarios", agencia_nombre, fecha=fecha, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta)
    df_pb = cargar_datos_agencia_tabla("cda_pagos_bancarios", agencia_nombre, fecha=fecha, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta)
    df_ps = cargar_datos_agencia_tabla("pagos_semana", agencia_nombre, fecha=fecha, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta)

    if cajero_id:
        df_p = filtrar_df_por_cajero(df_p, cajero_id)
        df_pb = filtrar_df_por_cajero(df_pb, cajero_id)

    if not df_ps.empty:
        nuevas_ps_p = []
        nuevas_ps_pb = []
        for _, r_ps in df_ps.iterrows():
            monto_ps = float(r_ps.get("monto", 0))
            fecha_ps_str = str(r_ps.get("fecha", ""))[:10]
            tipo_ps = str(r_ps.get("tipo_pago", "Pago")).strip()
            metodo_ps = str(r_ps.get("metodo", "EFECTIVO")).strip().upper()
            ref_ps = str(r_ps.get("referencia", "")).strip()

            ya_existe_p = False
            if not df_p.empty and "monto" in df_p.columns:
                fechas_p = df_p["fecha"].astype(str).str.slice(0, 10)
                coincides = df_p[
                    (fechas_p == fecha_ps_str) & 
                    (abs(df_p["monto"].astype(float) - monto_ps) < 0.01)
                ]
                if not coincides.empty:
                    ya_existe_p = True

            if not ya_existe_p:
                tipo_final = tipo_ps
                if metodo_ps == "BANCO":
                    ref_t = ref_ps if ref_ps else "BANCO"
                    if "ref" not in tipo_ps.lower():
                        tipo_final = f"{tipo_ps} - BANCO (Ref: {ref_t})"
                
                nuevas_ps_p.append({
                    "fecha": fecha_ps_str,
                    "agencia": agencia_nombre,
                    "nombre_agency": agencia_nombre,
                    "tipo_pago": tipo_final,
                    "monto": monto_ps,
                    "moneda": r_ps.get("moneda", "BS"),
                    "referencia": ref_ps,
                    "user_id": r_ps.get("user_id"),
                    "confirmado": True
                })

            is_prem_ps = any(k in tipo_ps.upper() for k in ["PREMIO", "PÉRDIDA", "PERDIDA", "ABONO", "REPOSICION", "REPOSICIÓN"])
            if metodo_ps == "BANCO" and not is_prem_ps:
                ya_existe_pb = False
                if not df_pb.empty and "monto" in df_pb.columns:
                    fechas_pb = df_pb["fecha"].astype(str).str.slice(0, 10)
                    coincides_pb = df_pb[
                        (fechas_pb == fecha_ps_str) & 
                        (abs(df_pb["monto"].astype(float) - monto_ps) < 0.01)
                    ]
                    if not coincides_pb.empty:
                        ya_existe_pb = True
                
                if not ya_existe_pb:
                    nuevas_ps_pb.append({
                        "fecha": fecha_ps_str,
                        "agencia": agencia_nombre,
                        "metodo_pago": "BANCO",
                        "monto": monto_ps,
                        "moneda": r_ps.get("moneda", "COP"),
                        "referencia": ref_ps,
                        "concepto": tipo_ps,
                        "datos_pagador": ref_ps,
                        "pos_o_cuenta": ref_ps,
                        "user_id": r_ps.get("user_id"),
                        "confirmado": True
                    })

        if nuevas_ps_p:
            df_p = pd.concat([df_p, pd.DataFrame(nuevas_ps_p)], ignore_index=True)
        if nuevas_ps_pb:
            df_pb = pd.concat([df_pb, pd.DataFrame(nuevas_ps_pb)], ignore_index=True)
        filas_banco = []
        for _, r in df_pb.iterrows():
            metodo = str(r.get("metodo_pago", "Pago Bancario")).strip()
            ref = str(r.get("referencia", "")).strip()
            tipo = f"{metodo} (Ref: {ref})" if ref else metodo
            filas_banco.append({
                "fecha": r.get("fecha"),
                "agencia": r.get("agencia"),
                "nombre_agency": r.get("nombre_agency"),
                "tipo_pago": tipo,
                "monto": float(r.get("monto", 0)),
                "moneda": r.get("moneda", "COP"),
                "cajero_id": r.get("cajero_id"),
                "user_id": r.get("user_id"),
                "confirmado": r.get("confirmado", False)
            })
        return pd.DataFrame(filas_banco), df_pb

    refs_existentes = set()
    if "tipo_pago" in df_p.columns:
        for val in df_p["tipo_pago"].dropna().astype(str):
            if "ref:" in val.lower():
                partes = val.lower().split("ref:")
                if len(partes) > 1:
                    ref_ext = partes[1].replace(")", "").strip()
                    if ref_ext:
                        refs_existentes.add(ref_ext.upper())

    nuevas_filas = []
    for _, r in df_pb.iterrows():
        ref_b = str(r.get("referencia", "")).strip().upper()
        if ref_b and ref_b in refs_existentes:
            continue
        
        metodo = str(r.get("metodo_pago", "Pago Bancario")).strip()
        tipo = f"{metodo} (Ref: {ref_b})" if ref_b else metodo
        monto_b = float(r.get("monto", 0))
        
        if not ref_b and not df_p.empty and "monto" in df_p.columns:
            coincide = df_p[
                (df_p["monto"].astype(float) == monto_b) & 
                (df_p["tipo_pago"].astype(str).str.contains(metodo, case=False, regex=False))
            ]
            if not coincide.empty:
                continue

        nuevas_filas.append({
            "fecha": r.get("fecha"),
            "agencia": r.get("agencia"),
            "nombre_agency": r.get("nombre_agency"),
            "tipo_pago": tipo,
            "monto": monto_b,
            "moneda": r.get("moneda", "COP"),
            "cajero_id": r.get("cajero_id"),
            "user_id": r.get("user_id"),
            "confirmado": r.get("confirmado", False)
        })

    if nuevas_filas:
        df_nuevas = pd.DataFrame(nuevas_filas)
        df_p = pd.concat([df_p, df_nuevas], ignore_index=True)

    df_p = sincronizar_confirmaciones_pagos(df_p, df_pb, agencia_nombre)
    return df_p, df_pb

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
        if cajero_id:
            res_c = supabase.table("cda_reportes_diarios")\
                .select("fecha")\
                .eq("nombre_agency", agencia_nombre)\
                .eq("cerrado", True)\
                .eq("cajero_id", str(cajero_id))\
                .order("fecha", desc=True)\
                .limit(1)\
                .execute()
            if res_c.data:
                return pd.to_datetime(res_c.data[0]["fecha"]).date()

        res_g = supabase.table("cda_reportes_diarios")\
            .select("fecha")\
            .eq("nombre_agency", agencia_nombre)\
            .eq("cerrado", True)\
            .order("fecha", desc=True)\
            .limit(1)\
            .execute()
        if res_g.data:
            return pd.to_datetime(res_g.data[0]["fecha"]).date()
    except Exception:
        pass
    return None

def obtener_fecha_inicial_operativa(agencia_nombre, cajero_id=None, u_id=None):
    """
    Retorna la fecha desde la cual se deben cargar los datos del periodo operativo.
    Si u_id se especifica (o para rol agencia/admin), consulta la fecha_desde del ciclo activo del admin en config_sistema.
    Si hay un último día cerrado posterior, retorna ultimo_dia_cerrado + 1 día.
    """
    f_desde_admin = None
    if u_id:
        try:
            ciclo = obtener_periodo_trabajo(u_id)
            if ciclo and ciclo.get("desde"):
                f_desde_admin = pd.to_datetime(ciclo["desde"]).date()
        except Exception:
            pass

    ult_cierre = obtener_ultimo_dia_cerrado(agencia_nombre, cajero_id=cajero_id)
    if ult_cierre:
        f_cierre_next = ult_cierre + timedelta(days=1)
        if f_desde_admin:
            return max(f_cierre_next, f_desde_admin)
        return f_cierre_next

    if f_desde_admin:
        return f_desde_admin
    
    fechas_encontradas = []
    for tabla in ["cda_reportes_diarios", "cda_gastos_diarios", "cda_pagos_diarios", "cda_premios_tickets", "pagos_semana"]:
        try:
            df = cargar_datos_agencia_tabla(tabla, agencia_nombre)
            if not df.empty and "fecha" in df.columns:
                f_min = df["fecha"].dropna().astype(str).str.slice(0, 10).min()
                if f_min and len(f_min) == 10:
                    fechas_encontradas.append(pd.to_datetime(f_min).date())
        except Exception:
            pass

    if fechas_encontradas:
        return min(fechas_encontradas)
    
    return datetime.now().date()

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
                "    cajero_id TEXT,\n"
                "    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,\n"
                "    UNIQUE(nombre_agency, fecha)\n"
                ");\n"
                "```"
            )
    return st.session_state["check_saldo_ok"]

def _check_cajero_id_cols():
    """Verifica que la columna `cajero_id` exista en cda_gastos_diarios, cda_pagos_diarios y cda_pagos_bancarios."""
    if "cajero_id_in_gastos" not in st.session_state:
        try:
            supabase.table("cda_gastos_diarios").select("cajero_id").limit(1).execute()
            st.session_state["cajero_id_in_gastos"] = True
        except Exception:
            st.session_state["cajero_id_in_gastos"] = False

    if "cajero_id_in_pagos" not in st.session_state:
        try:
            supabase.table("cda_pagos_diarios").select("cajero_id").limit(1).execute()
            st.session_state["cajero_id_in_pagos"] = True
        except Exception:
            st.session_state["cajero_id_in_pagos"] = False

    if "cajero_id_in_bancarios" not in st.session_state:
        try:
            supabase.table("cda_pagos_bancarios").select("cajero_id").limit(1).execute()
            st.session_state["cajero_id_in_bancarios"] = True
        except Exception:
            st.session_state["cajero_id_in_bancarios"] = False

    if not st.session_state["cajero_id_in_gastos"] or not st.session_state["cajero_id_in_pagos"] or not st.session_state["cajero_id_in_bancarios"]:
        st.warning(
            "⚠️ Las columnas para separar gastos/pagos por cajero no están totalmente creadas en Supabase.\n\n"
            "Ejecuta este SQL en el Editor SQL de Supabase para habilitar el registro por cajero:\n\n"
            "```sql\n"
            "ALTER TABLE cda_gastos_diarios ADD COLUMN IF NOT EXISTS cajero_id TEXT;\n"
            "ALTER TABLE cda_pagos_diarios ADD COLUMN IF NOT EXISTS cajero_id TEXT;\n"
            "ALTER TABLE cda_pagos_bancarios ADD COLUMN IF NOT EXISTS cajero_id TEXT;\n"
            "```"
        )
    return st.session_state["cajero_id_in_gastos"] and st.session_state["cajero_id_in_pagos"] and st.session_state["cajero_id_in_bancarios"]

def obtener_saldo_anterior(agencia_nombre, fecha_sel, cajero_id=None, moneda="BS"):
    """Retorna el saldo restante del último día cerrado anterior a fecha_sel o el saldo inicial de la moneda en agencias."""
    ag_str = str(agencia_nombre).strip()
    m_code = str(moneda).strip().lower()
    
    # 1. Buscar saldo específico por cajero en saldo_taquilla para la moneda requerida
    if cajero_id is not None:
        try:
            c_str = str(cajero_id).strip()
            if c_str and c_str.lower() not in ["none", "nan", ""]:
                res_c = supabase.table("saldo_taquilla")\
                    .select("saldo_restante")\
                    .ilike("nombre_agency", ag_str)\
                    .ilike("moneda", m_code)\
                    .eq("cajero_id", c_str)\
                    .lt("fecha", str(fecha_sel))\
                    .order("fecha", desc=True)\
                    .limit(1)\
                    .execute()
                if res_c.data:
                    return float(res_c.data[0]["saldo_restante"])
                try:
                    res_u = supabase.table("saldo_taquilla")\
                        .select("saldo_restante")\
                        .ilike("nombre_agency", ag_str)\
                        .ilike("moneda", m_code)\
                        .eq("user_id", c_str)\
                        .lt("fecha", str(fecha_sel))\
                        .order("fecha", desc=True)\
                        .limit(1)\
                        .execute()
                    if res_u.data:
                        return float(res_u.data[0]["saldo_restante"])
                except Exception:
                    pass
        except Exception:
            pass

    # 2. Buscar saldo general de agencia en saldo_taquilla para la última fecha cerrada y moneda requerida
    try:
        res_date = supabase.table("saldo_taquilla")\
            .select("fecha")\
            .ilike("nombre_agency", ag_str)\
            .ilike("moneda", m_code)\
            .lt("fecha", str(fecha_sel))\
            .order("fecha", desc=True)\
            .limit(1)\
            .execute()
        if res_date.data:
            latest_date = res_date.data[0]["fecha"]
            res_all = supabase.table("saldo_taquilla")\
                .select("saldo_restante")\
                .ilike("nombre_agency", ag_str)\
                .ilike("moneda", m_code)\
                .eq("fecha", latest_date)\
                .execute()
            if res_all.data:
                return sum(float(r["saldo_restante"]) for r in res_all.data)
    except Exception:
        pass

    # 3. Buscar el saldo inicial correspondiente a la moneda específica en la tabla agencias
    try:
        res_ag = supabase.table("agencias").select("*").ilike("nombre_agencia", ag_str).execute()
        if not res_ag.data:
            res_ag = supabase.table("agencias").select("*").execute()
            
        if res_ag.data:
            df_ag_tmp = pd.DataFrame(res_ag.data)
            df_ag_tmp.columns = [c.lower().strip() for c in df_ag_tmp.columns]
            m_ag = df_ag_tmp[df_ag_tmp["nombre_agencia"].astype(str).str.strip().str.upper() == ag_str.upper()]
            if not m_ag.empty:
                r_ag = m_ag.iloc[0]
                col_target = f"saldo_inicial_{m_code}"
                if col_target in r_ag and pd.notna(r_ag[col_target]):
                    try:
                        return float(r_ag[col_target])
                    except Exception:
                        pass
                if m_code == "bs":
                    for col_alt in ["saldo_inicial_bs", "saldo_inicial", "saldo_arrastre"]:
                        if col_alt in r_ag and pd.notna(r_ag[col_alt]):
                            try:
                                return float(r_ag[col_alt])
                            except Exception:
                                pass
    except Exception:
        pass

    return 0.0

def modulo_home(agencia_data):
    ag_nombre = agencia_data['nombre_agencia']
    u_id_admin = agencia_data.get('user_id')
    ciclo_admin = obtener_periodo_trabajo(u_id_admin)

    cajero_info = st.session_state.get("cajero_actual", {})
    nombre_user = (cajero_info.get("nombre") or cajero_info.get("usuario") or "USUARIO").upper()
    rol_user = str(cajero_info.get("rol") or "cajero").lower()
    cajero_id = cajero_info.get("id")
    es_supervisor = (rol_user == 'supervisor')
    es_agencia = (rol_user == 'agencia')
    es_sup_o_ag = es_supervisor or es_agencia

    fecha_hoy = datetime.now().date()
    str_hoy = str(fecha_hoy)

    c_id_target = None if es_sup_o_ag else cajero_id

    ult_cierre = obtener_ultimo_dia_cerrado(ag_nombre, cajero_id=c_id_target)
    fecha_operativa = obtener_fecha_inicial_operativa(ag_nombre, cajero_id=c_id_target, u_id=u_id_admin)
    str_operativa = str(fecha_operativa)

    saldo_anterior = obtener_saldo_anterior(ag_nombre, fecha_operativa, cajero_id=c_id_target)
    dia_cerrado_hoy = dia_esta_cerrado(ag_nombre, fecha_operativa, cajero_id=c_id_target)

    # Cargar métricas del periodo operativo actual desde el último cierre (gte fecha_operativa)
    df_v_hoy, df_g_hoy, df_p_hoy, df_pb_hoy, df_t_hoy = pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    f_desde_admin = str(ciclo_admin.get("desde"))
    f_hasta_admin = str(ciclo_admin.get("hasta"))

    try:
        df_v_hoy = cargar_datos_agencia_tabla("cda_reportes_diarios", ag_nombre, fecha_desde=str_operativa, fecha_hasta=f_hasta_admin)
        if df_v_hoy.empty or "monto_venta" not in df_v_hoy.columns or float(pd.to_numeric(df_v_hoy["monto_venta"], errors="coerce").fillna(0).sum()) == 0:
            df_ofic = cargar_datos_agencia_tabla("carga_actual", ag_nombre, fecha_desde=f_desde_admin, fecha_hasta=f_hasta_admin)
            if df_ofic.empty:
                df_ofic = cargar_datos_agencia_tabla("carga_actual", ag_nombre)
            if not df_ofic.empty:
                df_ofic["monto_venta"] = pd.to_numeric(df_ofic.get("venta", 0), errors="coerce").fillna(0.0)
                df_ofic["comision"] = pd.to_numeric(df_ofic.get("comision", 0), errors="coerce").fillna(0.0)
                df_ofic["monto_premios"] = pd.to_numeric(df_ofic.get("premios", 0), errors="coerce").fillna(0.0)
                df_ofic["neto"] = pd.to_numeric(df_ofic.get("neto", 0), errors="coerce").fillna(0.0)
                df_v_hoy = df_ofic

        df_g_hoy = cargar_datos_agencia_tabla("cda_gastos_diarios", ag_nombre, fecha_desde=str_operativa, fecha_hasta=f_hasta_admin)
        if df_g_hoy.empty or "monto" not in df_g_hoy.columns or float(pd.to_numeric(df_g_hoy["monto"], errors="coerce").fillna(0).sum()) == 0:
            df_g_ofic = cargar_datos_agencia_tabla("gastos", ag_nombre, fecha_desde=f_desde_admin, fecha_hasta=f_hasta_admin)
            if not df_g_ofic.empty:
                df_g_ofic["concepto"] = df_g_ofic.get("concepto", df_g_ofic.get("descripcion", "Gasto General"))
                df_g_hoy = df_g_ofic

        df_p_hoy, df_pb_hoy = obtener_pagos_unificados(ag_nombre, fecha_desde=str_operativa, fecha_hasta=f_hasta_admin, cajero_id=c_id_target, es_supervisor=es_sup_o_ag)
        if df_p_hoy.empty or "monto" not in df_p_hoy.columns or float(pd.to_numeric(df_p_hoy["monto"], errors="coerce").fillna(0).sum()) == 0:
            df_p_sem = cargar_datos_agencia_tabla("pagos_semana", ag_nombre, fecha_desde=f_desde_admin, fecha_hasta=f_hasta_admin)
            if df_p_sem.empty:
                df_p_sem = cargar_datos_agencia_tabla("pagos_semana", ag_nombre)
            if not df_p_sem.empty:
                df_p_sem["tipo_pago"] = df_p_sem.get("metodo", df_p_sem.get("tipo", df_p_sem.get("tipo_pago", "EFECTIVO")))
                df_p_hoy = df_p_sem

        if df_p_hoy.empty and not df_pb_hoy.empty:
            df_pb_tmp = df_pb_hoy.copy()
            df_pb_tmp["tipo_pago"] = df_pb_tmp.get("metodo_pago", df_pb_tmp.get("concepto", "PAGO BANCO"))
            df_p_hoy = df_pb_tmp

        loc_pagos = obtener_pagos_locales_agencia(u_id_admin, ag_nombre)
        if loc_pagos:
            df_p_loc = pd.DataFrame(loc_pagos)
            if "tipo_pago" not in df_p_loc.columns:
                df_p_loc["tipo_pago"] = df_p_loc.get("metodo", df_p_loc.get("tipo", "EFECTIVO"))
            df_p_hoy = pd.concat([df_p_hoy, df_p_loc], ignore_index=True) if not df_p_hoy.empty else df_p_loc

        loc_gastos = obtener_gastos_locales_agencia(u_id_admin, ag_nombre)
        if loc_gastos:
            df_g_loc = pd.DataFrame(loc_gastos)
            df_g_hoy = pd.concat([df_g_hoy, df_g_loc], ignore_index=True) if not df_g_hoy.empty else df_g_loc

        df_t_hoy = cargar_datos_agencia_tabla("cda_premios_tickets", ag_nombre, fecha_desde=str_operativa, fecha_hasta=f_hasta_admin)
    except Exception:
        pass

    df_v_raw = df_v_hoy.copy()
    df_g_raw = df_g_hoy.copy()
    df_p_raw = df_p_hoy.copy()
    df_pb_raw = df_pb_hoy.copy()
    df_t_raw = df_t_hoy.copy()

    # Multimoneda: Identificar monedas asociadas a la agencia y sus registros
    monedas_conf = [m.strip().upper() for m in str(agencia_data.get("monedas", "BS")).split(",") if m.strip()]
    monedas_data = df_v_raw["moneda"].astype(str).str.strip().str.upper().unique().tolist() if not df_v_raw.empty and "moneda" in df_v_raw.columns else []
    todas_monedas = [m for m in sorted(list(set(monedas_conf + monedas_data))) if m and m.lower() not in ["none", "nan", ""]]
    if not todas_monedas:
        todas_monedas = ["BS"]

    # BANNER PRINCIPAL DE BIENVENIDA
    badge_estado = '<span style="background-color: rgba(0, 200, 83, 0.2); color: #00c853; font-weight: 700; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; border: 1px solid rgba(0, 200, 83, 0.4);">🟢 DÍA OPERATIVO ABIERTO</span>' if not dia_cerrado_hoy else '<span style="background-color: rgba(244, 63, 94, 0.2); color: #f43f5e; font-weight: 700; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; border: 1px solid rgba(244, 63, 94, 0.4);">🔒 DÍA CERRADO</span>'

    ciclo_rango_str = f"{ciclo_admin.get('desde')} al {ciclo_admin.get('hasta')}"
    sem_no_str = ciclo_admin.get('semana', '')

    wa_home = str(agencia_data.get("telefono_whatsapp", agencia_data.get("telefono", ""))).strip()
    if not wa_home or wa_home.lower() in ["none", "nan"]:
        wa_home = obtener_whatsapp_agencia_local(u_id_admin, ag_nombre)
    wa_home_str = f" &bull; 📱 WhatsApp: <b style='color: #25D366;'>{wa_home}</b>" if wa_home and wa_home.lower() != "none" else ""

    st.markdown(
        f"""
        <div style="background: linear-gradient(135deg, rgba(11, 19, 37, 0.95) 0%, rgba(13, 27, 42, 0.95) 100%); border: 1px solid rgba(255, 255, 255, 0.08); padding: 1.25rem 1.5rem; border-radius: 16px; margin-bottom: 1.25rem; box-shadow: 0 8px 24px rgba(0,0,0,0.25);">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
                <div>
                    <h2 style="margin: 0; font-size: 1.5rem; font-weight: 800; color: #ffffff; letter-spacing: -0.02em;">
                        👋 ¡Bienvenido, {nombre_user}!
                    </h2>
                    <p style="margin: 0.25rem 0 0 0; font-size: 0.88rem; color: #94a3b8;">
                        Panel Principal &bull; 🏢 <b style="color: #f8fafc;">{ag_nombre}</b> &bull; 👤 Rol: <b style="color: #69f0ae;">{rol_user}</b>{wa_home_str}
                    </p>
                </div>
                <div style="text-align: right;">
                    {badge_estado}
                    <div style="font-size: 0.8rem; color: #64748b; margin-top: 0.35rem;">
                        📅 Día Operativo: <b>{str_operativa}</b> | Ciclo Admin (Sem. {sem_no_str}): {ciclo_rango_str}
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # GUÍA AUTOMÁTICA ASIGNADA POR ROL AL ENTRAR
    with st.expander(f"📖 Ver Guía Operativa Oficial — Rol {rol_user.upper()}", expanded=False):
        pdf_file_role = f"Guia_de_Uso_{rol_user.upper()}.pdf"
        pdf_p_home = os.path.join(os.path.dirname(__file__), pdf_file_role)
        if not os.path.exists(pdf_p_home):
            pdf_p_home = os.path.join(os.path.dirname(__file__), "Guia_de_Uso_Taquilla_Movil.pdf")
            
        st.markdown(f"##### 🎯 Manual de Instrucciones Asignado para el Rol: **{rol_user.upper()}**")
        if rol_user == "agencia":
            st.markdown("""
            - **Monitoreo de Ciclo:** Revisa tus ventas brutas, comisiones negociadas y saldo neto en `🏠 Inicio`.
            - **Libro de Cobranza:** Consulta saldos anteriores y balances finales en `📊 Reporte`.
            - **Registrar Abonos:** Registra tus pagos en efectivo en `💵 Pago Efectivo` o transferencias en `🏦 Gestión Bancaria`.
            """)
        elif rol_user == "supervisor":
            st.markdown("""
            - **Arqueo por Cajero:** Monitorea el balance de cada terminal en `⚙️ Gestión de Cierre por Cajero`.
            - **Recaudar Efectivo (Cajero ➔ Supervisor):** Presiona `🤝 Confirmar (Supervisor)` en `📌 Pizarra`.
            - **Entregar a Admin:** Usa `💸 Entregar al Administrador` para rendir la caja chica.
            """)
        else:
            st.markdown("""
            - **Registrar Ventas:** Ingrese ventas en `🎰 Carga de Ventas` y premios pagados.
            - **Registrar Gastos:** Reporte gastos de turno en `💸 Gestión de Gastos`.
            - **Rendir Turno:** Entregue su efectivo al supervisor y solicite el cierre en `🔒 Cierre Diario`.
            """)
            
        if os.path.exists(pdf_p_home):
            with open(pdf_p_home, "rb") as f_pdf_h:
                st.download_button(
                    label=f"📥 Descargar PDF Oficial de Operaciones ({rol_user.upper()})",
                    data=f_pdf_h.read(),
                    file_name=pdf_file_role,
                    mime="application/pdf",
                    use_container_width=True
                )

    # CREACIÓN DE ÁREAS INDEPENDIENTES POR MONEDA (UNA POR CADA MONEDA)
    if len(todas_monedas) > 1:
        tabs_m = st.tabs([f"💱 ÁREA OPERATIVA: {m}" for m in todas_monedas])
    else:
        tabs_m = [st.container()]

    for idx_m, m_code in enumerate(todas_monedas):
        with tabs_m[idx_m]:
            sym_curr = "Bs." if m_code == "BS" else ("$" if m_code == "USD" else "COP$")
            
            # Filtrar dataframes exclusivamente para la moneda m_code
            df_v_m = df_v_raw[df_v_raw["moneda"].astype(str).str.strip().str.upper() == m_code] if not df_v_raw.empty and "moneda" in df_v_raw.columns else pd.DataFrame()
            df_g_m = df_g_raw[df_g_raw["moneda"].astype(str).str.strip().str.upper() == m_code] if not df_g_raw.empty and "moneda" in df_g_raw.columns else pd.DataFrame()
            df_p_m = df_p_raw[df_p_raw["moneda"].astype(str).str.strip().str.upper() == m_code] if not df_p_raw.empty and "moneda" in df_p_raw.columns else pd.DataFrame()
            df_pb_m = df_pb_raw[df_pb_raw["moneda"].astype(str).str.strip().str.upper() == m_code] if not df_pb_raw.empty and "moneda" in df_pb_raw.columns else pd.DataFrame()
            df_t_m = df_t_raw[df_t_raw["moneda"].astype(str).str.strip().str.upper() == m_code] if not df_t_raw.empty and "moneda" in df_t_raw.columns else pd.DataFrame()

            if not es_sup_o_ag and cajero_id:
                df_v_m = filtrar_df_por_cajero(df_v_m, cajero_id)
                df_g_m = filtrar_df_por_cajero(df_g_m, cajero_id)
                df_p_m = filtrar_df_por_cajero(df_p_m, cajero_id)
                df_pb_m = filtrar_df_por_cajero(df_pb_m, cajero_id)
                df_t_m = filtrar_df_por_cajero(df_t_m, cajero_id)

            t_v_m = float(df_v_m["monto_venta"].sum()) if not df_v_m.empty and "monto_venta" in df_v_m.columns else 0.0
            t_c_m = float(df_v_m["comision"].sum()) if not df_v_m.empty and "comision" in df_v_m.columns else 0.0

            p_rep_m = float(df_v_m["monto_premios"].sum()) if not df_v_m.empty and "monto_premios" in df_v_m.columns else 0.0
            p_tick_m = float(df_t_m["monto"].sum()) if not df_t_m.empty and "monto" in df_t_m.columns else 0.0
            t_p_m = max(p_rep_m, p_tick_m)

            t_g_m = float(df_g_m["monto"].sum()) if not df_g_m.empty and "monto" in df_g_m.columns else 0.0

            t_pago_efectivo_m = 0.0
            t_pago_banco_diarios_m = 0.0
            t_pago_premios_m = 0.0

            if not df_p_m.empty:
                tipos_str_m = df_p_m["tipo_pago"].astype(str).str.upper() if "tipo_pago" in df_p_m.columns else pd.Series([""]*len(df_p_m))
                is_premio_m = tipos_str_m.str.contains("PREMIO|PÉRDIDA|PERDIDA|ABONO|REPOSICION|REPOSICIÓN", regex=True)
                t_pago_premios_m = float(df_p_m[is_premio_m]["monto"].sum())
                
                is_efectivo_m = tipos_str_m.str.contains("EFECTIVO") & (~is_premio_m)
                t_pago_efectivo_m = float(df_p_m[is_efectivo_m]["monto"].sum())
                
                is_banco_m = (~is_efectivo_m) & (~is_premio_m)
                t_pago_banco_diarios_m = float(df_p_m[is_banco_m]["monto"].sum())
            else:
                t_pago_efectivo_m = 0.0
                t_pago_banco_diarios_m = 0.0
                t_pago_premios_m = 0.0

            t_pago_banco_bancarios_m = float(df_pb_m["monto"].sum()) if not df_pb_m.empty and "monto" in df_pb_m.columns else 0.0
            t_pago_banco_m = max(t_pago_banco_diarios_m, t_pago_banco_bancarios_m)

            saldo_op_m = t_v_m - t_c_m - t_p_m
            saldo_neto_m = saldo_op_m - t_g_m - t_pago_efectivo_m - t_pago_banco_m + t_pago_premios_m
            saldo_ant_m = obtener_saldo_anterior(ag_nombre, fecha_operativa, cajero_id=c_id_target, moneda=m_code)
            saldo_fin_m = saldo_ant_m + saldo_neto_m

            # 1. RESUMEN OPERATIVO DE LA MONEDA
            render_titulo_seccion(f"📊 Resumen Operativo ({m_code}) - Ciclo Admin: {ciclo_rango_str}")
            render_tarjetas_metricas(t_v_m, t_c_m, t_p_m, t_g_m, t_pago_efectivo_m, saldo_neto_m, t_pago_banco=t_pago_banco_m, solo_operativo=True, moneda=m_code)

            # 2. BALANCE DE SALDO ACUMULADO DE LA MONEDA CON SU ARRASTRE
            cur_sf_color_m = '#34d399' if saldo_fin_m >= 0 else '#fb7185'
            st.markdown(
                f"""
                <div style="background-color: rgba(13, 27, 34, 0.5); padding: 0.85rem 1.25rem; border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.08); margin-top: 0.75rem; margin-bottom: 1.25rem; text-align: center; font-size: 0.85rem;">
                    <span style="color: #94a3b8;">Saldo Anterior ({m_code}):</span> <b style="color: #ffffff;">{sym_curr} {saldo_ant_m:,.2f}</b>
                    <span style="margin: 0 0.4rem; color: rgba(255,255,255,0.4);">+</span>
                    <span style="color: #94a3b8;">Resultado Hoy / Periodo:</span> <b style="color: {'#34d399' if saldo_op_m >= 0 else '#fb7185'};">{sym_curr} {saldo_op_m:,.2f}</b>
                    <span style="margin: 0 0.4rem; color: rgba(255,255,255,0.4);">-</span>
                    <span style="color: #94a3b8;">Gastos:</span> <b style="color: #ffffff;">{sym_curr} {t_g_m:,.2f}</b>
                    <span style="margin: 0 0.4rem; color: rgba(255,255,255,0.4);">-</span>
                    <span style="color: #94a3b8;">Pagos Bancos:</span> <b style="color: #ffffff;">{sym_curr} {t_pago_banco_m:,.2f}</b>
                    <span style="margin: 0 0.4rem; color: rgba(255,255,255,0.4);">-</span>
                    <span style="color: #94a3b8;">Pago Efectivo:</span> <b style="color: #ffffff;">{sym_curr} {t_pago_efectivo_m:,.2f}</b>
                    <span style="margin: 0 0.4rem; color: rgba(255,255,255,0.4);">+</span>
                    <span style="color: #94a3b8;">Pago Pérdidas / Premios:</span> <b style="color: #34d399;">{sym_curr} {t_pago_premios_m:,.2f}</b>
                    <span style="margin: 0 0.4rem; color: rgba(255,255,255,0.4);">=</span>
                    <span style="color: #94a3b8;">Saldo Actual ({m_code}):</span> <b style="font-size: 1.1rem; color: {cur_sf_color_m};">{sym_curr} {saldo_fin_m:,.2f}</b>
                </div>
                """,
                unsafe_allow_html=True
            )

            # 3. TABLAS DE ACTIVIDAD DE LA MONEDA
            col_t1, col_t2 = st.columns([1, 1])
            with col_t1:
                render_titulo_seccion(f"📋 Ventas del Ciclo - {m_code} ({ciclo_rango_str})")
                if not df_v_m.empty:
                    df_v_disp = df_v_m.copy()
                    if "monto_venta" in df_v_disp.columns and "venta" not in df_v_disp.columns:
                        df_v_disp = df_v_disp.rename(columns={"monto_venta": "venta"})
                    elif "monto_venta" in df_v_disp.columns and "venta" in df_v_disp.columns:
                        df_v_disp = df_v_disp.drop(columns=["monto_venta"])

                    if "monto_premios" in df_v_disp.columns and "premios" not in df_v_disp.columns:
                        df_v_disp = df_v_disp.rename(columns={"monto_premios": "premios"})
                    elif "monto_premios" in df_v_disp.columns and "premios" in df_v_disp.columns:
                        df_v_disp = df_v_disp.drop(columns=["monto_premios"])

                    desired_cols = ["sistema", "moneda", "venta", "comision", "premios", "neto"]
                    cols_v_show = [c for c in desired_cols if c in df_v_disp.columns]
                    df_v_disp = df_v_disp.loc[:, ~df_v_disp.columns.duplicated()][cols_v_show]

                    st.dataframe(
                        df_v_disp,
                        column_config={
                            "sistema": "Sistema",
                            "moneda": "Moneda",
                            "venta": st.column_config.NumberColumn("Venta", format="$%,.2f"),
                            "comision": st.column_config.NumberColumn("Comisión", format="$%,.2f"),
                            "premios": st.column_config.NumberColumn("Premios", format="$%,.2f"),
                            "neto": st.column_config.NumberColumn("Neto", format="$%,.2f"),
                        },
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info(f"ℹ️ Sin registros de ventas cargados en {m_code} para este ciclo.")

            with col_t2:
                render_titulo_seccion(f"💸 Gastos y Pagos del Ciclo - {m_code} ({ciclo_rango_str})")
                df_p_all_m = pd.DataFrame()
                if not df_p_m.empty:
                    df_p_all_m = df_p_m.copy()
                if not df_pb_m.empty:
                    df_pb_fmt_m = df_pb_m.copy()
                    if "tipo_pago" not in df_pb_fmt_m.columns:
                        df_pb_fmt_m["tipo_pago"] = df_pb_fmt_m.get("metodo_pago", df_pb_fmt_m.get("concepto", "PAGO BANCO"))
                    df_p_all_m = pd.concat([df_p_all_m, df_pb_fmt_m], ignore_index=True) if not df_p_all_m.empty else df_pb_fmt_m

                if not df_g_m.empty or not df_p_all_m.empty:
                    if not df_g_m.empty:
                        st.caption(f"💸 **Gastos Registrados ({m_code}):**")
                        df_g_disp = enriquecer_columna_cajero(df_g_m)
                        if "confirmado" in df_g_disp.columns:
                            df_g_disp["Conf."] = df_g_disp["confirmado"].apply(lambda c: "✅ C" if c else "⏳ Pendiente")
                        if "agencia" not in df_g_disp.columns and "nombre_agency" in df_g_disp.columns:
                            df_g_disp["agencia"] = df_g_disp["nombre_agency"]
                        elif "nombre_agency" in df_g_disp.columns:
                            df_g_disp["agencia"] = df_g_disp["agencia"].fillna(df_g_disp["nombre_agency"])
                        cols_g_show = [c for c in ["fecha", "agencia", "cajero", "concepto", "moneda", "monto", "Conf."] if c in df_g_disp.columns]
                        st.dataframe(
                            df_g_disp[cols_g_show],
                            column_config={"monto": st.column_config.NumberColumn("monto", format="$%,.2f")},
                            use_container_width=True,
                            hide_index=True
                        )
                    if not df_p_all_m.empty:
                        df_p_disp = sincronizar_confirmaciones_pagos(df_p_all_m, df_pb_m, ag_nombre)
                        df_p_disp = enriquecer_columna_cajero(df_p_disp)
                        if "confirmado" in df_p_disp.columns:
                            df_p_disp["Conf."] = df_p_disp["confirmado"].apply(lambda c: "✅ C" if c else "⏳ Pendiente")
                        if "agencia" not in df_p_disp.columns and "nombre_agency" in df_p_disp.columns:
                            df_p_disp["agencia"] = df_p_disp["nombre_agency"]
                        elif "nombre_agency" in df_p_disp.columns:
                            df_p_disp["agencia"] = df_p_disp["agencia"].fillna(df_p_disp["nombre_agency"])
                        if "tipo_pago" in df_p_disp.columns:
                            df_p_disp = df_p_disp.rename(columns={"tipo_pago": "pagos registrados", "referencia": "referencia / banco"})
                        cols_p_show = [c for c in ["fecha", "agencia", "cajero", "pagos registrados", "referencia / banco", "banco", "moneda", "monto", "Conf."] if c in df_p_disp.columns]
                        st.dataframe(
                            df_p_disp[cols_p_show],
                            column_config={"monto": st.column_config.NumberColumn("monto", format="$%,.2f")},
                            use_container_width=True,
                            hide_index=True
                        )
                else:
                    st.info(f"ℹ️ Sin gastos ni pagos registrados en {m_code} para esta fecha.")

    if es_supervisor:
        try:
            res_u = supabase.table("taquilla_usuarios").select("id, usuario, nombre_cajero, rol").execute()
            cajeros_list = [u for u in (res_u.data or []) if u.get("rol") == "cajero"]
        except Exception:
            cajeros_list = []

        if cajeros_list:
            render_titulo_seccion("⚙️ Gestión de Cierre por Cajero (Supervisor)")
            cols_c = st.columns(len(cajeros_list)) if len(cajeros_list) <= 4 else st.columns(3)
            for idx_c, c_usr in enumerate(cajeros_list):
                c_id_item = str(c_usr["id"])
                c_name_item = c_usr.get("nombre_cajero") or c_usr.get("usuario")
                c_closed_item = dia_esta_cerrado(ag_nombre, fecha_operativa, cajero_id=c_id_item)
                col_target = cols_c[idx_c % len(cols_c)]
                with col_target.container(border=True):
                    st.markdown(f"**👤 {c_name_item}**")

                    df_v_c = filtrar_df_por_cajero(df_v_raw, c_id_item)
                    df_g_c = filtrar_df_por_cajero(df_g_raw, c_id_item)
                    df_pg_c = filtrar_df_por_cajero(df_p_raw, c_id_item)
                    df_pb_c = filtrar_df_por_cajero(df_pb_raw, c_id_item)
                    df_t_c = filtrar_df_por_cajero(df_t_raw, c_id_item)

                    v_item = float(df_v_c["monto_venta"].sum()) if not df_v_c.empty and "monto_venta" in df_v_c.columns else 0.0
                    c_item = float(df_v_c["comision"].sum()) if not df_v_c.empty and "comision" in df_v_c.columns else 0.0
                    
                    p_rep_c = float(df_v_c["monto_premios"].sum()) if not df_v_c.empty and "monto_premios" in df_v_c.columns else 0.0
                    p_tick_c = float(df_t_c["monto"].sum()) if not df_t_c.empty and "monto" in df_t_c.columns else 0.0
                    p_item = max(p_rep_c, p_tick_c)

                    g_item = float(df_g_c["monto"].sum()) if not df_g_c.empty and "monto" in df_g_c.columns else 0.0

                    if not df_pg_c.empty:
                        is_efectivo_c = df_pg_c["tipo_pago"].astype(str).str.lower().str.contains("efectivo") if "tipo_pago" in df_pg_c.columns else pd.Series([True]*len(df_pg_c))
                        pg_efectivo_item = float(df_pg_c[is_efectivo_c]["monto"].sum()) if not df_pg_c.empty else 0.0
                        pg_banco_diarios_c = float(df_pg_c[~is_efectivo_c]["monto"].sum()) if not df_pg_c.empty else 0.0
                    else:
                        pg_efectivo_item = 0.0
                        pg_banco_diarios_c = 0.0

                    pg_banco_bancarios_c = float(df_pb_c["monto"].sum()) if not df_pb_c.empty and "monto" in df_pb_c.columns else 0.0
                    pg_banco_item = max(pg_banco_diarios_c, pg_banco_bancarios_c)

                    s_dia_item = v_item - c_item - p_item - g_item - pg_efectivo_item - pg_banco_item
                    s_ant_item = obtener_saldo_anterior(ag_nombre, fecha_operativa, cajero_id=c_id_item)
                    s_final_item = s_ant_item + s_dia_item

                    st.markdown(
                        f"""
                        <div style="background-color: rgba(255, 255, 255, 0.03); padding: 8px 12px; border-radius: 8px; margin-bottom: 0.8rem; border: 1px solid rgba(255, 255, 255, 0.05); font-size: 0.82rem;">
                            <div style="display: flex; justify-content: space-between;"><span>Saldo Anterior:</span> <b style="color: #94a3b8;">${s_ant_item:,.2f}</b></div>
                            <div style="display: flex; justify-content: space-between;"><span>Ventas:</span> <b>${v_item:,.2f}</b></div>
                            <div style="display: flex; justify-content: space-between;"><span>Comisión:</span> <b>${c_item:,.2f}</b></div>
                            <div style="display: flex; justify-content: space-between;"><span>Premios:</span> <b>${p_item:,.2f}</b></div>
                            <div style="display: flex; justify-content: space-between;"><span>Gastos:</span> <b>${g_item:,.2f}</b></div>
                            <div style="display: flex; justify-content: space-between;"><span>Pago Efectivo:</span> <b>${pg_efectivo_item:,.2f}</b></div>
                            <div style="display: flex; justify-content: space-between;"><span>Pagos Bancos / Puntos:</span> <b>${pg_banco_item:,.2f}</b></div>
                            <div style="display: flex; justify-content: space-between; border-top: 1px dashed rgba(255,255,255,0.1); padding-top: 4px; margin-top: 4px;"><span>Resultado Día:</span> <b style="color: {'#34d399' if s_dia_item >= 0 else '#ef4444'};">${s_dia_item:,.2f}</b></div>
                            <div style="display: flex; justify-content: space-between; border-top: 1px solid rgba(255,255,255,0.15); padding-top: 4px; margin-top: 4px;"><span>Saldo Actual:</span> <b style="color: #00c853; font-size: 0.88rem;">${s_final_item:,.2f}</b></div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                    if c_closed_item:
                        st.markdown(
                            f"""
                            <div style="background-color: rgba(52, 211, 153, 0.15); color: #34d399; font-weight: 700; padding: 6px 12px; border-radius: 8px; font-size: 0.85rem; border: 1px solid rgba(52, 211, 153, 0.3); text-align: center; margin-bottom: 0.8rem;">
                                🔒 CERRADO
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    else:
                        st.markdown(
                            f"""
                            <div style="background-color: rgba(239, 68, 68, 0.15); color: #ef4444; font-weight: 700; padding: 6px 12px; border-radius: 8px; font-size: 0.85rem; border: 1px solid rgba(239, 68, 68, 0.3); text-align: center; margin-bottom: 0.8rem;">
                                ⚠️ ALERTA: ABIERTO - {fecha_operativa.strftime('%Y-%m-%d')}
                            </div>
                            """,
                            unsafe_allow_html=True
                        )






# ? módulos de la taquilla ?
def modulo_registro_taquilla(agencia_data):
    render_encabezado_principal(f"🎰 Carga de Ventas: {agencia_data['nombre_agencia']}")
    cajero_info = st.session_state.get("cajero_actual", {})
    rol_usuario = cajero_info.get("rol", "cajero")
    cajero_id = cajero_info.get("id")
    es_supervisor = (rol_usuario == 'supervisor')
    sistemas_lista = [s.strip() for s in str(agencia_data.get("sistemas", "BETM3")).split(",")]

    ult_fecha = obtener_ultimo_dia_cerrado(agencia_data['nombre_agencia'], cajero_id=cajero_id if not es_supervisor else None)
    fecha_defecto = ult_fecha if ult_fecha else datetime.now().date()

    if "fecha_carga_actual" not in st.session_state or st.session_state.get("last_carga_cajero") != str(cajero_id):
        st.session_state["fecha_carga_actual"] = fecha_defecto
        st.session_state["last_carga_cajero"] = str(cajero_id)

    monedas_lista = [m.strip().upper() for m in str(agencia_data.get("monedas", "BS")).split(",") if m.strip()]
    moneda_def_ag = monedas_lista[0] if monedas_lista else "BS"

    col_f, col_m = st.columns([2, 2])
    with col_f:
        fecha_seleccionada = st.date_input(
            "📅 Seleccione el día a cargar:",
            value=st.session_state["fecha_carga_actual"],
            key="fecha_carga_input",
            on_change=lambda: setattr(st.session_state, 'fecha_carga_actual', st.session_state["fecha_carga_input"])
        )
    with col_m:
        if len(monedas_lista) > 1:
            moneda_sel = st.selectbox("💰 Moneda para esta carga:", monedas_lista, key=f"sel_mon_carga_{agencia_data['nombre_agencia']}")
        else:
            moneda_sel = moneda_def_ag
            st.markdown(f"<div style='margin-top: 24px; font-weight: 700; color: #38bdf8;'>💰 Moneda: {moneda_sel}</div>", unsafe_allow_html=True)

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
                        "moneda": moneda_sel,
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
    render_encabezado_principal("💸 Gastos Agencias")
    u_id = agencia_data['user_id']
    ag_nombre = agencia_data['nombre_agencia']
    cajero_info = st.session_state.get("cajero_actual", {})
    rol_usuario = str(cajero_info.get("rol", "cajero")).lower()
    cajero_id = cajero_info.get("id")
    es_supervisor = (rol_usuario == 'supervisor')
    es_agencia = (rol_usuario == 'agencia')

    cajeros_list = []
    map_cajeros = {}
    cajero_filtro_target = None

    ciclo_admin = obtener_periodo_trabajo(u_id)
    fecha_ciclo_hasta = None
    if ciclo_admin and ciclo_admin.get("hasta"):
        try:
            fecha_ciclo_hasta = pd.to_datetime(ciclo_admin["hasta"]).date()
        except Exception:
            pass

    if es_supervisor:
        try:
            res_u = supabase.table("taquilla_usuarios").select("id, usuario, nombre_cajero, rol").execute()
            cajeros_list = [u for u in (res_u.data or []) if u.get("rol") == "cajero"]
            map_cajeros = {str(c["id"]): c.get("nombre_cajero") or c.get("usuario") for c in cajeros_list}
        except Exception:
            cajeros_list = []

        col_f1, col_f2 = st.columns([2, 2])
        with col_f1:
            ult_fecha = obtener_ultimo_dia_cerrado(ag_nombre, cajero_id=None)
            fecha_defecto = fecha_ciclo_hasta if fecha_ciclo_hasta else (ult_fecha if ult_fecha else datetime.now().date())
            if "fecha_gasto_filtro" not in st.session_state or st.session_state.get("last_gasto_cajero") != str(cajero_id):
                st.session_state["fecha_gasto_filtro"] = fecha_defecto
                st.session_state["last_gasto_cajero"] = str(cajero_id)

            fecha_filtro = st.date_input(
                "📅 Ver gastos del día:",
                value=st.session_state["fecha_gasto_filtro"],
                key="fecha_gasto_filtro_input"
            )
        with col_f2:
            opts_sup = ["👥 TODOS LOS CAJEROS"] + [f"👤 {map_cajeros[str(c['id'])]}" for c in cajeros_list]
            sel_sup_label = st.selectbox("👤 Filtrar por Cajero:", opts_sup, key="gastos_sel_cajero_sup")
            if sel_sup_label != "👥 TODOS LOS CAJEROS":
                cname = sel_sup_label.replace("👤 ", "")
                cajero_filtro_target = next((str(c["id"]) for c in cajeros_list if (c.get("nombre_cajero") or c.get("usuario")) == cname), None)
    else:
        c_id_ref = None if es_agencia else cajero_id
        ult_fecha = obtener_ultimo_dia_cerrado(ag_nombre, cajero_id=c_id_ref)
        fecha_defecto = fecha_ciclo_hasta if fecha_ciclo_hasta else (ult_fecha if ult_fecha else datetime.now().date())
        if "fecha_gasto_filtro" not in st.session_state or st.session_state.get("last_gasto_cajero") != str(cajero_id):
            st.session_state["fecha_gasto_filtro"] = fecha_defecto
            st.session_state["last_gasto_cajero"] = str(cajero_id)

        col_f, _ = st.columns([2, 2])
        with col_f:
            fecha_filtro = st.date_input(
                "📅 Ver gastos del día:",
                value=st.session_state["fecha_gasto_filtro"],
                key="fecha_gasto_filtro_input"
            )

    c_target_id = cajero_filtro_target if es_supervisor else (None if es_agencia else cajero_id)

    cerrado = dia_esta_cerrado(ag_nombre, fecha_filtro, cajero_id=c_target_id)
    if cerrado:
        st.info(f"🔒 El día {fecha_filtro} está cerrado para este usuario. No se pueden registrar nuevos gastos.")

    try:
        df_g = cargar_datos_agencia_tabla("cda_gastos_diarios", ag_nombre, fecha=fecha_filtro)
        if c_target_id:
            df_g = filtrar_df_por_cajero(df_g, c_target_id)
    except Exception:
        df_g = pd.DataFrame()

    if not df_g.empty:
        render_titulo_seccion("📋 Gastos del Día")
        df_g_disp = enriquecer_columna_cajero(df_g)
        if "confirmado" in df_g_disp.columns:
            df_g_disp["Conf."] = df_g_disp["confirmado"].apply(lambda c: "✅ C" if c else "⏳ Pendiente")
        if "agencia" not in df_g_disp.columns and "nombre_agency" in df_g_disp.columns:
            df_g_disp["agencia"] = df_g_disp["nombre_agency"]
        elif "nombre_agency" in df_g_disp.columns:
            df_g_disp["agencia"] = df_g_disp["agencia"].fillna(df_g_disp["nombre_agency"])
        cols_g = ["fecha", "agencia", "cajero", "concepto", "moneda", "monto", "Conf."]
        cols_existentes = [c for c in cols_g if c in df_g_disp.columns]
        st.dataframe(
            df_g_disp[cols_existentes],
            column_config={
                "monto": st.column_config.NumberColumn("monto", format="$%,.2f")
            },
            use_container_width=True,
            hide_index=True
        )
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
                    gasto_data = {
                        "fecha": str(fecha_g), 
                        "agencia": ag_nombre,
                        "nombre_agency": ag_nombre,
                        "concepto": concepto_g.upper().strip(),
                        "monto": round(float(monto_g), 2),
                        "moneda": moneda_g, 
                        "user_id": u_id,
                        "confirmado": False
                    }
                    if st.session_state.get("cajero_id_in_gastos", False):
                        gasto_data["cajero_id"] = cajero_id
                    supabase.table("cda_gastos_diarios").insert(gasto_data).execute()
                    st.success("✅ Gasto guardado exitosamente!"); time.sleep(1); st.rerun()


def modulo_pagos(agencia_data):
    render_encabezado_principal("💵 Pago Efectivo")
    u_id = agencia_data['user_id']
    ag_nombre = agencia_data['nombre_agencia']
    cajero_info = st.session_state.get("cajero_actual", {})
    rol_usuario = str(cajero_info.get("rol", "cajero")).lower()
    cajero_id = cajero_info.get("id")
    es_supervisor = (rol_usuario == 'supervisor')
    es_agencia = (rol_usuario == 'agencia')

    cajeros_list = []
    map_cajeros = {}
    cajero_filtro_target = None

    if es_supervisor:
        try:
            res_u = supabase.table("taquilla_usuarios").select("id, usuario, nombre_cajero, rol").execute()
            cajeros_list = [u for u in (res_u.data or []) if u.get("rol") == "cajero"]
            map_cajeros = {str(c["id"]): c.get("nombre_cajero") or c.get("usuario") for c in cajeros_list}
        except Exception:
            cajeros_list = []

        col_f1, col_f2 = st.columns([2, 2])
        with col_f1:
            ult_fecha = obtener_ultimo_dia_cerrado(ag_nombre, cajero_id=None)
            fecha_defecto = ult_fecha if ult_fecha else datetime.now().date()
            if "fecha_pago_filtro" not in st.session_state or st.session_state.get("last_pago_cajero") != str(cajero_id):
                st.session_state["fecha_pago_filtro"] = fecha_defecto
                st.session_state["last_pago_cajero"] = str(cajero_id)

            fecha_filtro = st.date_input(
                "📅 Ver pagos del día:",
                value=st.session_state["fecha_pago_filtro"],
                key="fecha_pago_filtro_input"
            )
        with col_f2:
            opts_sup = ["👥 TODOS LOS CAJEROS"] + [f"👤 {map_cajeros[str(c['id'])]}" for c in cajeros_list]
            sel_sup_label = st.selectbox("👤 Filtrar por Cajero:", opts_sup, key="pagos_sel_cajero_sup")
            if sel_sup_label != "👥 TODOS LOS CAJEROS":
                cname = sel_sup_label.replace("👤 ", "")
                cajero_filtro_target = next((str(c["id"]) for c in cajeros_list if (c.get("nombre_cajero") or c.get("usuario")) == cname), None)
    else:
        c_id_ref = None if es_agencia else cajero_id
        ult_fecha = obtener_ultimo_dia_cerrado(ag_nombre, cajero_id=c_id_ref)
        fecha_defecto = ult_fecha if ult_fecha else datetime.now().date()
        if "fecha_pago_filtro" not in st.session_state or st.session_state.get("last_pago_cajero") != str(cajero_id):
            st.session_state["fecha_pago_filtro"] = fecha_defecto
            st.session_state["last_pago_cajero"] = str(cajero_id)

        col_f, _ = st.columns([2, 2])
        with col_f:
            fecha_filtro = st.date_input(
                "📅 Ver pagos del día:",
                value=st.session_state["fecha_pago_filtro"],
                key="fecha_pago_filtro_input"
            )

    c_target_id = cajero_filtro_target if es_supervisor else (None if es_agencia else cajero_id)

    cerrado = dia_esta_cerrado(ag_nombre, fecha_filtro, cajero_id=c_target_id)
    if cerrado:
        st.info(f"🔒 El día {fecha_filtro} está cerrado para este usuario. No se pueden registrar nuevos pagos.")

    try:
        df_p = cargar_datos_agencia_tabla("cda_pagos_diarios", ag_nombre, fecha=fecha_filtro)
        if c_target_id:
            df_p = filtrar_df_por_cajero(df_p, c_target_id)
    except Exception:
        df_p = pd.DataFrame()

    if not df_p.empty:
        render_titulo_seccion("📋 Pagos del Día")
        df_p_disp = sincronizar_confirmaciones_pagos(df_p, ag_nombre=ag_nombre)
        df_p_disp = enriquecer_columna_cajero(df_p_disp)
        if "confirmado" in df_p_disp.columns:
            df_p_disp["Conf."] = df_p_disp["confirmado"].apply(lambda c: "✅ C" if c else "⏳ Pendiente")
        if "agencia" not in df_p_disp.columns and "nombre_agency" in df_p_disp.columns:
            df_p_disp["agencia"] = df_p_disp["nombre_agency"]
        elif "nombre_agency" in df_p_disp.columns:
            df_p_disp["agencia"] = df_p_disp["agencia"].fillna(df_p_disp["nombre_agency"])
        df_p_disp = df_p_disp.rename(columns={"tipo_pago": "pagos registrados"})
        cols_p = ["fecha", "agencia", "cajero", "pagos registrados", "moneda", "monto", "Conf."]
        cols_p = [c for c in cols_p if c in df_p_disp.columns]
        st.dataframe(
            df_p_disp[cols_p],
            column_config={
                "monto": st.column_config.NumberColumn("monto", format="$%,.2f")
            },
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("ℹ️ No hay pagos en este día.")

    if not cerrado:
        with st.form("form_p", clear_on_submit=True):
            render_titulo_seccion("📝 Registrar Nuevo Pago")
            c1, c2, c3, c4 = st.columns([2, 2, 3, 3])
            fecha_pg = c1.date_input("Fecha", value=fecha_filtro)
            moneda_pg = c2.selectbox("Moneda", ["COP", "USD", "BS"], index=0)
            monto_pg = c3.number_input("Monto", min_value=0.0, format="%.2f")
            if es_agencia:
                opts_tipo_pg = ["Pago a Comercializador"]
            else:
                opts_tipo_pg = ["Efectivo (Entregado a Admin)", "Pago de Premios / Abono de Pérdida", "Abono / Reposición de Caja", "Pago a Comercializador"]
            tipo_pg = c4.selectbox("Tipo Pago / Concepto", opts_tipo_pg)
            if st.form_submit_button("💾 GUARDAR PAGO", use_container_width=True):
                if monto_pg <= 0:
                    st.error("Ingrese un monto válido mayor a cero.")
                else:
                    pago_data = {
                        "fecha": str(fecha_pg), 
                        "agencia": ag_nombre,
                        "nombre_agency": ag_nombre,
                        "tipo_pago": tipo_pg, 
                        "monto": round(float(monto_pg), 2),
                        "moneda": moneda_pg, 
                        "user_id": u_id,
                        "confirmado": False,
                        "confirmado_supervisor": False
                    }
                    if st.session_state.get("cajero_id_in_pagos", False) or cajero_id:
                        pago_data["cajero_id"] = cajero_id
                    supabase.table("cda_pagos_diarios").insert(pago_data).execute()
                    st.success("✅ Pago guardado exitosamente!")
                    time.sleep(1)
                    st.rerun()


def modulo_gestion_bancaria(agencia_data):
    render_encabezado_principal("🏛️ Gestión Bancaria")
    render_subtitulo_terminal(agencia_data['nombre_agencia'])
    u_id = str(agencia_data['user_id']).strip()
    ag_nombre = str(agencia_data['nombre_agencia']).strip()

    if "bancaria_form_version" not in st.session_state:
        st.session_state["bancaria_form_version"] = 0

    cajero_info_b = st.session_state.get("cajero_actual", {})
    rol_usuario_b = str(cajero_info_b.get("rol", "cajero")).lower()
    cajero_id_b = cajero_info_b.get("id")
    es_supervisor_b = (rol_usuario_b == 'supervisor')
    es_agencia_b = (rol_usuario_b == 'agencia')

    c_id_ref = None if (es_agencia_b or es_supervisor_b) else cajero_id_b
    ult_fecha = obtener_ultimo_dia_cerrado(ag_nombre, cajero_id=c_id_ref)
    fecha_defecto = ult_fecha if ult_fecha else datetime.now().date()

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

    # Construcción dinámica de pestañas según disponibilidad de cuentas y dispositivos
    tabs_config = []
    if not df_cuentas.empty:
        tabs_config.append(("cuentas", "🏦 Cuentas Bancarias"))
    if not df_dispositivos.empty:
        tabs_config.append(("dispositivos", "📟 Dispositivos de Pago (POS / Biopago)"))
    tabs_config.append(("registrar", "💸 Registrar Pago"))
    tabs_config.append(("historial", "📊 Historial y Resumen"))

    tab_objects = st.tabs([t[1] for t in tabs_config])
    tabs_map = {t[0]: tab_objects[i] for i, t in enumerate(tabs_config)}

    # ==================== TAB 1: CUENTAS BANCARIAS ====================
    if "cuentas" in tabs_map:
        with tabs_map["cuentas"]:
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
    if "dispositivos" in tabs_map:
        with tabs_map["dispositivos"]:
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
    with tabs_map["registrar"]:
        render_titulo_seccion("💸 Registrar Pago Recibido")

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
        fecha_pago = col_top1.date_input("Fecha de Operación", value=fecha_defecto, key="reg_fecha_pago")
        pos_o_cuenta = col_top2.selectbox("Seleccione Dispositivo / Cuenta de Pago Asignado*", lista_opciones_destino, key="reg_destino_unificado")

        cerrado = dia_esta_cerrado(ag_nombre, fecha_pago, cajero_id=c_id_ref)
        if cerrado:
            st.info(f"🔒 El día {fecha_pago} está cerrado para este usuario. No se pueden registrar nuevos pagos.")

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
        monto_pago = col_v1.number_input("Monto Recibido*", min_value=0.0, format="%.2f", key=f"reg_monto_pago_{st.session_state.bancaria_form_version}")
        rol_actual_b = str(st.session_state.get("cajero_actual", {}).get("rol", "")).lower()
        if rol_actual_b == "agencia":
            opts_concepto = ["Pago a Comercializador"]
        else:
            opts_concepto = ["Compra de Tickets", "Pago de Premios", "Recibos Punto Venta", "Pago a Comercializador"]
        concepto = col_v2.selectbox("Concepto de Operación*", opts_concepto, key="reg_concepto_pago")

        # Campos dinámicos según el concepto seleccionado
        if concepto in ["Compra de Tickets", "Pago de Premios", "Pago a Comercializador"]:
            col_f1, col_f2 = st.columns([3, 3])
            referencia = col_f1.text_input("Número de Referencia / Comprobante*", placeholder="Ej: 987654 / Últimos 6 dígitos", key=f"reg_ref_pago_{st.session_state.bancaria_form_version}")
            datos_cliente = col_f2.text_input("Datos del Pagador / Titular", placeholder="Ej: V-14567890 / Pedro Pérez", key=f"reg_datos_cliente_{st.session_state.bancaria_form_version}")
        else:
            referencia = st.text_input("Número de Referencia / Comprobante*", placeholder="Ej: 987654 / Últimos 6 dígitos", key=f"reg_ref_pago_{st.session_state.bancaria_form_version}")
            datos_cliente = ""

        # Botón de envío
        if st.button("💾 REGISTRAR PAGO BANCARIO", use_container_width=True, type="primary", disabled=cerrado):
            if cerrado:
                st.error(f"🔒 El día {fecha_pago} está cerrado para este usuario. No se pueden registrar nuevos pagos.")
            elif monto_pago <= 0:
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
                        "confirmado": False,
                        "created_at": datetime.now().isoformat()
                    }
                    if st.session_state.get("cajero_id_in_bancarios", False) and cajero_id_b:
                        data_bancaria["cajero_id"] = cajero_id_b
                    supabase.table("cda_pagos_bancarios").insert(data_bancaria).execute()

                    st.success(f"✅ Pago por {metodo_pago} (Ref: {referencia}) registrado exitosamente!")
                    # Limpiar campos de entrada incrementando la versión del formulario
                    st.session_state["bancaria_form_version"] += 1
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar transacción: {e}")

    # ==================== TAB 4: HISTORIAL Y RESUMEN ====================
    with tabs_map["historial"]:
        render_titulo_seccion("📊 Historial de Transacciones Bancarias")

        c_f1, _ = st.columns([2, 2])
        fecha_hist = c_f1.date_input("📅 Filtrar por Fecha:", value=fecha_defecto, key="fecha_hist_bancaria")

        cajero_info_b = st.session_state.get("cajero_actual", {})
        rol_usuario_b = str(cajero_info_b.get("rol", "cajero")).lower()
        cajero_id_b = cajero_info_b.get("id")
        es_supervisor_b = (rol_usuario_b == 'supervisor')
        es_agencia_b = (rol_usuario_b == 'agencia')

        try:
            res_pb = supabase.table("cda_pagos_bancarios").select("*").eq("fecha", str(fecha_hist)).execute()
            df_pb = pd.DataFrame(res_pb.data or [])
            if not df_pb.empty:
                df_pb.columns = [c.lower() for c in df_pb.columns]
                if not es_supervisor_b and not es_agencia_b and cajero_id_b:
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
            if "confirmado" in df_pb.columns:
                df_pb["Conf."] = df_pb["confirmado"].apply(lambda c: "✅ C" if c else "⏳ Pendiente")
            cols_show_pb = [c for c in ["fecha", "metodo_pago", "monto", "moneda", "referencia", "pos_o_cuenta", "concepto", "datos_pagador", "Conf.", "created_at"] if c in df_pb.columns]
            st.dataframe(df_pb[cols_show_pb], use_container_width=True, hide_index=True)
        else:
            st.info(f"ℹ️ No hay transacciones bancarias registradas el día {fecha_hist}.")


def modulo_reporte_rango(agencia_data):
    render_encabezado_principal("📊 Reporte")
    render_subtitulo_terminal(agencia_data['nombre_agencia'])
    u_id = agencia_data['user_id']
    ciclo_admin = obtener_periodo_trabajo(u_id)
    hoy = datetime.now().date()
    default_desde = hoy
    default_hasta = hoy
    try:
        if ciclo_admin and ciclo_admin.get("desde"):
            default_desde = pd.to_datetime(ciclo_admin["desde"]).date()
        if ciclo_admin and ciclo_admin.get("hasta"):
            default_hasta = pd.to_datetime(ciclo_admin["hasta"]).date()
    except Exception:
        pass

    cajero_info = st.session_state.get("cajero_actual", {})
    rol_usuario = str(cajero_info.get("rol", "cajero")).lower()
    cajero_id = cajero_info.get("id")
    es_supervisor = (rol_usuario == 'supervisor')
    es_agencia = (rol_usuario == 'agencia')

    cajeros_list = []
    map_cajeros = {}
    cajero_filtro_target = None

    if es_supervisor:
        try:
            res_u = supabase.table("taquilla_usuarios").select("id, usuario, nombre_cajero, rol").execute()
            cajeros_list = [u for u in (res_u.data or []) if u.get("rol") == "cajero"]
            map_cajeros = {str(c["id"]): c.get("nombre_cajero") or c.get("usuario") for c in cajeros_list}
        except Exception:
            cajeros_list = []

        c1, c2, c3 = st.columns([2, 2, 3])
        d = c1.date_input("📅 Desde", value=default_desde, key="rango_fecha_desde")
        h = c2.date_input("📅 Hasta", value=default_hasta, key="rango_fecha_hasta")

        opts_sup = ["👥 TODOS LOS CAJEROS"] + [f"👤 {map_cajeros[str(c['id'])]}" for c in cajeros_list]
        sel_sup_label = c3.selectbox("👤 Filtrar por Cajero:", opts_sup, key="rango_sel_cajero_sup")
        if sel_sup_label != "👥 TODOS LOS CAJEROS":
            cname = sel_sup_label.replace("👤 ", "")
            cajero_filtro_target = next((str(c["id"]) for c in cajeros_list if (c.get("nombre_cajero") or c.get("usuario")) == cname), None)
    else:
        c1, c2 = st.columns(2)
        d = c1.date_input("📅 Desde", value=default_desde, key="rango_fecha_desde")
        h = c2.date_input("📅 Hasta", value=default_hasta, key="rango_fecha_hasta")

    if d > h:
        st.error("La fecha 'Desde' no puede ser mayor que 'Hasta'.")
        return

    c_target_id = cajero_filtro_target if es_supervisor else (None if es_agencia else cajero_id)

    try:
        df_v = cargar_datos_agencia_tabla("cda_reportes_diarios", agencia_data['nombre_agencia'], fecha_desde=d, fecha_hasta=h)
        if df_v.empty or "monto_venta" not in df_v.columns or float(pd.to_numeric(df_v["monto_venta"], errors="coerce").fillna(0).sum()) == 0:
            df_ofic = cargar_datos_agencia_tabla("carga_actual", agencia_data['nombre_agencia'], fecha_desde=d, fecha_hasta=h)
            if df_ofic.empty:
                df_ofic = cargar_datos_agencia_tabla("carga_actual", agencia_data['nombre_agencia'])
            if not df_ofic.empty:
                df_ofic["monto_venta"] = pd.to_numeric(df_ofic.get("venta", 0), errors="coerce").fillna(0.0)
                df_ofic["comision"] = pd.to_numeric(df_ofic.get("comision", 0), errors="coerce").fillna(0.0)
                df_ofic["monto_premios"] = pd.to_numeric(df_ofic.get("premios", 0), errors="coerce").fillna(0.0)
                df_ofic["neto"] = pd.to_numeric(df_ofic.get("neto", 0), errors="coerce").fillna(0.0)
                df_v = df_ofic

        df_g = cargar_datos_agencia_tabla("cda_gastos_diarios", agencia_data['nombre_agencia'], fecha_desde=d, fecha_hasta=h)
        if df_g.empty or "monto" not in df_g.columns or float(pd.to_numeric(df_g["monto"], errors="coerce").fillna(0).sum()) == 0:
            df_g_ofic = cargar_datos_agencia_tabla("gastos", agencia_data['nombre_agencia'], fecha_desde=d, fecha_hasta=h)
            if not df_g_ofic.empty:
                df_g_ofic["concepto"] = df_g_ofic.get("concepto", df_g_ofic.get("descripcion", "Gasto General"))
                df_g = df_g_ofic

        df_t = cargar_datos_agencia_tabla("cda_premios_tickets", agencia_data['nombre_agencia'], fecha_desde=d, fecha_hasta=h)

        if not df_v.empty and 'fecha' in df_v.columns: df_v['fecha'] = pd.to_datetime(df_v['fecha']).dt.date
        if not df_g.empty and 'fecha' in df_g.columns: df_g['fecha'] = pd.to_datetime(df_g['fecha']).dt.date
        if not df_t.empty and 'fecha' in df_t.columns: df_t['fecha'] = pd.to_datetime(df_t['fecha']).dt.date

        if c_target_id:
            df_v = filtrar_df_por_cajero(df_v, c_target_id)
            df_t = filtrar_df_por_cajero(df_t, c_target_id)
            df_g = filtrar_df_por_cajero(df_g, c_target_id)

        df_p, df_pb = obtener_pagos_unificados(
            agencia_data['nombre_agencia'],
            fecha_desde=d,
            fecha_hasta=h,
            cajero_id=c_target_id,
            es_supervisor=(not bool(c_target_id))
        )
        if not df_p.empty and 'fecha' in df_p.columns: df_p['fecha'] = pd.to_datetime(df_p['fecha']).dt.date
    except Exception as e:
        st.error(f"Error: {e}"); return

    # Multimoneda en Reporte
    monedas_conf = [m.strip().upper() for m in str(agencia_data.get("monedas", "BS")).split(",") if m.strip()]
    monedas_data = df_v["moneda"].astype(str).str.strip().str.upper().unique().tolist() if not df_v.empty and "moneda" in df_v.columns else []
    todas_monedas = [m for m in sorted(list(set(monedas_conf + monedas_data))) if m and m.lower() not in ["none", "nan", ""]]
    if not todas_monedas:
        todas_monedas = ["BS"]

    if len(todas_monedas) > 1:
        tabs_m = st.tabs([f"💱 REPORTES {m}" for m in todas_monedas])
    else:
        tabs_m = [st.container()]

    for idx_m, m_code in enumerate(todas_monedas):
        with tabs_m[idx_m]:
            sym_curr = "Bs." if m_code == "BS" else ("$" if m_code == "USD" else "COP$")
            
            df_v_m = df_v[df_v["moneda"].astype(str).str.strip().str.upper() == m_code] if not df_v.empty and "moneda" in df_v.columns else (df_v if len(todas_monedas) == 1 else pd.DataFrame())
            df_g_m = df_g[df_g["moneda"].astype(str).str.strip().str.upper() == m_code] if not df_g.empty and "moneda" in df_g.columns else (df_g if len(todas_monedas) == 1 else pd.DataFrame())
            df_p_m = df_p[df_p["moneda"].astype(str).str.strip().str.upper() == m_code] if not df_p.empty and "moneda" in df_p.columns else (df_p if len(todas_monedas) == 1 else pd.DataFrame())
            df_pb_m = df_pb[df_pb["moneda"].astype(str).str.strip().str.upper() == m_code] if not df_pb.empty and "moneda" in df_pb.columns else (df_pb if len(todas_monedas) == 1 else pd.DataFrame())

            render_titulo_seccion(f"📈 Resumen General ({m_code})")
            tv = float(df_v_m['monto_venta'].sum()) if not df_v_m.empty and 'monto_venta' in df_v_m.columns else 0.0
            tc = float(df_v_m['comision'].sum()) if not df_v_m.empty and 'comision' in df_v_m.columns else 0.0
            tp = float(df_v_m['monto_premios'].sum()) if not df_v_m.empty and 'monto_premios' in df_v_m.columns else 0.0
            tg = float(df_g_m['monto'].sum()) if not df_g_m.empty and 'monto' in df_g_m.columns else 0.0

            t_pago_efectivo_m = 0.0
            t_pago_banco_diarios_m = 0.0
            t_pago_premios_m = 0.0

            if not df_p_m.empty:
                tipos_str_m = df_p_m["tipo_pago"].astype(str).str.upper() if "tipo_pago" in df_p_m.columns else pd.Series([""]*len(df_p_m))
                is_premio_m = tipos_str_m.str.contains("PREMIO|PÉRDIDA|PERDIDA|ABONO|REPOSICION|REPOSICIÓN", regex=True)
                t_pago_premios_m = float(df_p_m[is_premio_m]["monto"].sum())
                
                is_efectivo_m = tipos_str_m.str.contains("EFECTIVO") & (~is_premio_m)
                t_pago_efectivo_m = float(df_p_m[is_efectivo_m]["monto"].sum())
                
                is_banco_m = (~is_efectivo_m) & (~is_premio_m)
                t_pago_banco_diarios_m = float(df_p_m[is_banco_m]["monto"].sum())
            else:
                t_pago_efectivo_m = 0.0
                t_pago_banco_diarios_m = 0.0
                t_pago_premios_m = 0.0

            t_pago_banco_bancarios_m = float(df_pb_m["monto"].sum()) if not df_pb_m.empty and "monto" in df_pb_m.columns else 0.0
            t_pago_banco_m = max(t_pago_banco_diarios_m, t_pago_banco_bancarios_m)

            saldo_op_m = tv - tc - tp
            saldo_neto_m = saldo_op_m - tg - t_pago_efectivo_m - t_pago_banco_m + t_pago_premios_m

            nom = agencia_data['nombre_agencia']
            saldo_ant = obtener_saldo_anterior(nom, d, cajero_id=c_target_id, moneda=m_code)
            t_saldo_final = saldo_ant + saldo_neto_m

            render_tarjetas_metricas(tv, tc, tp, tg, t_pago_efectivo_m, saldo_neto_m, t_pago_banco=t_pago_banco_m, solo_operativo=True, moneda=m_code)

            cur_sf_color_m = '#34d399' if t_saldo_final >= 0 else '#fb7185'
            st.markdown(
                f"""
                <div style="background-color: rgba(13, 27, 34, 0.5); padding: 0.85rem 1.25rem; border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.08); margin-top: 0.75rem; margin-bottom: 1.25rem; text-align: center; font-size: 0.85rem;">
                    <span style="color: #94a3b8;">Saldo Anterior ({m_code}):</span> <b style="color: #ffffff;">{sym_curr} {saldo_ant:,.2f}</b>
                    <span style="margin: 0 0.4rem; color: rgba(255,255,255,0.4);">+</span>
                    <span style="color: #94a3b8;">Resultado Hoy / Periodo:</span> <b style="color: {'#34d399' if saldo_op_m >= 0 else '#fb7185'};">{sym_curr} {saldo_op_m:,.2f}</b>
                    <span style="margin: 0 0.4rem; color: rgba(255,255,255,0.4);">-</span>
                    <span style="color: #94a3b8;">Gastos:</span> <b style="color: #ffffff;">{sym_curr} {tg:,.2f}</b>
                    <span style="margin: 0 0.4rem; color: rgba(255,255,255,0.4);">-</span>
                    <span style="color: #94a3b8;">Pagos Bancos:</span> <b style="color: #ffffff;">{sym_curr} {t_pago_banco_m:,.2f}</b>
                    <span style="margin: 0 0.4rem; color: rgba(255,255,255,0.4);">-</span>
                    <span style="color: #94a3b8;">Pago Efectivo:</span> <b style="color: #ffffff;">{sym_curr} {t_pago_efectivo_m:,.2f}</b>
                    <span style="margin: 0 0.4rem; color: rgba(255,255,255,0.4);">+</span>
                    <span style="color: #94a3b8;">Pago Pérdidas / Premios:</span> <b style="color: #34d399;">{sym_curr} {t_pago_premios_m:,.2f}</b>
                    <span style="margin: 0 0.4rem; color: rgba(255,255,255,0.4);">=</span>
                    <span style="color: #94a3b8;">Saldo Actual ({m_code}):</span> <b style="font-size: 1.1rem; color: {cur_sf_color_m};">{sym_curr} {t_saldo_final:,.2f}</b>
                </div>
                """,
                unsafe_allow_html=True
            )
            st.divider()

            render_titulo_seccion(f"📋 Detalle por Día ({m_code})")
            if not df_v_m.empty:
                cols = ["fecha", "sistema", "moneda", "monto_venta", "comision", "monto_premios"]
                cols = [c for c in cols if c in df_v_m.columns]
                df_v_disp = df_v_m[cols].sort_values(["fecha", "sistema"]).copy()
                df_v_disp = df_v_disp.rename(columns={"monto_venta": "venta", "monto_premios": "premios"})
                st.dataframe(
                    df_v_disp,
                    column_config={
                        "venta": st.column_config.NumberColumn("Venta", format="$%,.2f"),
                        "comision": st.column_config.NumberColumn("Comisión", format="$%,.2f"),
                        "premios": st.column_config.NumberColumn("Premios", format="$%,.2f"),
                    },
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info(f"Sin ventas registradas en {m_code}.")

            if not df_g_m.empty:
                with st.expander(f"💸 Gastos ({m_code})"):
                    df_g_disp = enriquecer_columna_cajero(df_g_m)
                    if "confirmado" in df_g_disp.columns:
                        df_g_disp["Conf."] = df_g_disp["confirmado"].apply(lambda c: "✅ C" if c else "⏳ Pendiente")
                    if "agencia" not in df_g_disp.columns and "nombre_agency" in df_g_disp.columns:
                        df_g_disp["agencia"] = df_g_disp["nombre_agency"]
                    elif "nombre_agency" in df_g_disp.columns:
                        df_g_disp["agencia"] = df_g_disp["agencia"].fillna(df_g_disp["nombre_agency"])
                    cols_g = ["agencia", "cajero", "concepto", "moneda", "monto", "Conf.", "fecha"]
                    cols_existentes = [c for c in cols_g if c in df_g_disp.columns]
                    st.dataframe(
                        df_g_disp[cols_existentes],
                        column_config={"monto": st.column_config.NumberColumn("monto", format="$%,.2f")},
                        use_container_width=True,
                        hide_index=True
                    )
            if not df_p_m.empty:
                with st.expander(f"💰 Pagos ({m_code})"):
                    df_p_disp = sincronizar_confirmaciones_pagos(df_p_m, df_pb_m, agencia_data['nombre_agencia'])
                    df_p_disp = enriquecer_columna_cajero(df_p_disp)
                    if "confirmado" in df_p_disp.columns:
                        df_p_disp["Conf."] = df_p_disp["confirmado"].apply(lambda c: "✅ C" if c else "⏳ Pendiente")
                    if "agencia" not in df_p_disp.columns and "nombre_agency" in df_p_disp.columns:
                        df_p_disp["agencia"] = df_p_disp["nombre_agency"]
                    elif "nombre_agency" in df_p_disp.columns:
                        df_p_disp["agencia"] = df_p_disp["agencia"].fillna(df_p_disp["nombre_agency"])
                    df_p_disp = df_p_disp.rename(columns={"tipo_pago": "pagos registrados"})
                    cols_p = ["agencia", "cajero", "pagos registrados", "moneda", "monto", "Conf.", "fecha"]
                    cols_existentes_p = [c for c in cols_p if c in df_p_disp.columns]
                    st.dataframe(
                        df_p_disp[cols_existentes_p],
                        column_config={"monto": st.column_config.NumberColumn("monto", format="$%,.2f")},
                        use_container_width=True,
                        hide_index=True
                    )

            def txt_rango_m():
                nom = agencia_data['nombre_agencia']
                lines = []
                lines.append("=" * 36)
                lines.append(f"  Reporte ({m_code}): {d} al {h}")
                lines.append(f"  {nom}")
                lines.append("=" * 36)
                if not df_v_m.empty:
                    for fe in sorted(df_v_m["fecha"].unique()):
                        lines.append(f"  --- {fe} ---")
                        df_dia = df_v_m[df_v_m["fecha"] == fe]
                        for _, r in df_dia.iterrows():
                            v_val = float(r.get('monto_venta', r.get('venta', 0)))
                            c_val = float(r.get('comision', 0))
                            p_val = float(r.get('monto_premios', r.get('premios', 0)))
                            lines.append(f"  {r.get('sistema', '')}")
                            lines.append(f"    Venta:    {sym_curr} {v_val:>10,.2f}")
                            lines.append(f"    Comisión: {sym_curr} {c_val:>10,.2f}")
                            lines.append(f"    Premios:  {sym_curr} {p_val:>10,.2f}")
                        lines.append("-" * 36)
                lines.append("=" * 36)
                lines.append(f"  TOTAL VENTAS:    {sym_curr} {tv:>10,.2f}")
                lines.append(f"  TOTAL COMISION:  {sym_curr} {tc:>10,.2f}")
                lines.append(f"  TOTAL PREMIOS:   {sym_curr} {tp:>10,.2f}")
                lines.append(f"  TOTAL GASTOS:    {sym_curr} {tg:>10,.2f}")
                lines.append(f"  PAGO EFECTIVO:   {sym_curr} {t_pago_efectivo_m:>10,.2f}")
                lines.append(f"  PAGOS BANCOS:    {sym_curr} {t_pago_banco_m:>10,.2f}")
                lines.append(f"  PAGO PREMIOS:    {sym_curr} {t_pago_premios_m:>10,.2f}")
                lines.append("-" * 36)
                lines.append(f"  SALDO PERIODO:   {sym_curr} {saldo_op_m:>10,.2f}")
                lines.append(f"  SALDO ANTERIOR:  {sym_curr} {saldo_ant:>10,.2f}")
                lines.append(f"  SALDO ACTUAL:    {sym_curr} {t_saldo_final:>10,.2f}")
                lines.append("=" * 36)
                lines.append("  Generado: " + obtener_hora_local().strftime("%Y-%m-%d %H:%M"))
                lines.append("=" * 36)
                return "\n".join(lines)

            txt_r = txt_rango_m()
            st.text_area(f"📄 Vista previa Reporte ({m_code})", txt_r, height=220, key=f"preview_reporte_{m_code}")
            wa_url = f"https://wa.me/?text={urllib.parse.quote(txt_r)}"
            st.link_button(f"📲 Compartir por WhatsApp ({m_code})", url=wa_url, use_container_width=True, key=f"wa_reporte_{m_code}")


def modulo_cierre_diario(agencia_data):
    render_encabezado_principal("🔒 Cierre Diario")
    u_id = agencia_data['user_id']
    nom = agencia_data['nombre_agencia']
    cajero_info = st.session_state.get("cajero_actual", {})
    cajero_id = cajero_info.get("id")
    es_supervisor = (cajero_info.get("rol", "") == "supervisor")

    ult_fecha = obtener_ultimo_dia_cerrado(nom, cajero_id=cajero_id if not es_supervisor else None)
    fecha_defecto = obtener_fecha_inicial_operativa(nom, cajero_id=cajero_id if not es_supervisor else None)

    if "fecha_cierre" not in st.session_state or st.session_state.get("last_cierre_cajero") != str(cajero_id):
        st.session_state["fecha_cierre"] = fecha_defecto
        st.session_state["last_cierre_cajero"] = str(cajero_id)

    col_f1, col_f2 = st.columns([2, 2])
    with col_f1:
        fecha_sel = st.date_input(
            "📅 Seleccione el día a cerrar:",
            value=st.session_state["fecha_cierre"],
            key="fecha_cierre_input"
        )

    cajeros_list = []
    map_cajeros = {}
    cajero_filtro_target = None

    if es_supervisor:
        try:
            res_u = supabase.table("taquilla_usuarios").select("id, usuario, nombre_cajero, rol").execute()
            cajeros_list = [u for u in (res_u.data or []) if u.get("rol") == "cajero"]
            map_cajeros = {str(c["id"]): c.get("nombre_cajero") or c.get("usuario") for c in cajeros_list}
        except Exception:
            cajeros_list = []

        with col_f2:
            opts_sup = ["👥 TODOS LOS CAJEROS"] + [f"👤 {map_cajeros[str(c['id'])]}" for c in cajeros_list]
            sel_sup_label = st.selectbox("👤 Filtrar por Cajero:", opts_sup, key="cierre_sel_cajero_sup")
            if sel_sup_label != "👥 TODOS LOS CAJEROS":
                cname = sel_sup_label.replace("👤 ", "")
                cajero_filtro_target = next((str(c["id"]) for c in cajeros_list if (c.get("nombre_cajero") or c.get("usuario")) == cname), None)

    c_target_id = cajero_filtro_target if es_supervisor else cajero_id
    cerrado = dia_esta_cerrado(nom, fecha_sel, cajero_id=c_target_id)

    # Cargar datos del día
    try:
        df_v = cargar_datos_agencia_tabla("cda_reportes_diarios", nom, fecha=fecha_sel)
        df_g = cargar_datos_agencia_tabla("cda_gastos_diarios", nom, fecha=fecha_sel)
        df_t = cargar_datos_agencia_tabla("cda_premios_tickets", nom, fecha=fecha_sel)

        df_v_raw = df_v.copy()
        df_g_raw = df_g.copy()
        df_t_raw = df_t.copy()

        if c_target_id:
            df_v = filtrar_df_por_cajero(df_v, c_target_id)
            df_g = filtrar_df_por_cajero(df_g, c_target_id)
            df_t = filtrar_df_por_cajero(df_t, c_target_id)

        df_pg, df_pb = obtener_pagos_unificados(
            nom,
            fecha=fecha_sel,
            cajero_id=c_target_id,
            es_supervisor=(not bool(c_target_id))
        )
        df_pg_raw = df_pg.copy()
        df_pb_raw = df_pb.copy()
    except Exception as e:
        st.error(f"Error: {e}"); return

    t_venta = float(df_v['monto_venta'].sum()) if not df_v.empty and 'monto_venta' in df_v.columns else 0.0
    t_comis = float(df_v['comision'].sum()) if not df_v.empty and 'comision' in df_v.columns else 0.0
    
    t_p_rep = float(df_v['monto_premios'].sum()) if not df_v.empty and 'monto_premios' in df_v.columns else 0.0
    t_p_tick = float(df_t['monto'].sum()) if not df_t.empty and 'monto' in df_t.columns else 0.0
    t_premios = max(t_p_rep, t_p_tick)
    t_gastos = float(df_g['monto'].sum()) if not df_g.empty and 'monto' in df_g.columns else 0.0

    pagos_entregados = 0.0
    abonos_recibidos = 0.0
    if not df_pg.empty and 'monto' in df_pg.columns:
        for _, r_pg in df_pg.iterrows():
            t_pg_tipo = str(r_pg.get("tipo_pago", "") or r_pg.get("metodo", "")).upper()
            m_pg = float(r_pg.get("monto", 0.0))
            if any(k in t_pg_tipo for k in ["PREMIO", "PREMIOS", "PERDIDA", "PÉRDIDA", "ABONO", "REPOSICION", "REPOSICIÓN", "ENTRADA"]):
                abonos_recibidos += m_pg
            else:
                pagos_entregados += m_pg

    t_pagos = pagos_entregados - abonos_recibidos
    t_saldo_dia = t_venta - t_comis - t_premios - t_gastos - t_pagos

    # Calcular Saldo Anterior y Saldo Final
    saldo_ant = obtener_saldo_anterior(nom, fecha_sel, cajero_id=c_target_id)
    t_saldo_final = saldo_ant + t_saldo_dia

    if cerrado:
        try:
            q_hoy = supabase.table("saldo_taquilla").select("saldo_restante").eq("nombre_agency", nom).eq("fecha", str(fecha_sel))
            if c_target_id:
                q_hoy = q_hoy.eq("cajero_id", str(c_target_id))
            res_hoy = q_hoy.execute()
            if res_hoy.data:
                t_saldo_final = sum(float(r["saldo_restante"]) for r in res_hoy.data)
        except Exception:
            pass

    titulo_resumen = f"📊 Resumen del {fecha_sel}"
    if es_supervisor and c_target_id:
        c_name_title = map_cajeros.get(str(c_target_id), f"ID {c_target_id}")
        titulo_resumen += f" - Cajero: {c_name_title}"

    saldo_operativo_dia = t_venta - t_comis - t_premios
    render_titulo_seccion(titulo_resumen)
    render_tarjetas_metricas(t_venta, t_comis, t_premios, t_gastos, t_pagos, t_saldo_dia, solo_operativo=True)

    st.markdown(
        f"""
        <div style="background-color: rgba(13, 27, 34, 0.4); padding: 0.85rem 1rem; border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.05); margin-top: 1rem; text-align: center; font-size: 0.85rem;">
            <span style="color: #94a3b8;">Saldo Anterior:</span> <b style="color: #ffffff;">${saldo_ant:,.2f}</b>
            <span style="margin: 0 0.4rem; color: rgba(255,255,255,0.4);">+</span>
            <span style="color: #94a3b8;">Resultado del Día:</span> <b style="color: {'#34d399' if saldo_operativo_dia >= 0 else '#fb7185'};">${saldo_operativo_dia:,.2f}</b>
            <span style="margin: 0 0.4rem; color: rgba(255,255,255,0.4);">-</span>
            <span style="color: #94a3b8;">Gastos:</span> <b style="color: #ffffff;">${t_gastos:,.2f}</b>
            <span style="margin: 0 0.4rem; color: rgba(255,255,255,0.4);">-</span>
            <span style="color: #94a3b8;">Pagos:</span> <b style="color: #ffffff;">${t_pagos:,.2f}</b>
            <span style="margin: 0 0.4rem; color: rgba(255,255,255,0.4);">=</span>
            <span style="color: #94a3b8;">Saldo Actual:</span> <b style="font-size: 1.1rem; color: #00c853;">${t_saldo_final:,.2f}</b>
        </div>
        """,
        unsafe_allow_html=True
    )

    if not df_v.empty:
        render_titulo_seccion("📋 Detalle por Sistema y Cajero")
        with st.expander("📋 Ver Detalle por Sistema y Cajero", expanded=True):
            try:
                if not map_cajeros:
                    res_u = supabase.table("taquilla_usuarios").select("id, usuario, nombre_cajero").execute()
                    map_cajeros = {str(u["id"]): u.get("nombre_cajero") or u.get("usuario") for u in (res_u.data or [])}
                df_v_display = df_v.copy()
                if "cajero_id" in df_v_display.columns:
                    df_v_display["cajero"] = df_v_display["cajero_id"].astype(str).map(lambda x: map_cajeros.get(x, f"ID {x}" if x != "None" and x != "nan" else "General"))
                    group_cols = ["sistema", "cajero"]
                else:
                    group_cols = ["sistema"]
                num_cols = [c for c in ["monto_venta", "comision", "monto_premios"] if c in df_v_display.columns]
                df_v_summary = df_v_display.groupby(group_cols, as_index=False)[num_cols].sum()
                df_v_summary = df_v_summary.rename(columns={"monto_venta": "venta", "monto_premios": "premios"})
                st.dataframe(
                    df_v_summary,
                    column_config={
                        "venta": st.column_config.NumberColumn("venta", format="$%,.2f"),
                        "comision": st.column_config.NumberColumn("comision", format="$%,.2f"),
                        "premios": st.column_config.NumberColumn("premios", format="$%,.2f"),
                    },
                    use_container_width=True,
                    hide_index=True
                )
            except Exception:
                num_cols = [c for c in ["monto_venta", "comision", "monto_premios"] if c in df_v.columns]
                df_v_summary = df_v.groupby("sistema", as_index=False)[num_cols].sum()
                df_v_summary = df_v_summary.rename(columns={"monto_venta": "venta", "monto_premios": "premios"})
                st.dataframe(
                    df_v_summary,
                    column_config={
                        "venta": st.column_config.NumberColumn("venta", format="$%,.2f"),
                        "comision": st.column_config.NumberColumn("comision", format="$%,.2f"),
                        "premios": st.column_config.NumberColumn("premios", format="$%,.2f"),
                    },
                    use_container_width=True,
                    hide_index=True
                )

    st.divider()

    if es_supervisor:
        render_titulo_seccion("⚙️ Gestión de Cierre por Cajero (Supervisor)")
        if cajeros_list:
            cols_c = st.columns(len(cajeros_list)) if len(cajeros_list) <= 4 else st.columns(3)
            for idx_c, c_usr in enumerate(cajeros_list):
                c_id_item = str(c_usr["id"])
                c_name_item = c_usr.get("nombre_cajero") or c_usr.get("usuario")
                c_closed_item = dia_esta_cerrado(nom, fecha_sel, cajero_id=c_id_item)
                col_target = cols_c[idx_c % len(cols_c)]
                with col_target.container(border=True):
                    st.markdown(f"**👤 {c_name_item}**")

                    df_v_c = filtrar_df_por_cajero(df_v_raw, c_id_item)
                    df_g_c = filtrar_df_por_cajero(df_g_raw, c_id_item)
                    df_pg_c = filtrar_df_por_cajero(df_pg_raw, c_id_item)
                    df_pb_c = filtrar_df_por_cajero(df_pb_raw, c_id_item)
                    df_t_c = filtrar_df_por_cajero(df_t_raw, c_id_item)

                    v_item = float(df_v_c["monto_venta"].sum()) if not df_v_c.empty and "monto_venta" in df_v_c.columns else 0.0
                    c_item = float(df_v_c["comision"].sum()) if not df_v_c.empty and "comision" in df_v_c.columns else 0.0
                    
                    p_rep_c = float(df_v_c["monto_premios"].sum()) if not df_v_c.empty and "monto_premios" in df_v_c.columns else 0.0
                    p_tick_c = float(df_t_c["monto"].sum()) if not df_t_c.empty and "monto" in df_t_c.columns else 0.0
                    p_item = max(p_rep_c, p_tick_c)

                    g_item = float(df_g_c["monto"].sum()) if not df_g_c.empty and "monto" in df_g_c.columns else 0.0

                    if not df_pg_c.empty:
                        is_efectivo = df_pg_c["tipo_pago"].astype(str).str.lower().str.contains("efectivo") if "tipo_pago" in df_pg_c.columns else pd.Series([True]*len(df_pg_c))
                        pg_efectivo_item = float(df_pg_c[is_efectivo]["monto"].sum()) if not df_pg_c.empty else 0.0
                        pg_banco_diarios = float(df_pg_c[~is_efectivo]["monto"].sum()) if not df_pg_c.empty else 0.0
                    else:
                        pg_efectivo_item = 0.0
                        pg_banco_diarios = 0.0

                    pg_banco_bancarios = float(df_pb_c["monto"].sum()) if not df_pb_c.empty and "monto" in df_pb_c.columns else 0.0
                    pg_banco_item = max(pg_banco_diarios, pg_banco_bancarios)

                    s_dia_item = v_item - c_item - p_item - g_item - pg_efectivo_item - pg_banco_item
                    s_ant_item = obtener_saldo_anterior(nom, fecha_sel, cajero_id=c_id_item)
                    s_final_item = s_ant_item + s_dia_item

                    st.markdown(
                        f"""
                        <div style="background-color: rgba(255, 255, 255, 0.03); padding: 8px 12px; border-radius: 8px; margin-bottom: 0.8rem; border: 1px solid rgba(255, 255, 255, 0.05); font-size: 0.82rem;">
                            <div style="display: flex; justify-content: space-between;"><span>Saldo Anterior:</span> <b style="color: #94a3b8;">${s_ant_item:,.2f}</b></div>
                            <div style="display: flex; justify-content: space-between;"><span>Ventas:</span> <b>${v_item:,.2f}</b></div>
                            <div style="display: flex; justify-content: space-between;"><span>Comisión:</span> <b>${c_item:,.2f}</b></div>
                            <div style="display: flex; justify-content: space-between;"><span>Premios:</span> <b>${p_item:,.2f}</b></div>
                            <div style="display: flex; justify-content: space-between;"><span>Gastos:</span> <b>${g_item:,.2f}</b></div>
                            <div style="display: flex; justify-content: space-between;"><span>Pago Efectivo:</span> <b>${pg_efectivo_item:,.2f}</b></div>
                            <div style="display: flex; justify-content: space-between;"><span>Pagos Bancos / Puntos:</span> <b>${pg_banco_item:,.2f}</b></div>
                            <div style="display: flex; justify-content: space-between; border-top: 1px dashed rgba(255,255,255,0.1); padding-top: 4px; margin-top: 4px;"><span>Resultado Día:</span> <b style="color: {'#34d399' if s_dia_item >= 0 else '#ef4444'};">${s_dia_item:,.2f}</b></div>
                            <div style="display: flex; justify-content: space-between; border-top: 1px solid rgba(255,255,255,0.15); padding-top: 4px; margin-top: 4px;"><span>Saldo Actual:</span> <b style="color: #00c853; font-size: 0.88rem;">${s_final_item:,.2f}</b></div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                    if c_closed_item:
                        st.markdown(
                            f"""
                            <div style="background-color: rgba(52, 211, 153, 0.15); color: #34d399; font-weight: 700; padding: 6px 12px; border-radius: 8px; font-size: 0.85rem; border: 1px solid rgba(52, 211, 153, 0.3); text-align: center; margin-bottom: 0.8rem;">
                                🔒 CERRADO - {fecha_sel}
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                        if st.button(f"🔓 Reabrir Día", key=f"btn_reabrir_{c_id_item}", use_container_width=True):
                            if reabrir_dia(nom, fecha_sel, cajero_id=c_id_item):
                                st.success(f"✅ Día reabierto para {c_name_item}.")
                                time.sleep(1); st.rerun()
                    else:
                        st.markdown(
                            f"""
                            <div style="background-color: rgba(239, 68, 68, 0.15); color: #ef4444; font-weight: 700; padding: 6px 12px; border-radius: 8px; font-size: 0.85rem; border: 1px solid rgba(239, 68, 68, 0.3); text-align: center; margin-bottom: 0.8rem;">
                                ⚠️ ALERTA: ABIERTO - {fecha_sel}
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                        if st.button(f"🔒 Cerrar Día", key=f"btn_cerrar_{c_id_item}", use_container_width=True):
                            if cerrar_dia(nom, fecha_sel, cajero_id=c_id_item):
                                try:
                                    t_v_c = v_item
                                    t_c_c = c_item
                                    t_p_c = p_item
                                    t_g_c = g_item
                                    t_pg_c = pg_efectivo_item + pg_banco_item
                                    
                                    s_ant_c = obtener_saldo_anterior(nom, fecha_sel, cajero_id=c_id_item)
                                    s_final_c = s_ant_c + (t_v_c - t_c_c - t_p_c - t_g_c - t_pg_c)
                                    p_saldo = {"nombre_agency": nom, "fecha": str(fecha_sel), "saldo_restante": s_final_c}
                                    if c_id_item:
                                        p_saldo["cajero_id"] = str(c_id_item)
                                    supabase.table("saldo_taquilla").upsert(p_saldo, on_conflict="nombre_agency,fecha,cajero_id").execute()
                                except Exception:
                                    pass
                                st.success(f"✅ Día cerrado para {c_name_item}.")
                                time.sleep(1); st.rerun()
    else:
        if cerrado:
            st.success(f"✅ Tu jornada del día {fecha_sel} está **CERRADA**.")
            st.info("ℹ️ Si requieres realizar modificaciones, solicita a tu supervisor que reabra tu jornada.")
        else:
            if df_v.empty and df_g.empty and df_pg.empty:
                st.info("ℹ️ No hay datos registrados para este día. Carga al menos una venta antes de cerrar.")
            else:
                if st.button("🔒 Cerrar Mi Día", type="primary", use_container_width=True):
                    if cerrar_dia(nom, fecha_sel, cajero_id):
                        try:
                            p_saldo = {"nombre_agency": nom, "fecha": str(fecha_sel), "saldo_restante": t_saldo_final}
                            if cajero_id:
                                p_saldo["cajero_id"] = str(cajero_id)
                            supabase.table("saldo_taquilla").upsert(p_saldo, on_conflict="nombre_agency,fecha,cajero_id").execute()
                            st.success("✅ Tu jornada fue cerrada y tu saldo guardado exitosamente.")
                        except Exception as e:
                            st.error(f"Error al guardar el saldo restante: {e}")
                        time.sleep(1); st.rerun()


def modulo_premios_tickets(agencia_data):
    render_encabezado_principal("🎟️ Tickets Premiados")
    rol_actual = str(st.session_state.get("cajero_actual", {}).get("rol", "cajero")).lower()
    es_supervisor = (rol_actual == "supervisor")
    u_id_real = str(st.session_state.get("cajero_actual", {}).get("id", agencia_data['user_id']))
    u_id_dueno = agencia_data['user_id']
    ag_nombre = agencia_data['nombre_agencia']

    if "premios_form_version" not in st.session_state:
        st.session_state["premios_form_version"] = 0

    ult_fecha = obtener_ultimo_dia_cerrado(ag_nombre, cajero_id=u_id_real if not es_supervisor else None)
    fecha_defecto = ult_fecha if ult_fecha else datetime.now().date()

    if "fecha_ticket_filtro" not in st.session_state or st.session_state.get("last_ticket_cajero") != str(u_id_real):
        st.session_state["fecha_ticket_filtro"] = fecha_defecto
        st.session_state["last_ticket_cajero"] = str(u_id_real)

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
        df_t_disp = enriquecer_columna_cajero(df_t)
        if "agencia" not in df_t_disp.columns and "nombre_agency" in df_t_disp.columns:
            df_t_disp["agencia"] = df_t_disp["nombre_agency"]
        elif "nombre_agency" in df_t_disp.columns:
            df_t_disp["agencia"] = df_t_disp["agencia"].fillna(df_t_disp["nombre_agency"])
        df_t_disp = df_t_disp.rename(columns={"numero_ticket": "numero ticket", "numero_tickets": "numero ticket"})
        cols_t = ["id", "agencia", "cajero", "sistema", "numero ticket", "monto", "estado", "fecha"]
        cols_t_show = [c for c in cols_t if c in df_t_disp.columns]
        st.dataframe(
            df_t_disp[cols_t_show],
            column_config={
                "monto": st.column_config.NumberColumn("monto", format="$%,.2f")
            },
            use_container_width=True,
            hide_index=True
        )
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
                    df_all_disp = enriquecer_columna_cajero(df_all)
                    if "agencia" not in df_all_disp.columns and "nombre_agency" in df_all_disp.columns:
                        df_all_disp["agencia"] = df_all_disp["nombre_agency"]
                    elif "nombre_agency" in df_all_disp.columns:
                        df_all_disp["agencia"] = df_all_disp["agencia"].fillna(df_all_disp["nombre_agency"])
                    df_all_disp = df_all_disp.rename(columns={"numero_ticket": "numero ticket", "numero_tickets": "numero ticket"})
                    cols_t = ["id", "agencia", "cajero", "sistema", "numero ticket", "monto", "estado", "fecha"]
                    cols_all_show = [c for c in cols_t if c in df_all_disp.columns]
                    st.dataframe(
                        df_all_disp[cols_all_show],
                        column_config={
                            "monto": st.column_config.NumberColumn("monto", format="$%,.2f")
                        },
                        use_container_width=True,
                        hide_index=True
                    )
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
                        d = cols[0].text_input(f"#{i+1}", key=f"dig_{i}_{st.session_state.premios_form_version}", max_chars=3, placeholder="000")
                        m = cols[2].number_input(f"Monto", min_value=0.0, format="%.2f", key=f"mon_lote_{i}_{st.session_state.premios_form_version}")
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
                                    moneda_prem_def = [m.strip().upper() for m in str(agencia_data.get("monedas", "BS")).split(",") if m.strip()][0] if agencia_data.get("monedas") else "BS"
                                    supabase.table("cda_reportes_diarios").insert({
                                        "nombre_agency": ag_nombre, "fecha": str(fecha_p),
                                        "sistema": sistema_p, "monto_venta": 0, "comision": 0,
                                        "monto_premios": monto_red, "neto": -monto_red,
                                        "moneda": moneda_prem_def, "user_id": agencia_data['user_id'],
                                        "cajero_id": u_id_real,
                                    }).execute()
                                ok_count += 1
                            except Exception as e:
                                errores.append(f"Ticket #{i+1}: {e}")
                        if ok_count:
                            st.success(f"✅ {ok_count} ticket(s) registrado(s).")
                            st.session_state["premios_form_version"] += 1
                        for e in errores:
                            st.warning(e)
                        if ok_count:
                            time.sleep(1); st.rerun()
                else:
                    st.info("📋 Modo *todos* — se registrarán N tickets con identificador TODOS")
                    monto_total = st.number_input("Monto Total", min_value=0.0, format="%.2f", key=f"monto_total_lote_{st.session_state.premios_form_version}")

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
                                    moneda_prem_def = [m.strip().upper() for m in str(agencia_data.get("monedas", "BS")).split(",") if m.strip()][0] if agencia_data.get("monedas") else "BS"
                                    supabase.table("cda_reportes_diarios").insert({
                                        "nombre_agency": ag_nombre, "fecha": str(fecha_p),
                                        "sistema": sistema_p, "monto_venta": 0, "comision": 0,
                                        "monto_premios": monto_total_red, "neto": -monto_total_red,
                                        "moneda": moneda_prem_def, "user_id": agencia_data['user_id'],
                                        "cajero_id": u_id_real,
                                    }).execute()
                            except Exception:
                                pass
                            if ok_count:
                                st.success(f"✅ {ok_count} ticket(s) TODOS registrados por ${monto_total:,.2f}.")
                                st.session_state["premios_form_version"] += 1
                            for e in errores:
                                st.warning(e)
                            if ok_count:
                                time.sleep(1); st.rerun()
            else:
                ticket = st.text_input("Número de Ticket", key=f"reg_ticket_num_{st.session_state.premios_form_version}").strip()
                monto_p = st.number_input("Monto del Premio", min_value=0.0, format="%.2f", key=f"reg_ticket_monto_{st.session_state.premios_form_version}")
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
                                        moneda_prem_def = [m.strip().upper() for m in str(agencia_data.get("monedas", "BS")).split(",") if m.strip()][0] if agencia_data.get("monedas") else "BS"
                                        supabase.table("cda_reportes_diarios").insert({
                                            "nombre_agency": ag_nombre, "fecha": str(fecha_p),
                                            "sistema": sistema_p, "monto_venta": 0, "comision": 0,
                                            "monto_premios": monto_redondeado, "neto": -monto_redondeado,
                                            "moneda": moneda_prem_def, "user_id": agencia_data['user_id'],
                                            "cajero_id": u_id_real,
                                        }).execute()
                                except Exception:
                                    pass
                                st.success("✅ Premio registrado.")
                                st.session_state["premios_form_version"] += 1
                                time.sleep(1); st.rerun()
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
    cajero_info = st.session_state.get("cajero_actual", {})
    rol_actual = str(cajero_info.get("rol", "cajero")).lower()
    cajero_id = cajero_info.get("id")
    es_supervisor = (rol_actual == "supervisor")
    es_agencia = (rol_actual == "agencia")

    cajeros_list = []
    map_cajeros = {}
    cajero_filtro_target = None

    if es_supervisor:
        try:
            res_u = supabase.table("taquilla_usuarios").select("id, usuario, nombre_cajero, rol").execute()
            cajeros_list = [u for u in (res_u.data or []) if u.get("rol") == "cajero"]
            map_cajeros = {str(c["id"]): c.get("nombre_cajero") or c.get("usuario") for c in cajeros_list}
        except Exception:
            cajeros_list = []

        col_f1, col_f2 = st.columns([2, 2])
        with col_f1:
            ult_fecha = obtener_ultimo_dia_cerrado(agencia_data['nombre_agencia'], cajero_id=None)
            fecha_defecto = ult_fecha if ult_fecha else datetime.now().date()
            if "fecha_reporte_dia" not in st.session_state or st.session_state.get("last_reporte_cajero") != str(cajero_id):
                st.session_state["fecha_reporte_dia"] = fecha_defecto
                st.session_state["last_reporte_cajero"] = str(cajero_id)

            fecha_sel = st.date_input(
                "📅 Seleccione el día:",
                value=st.session_state["fecha_reporte_dia"],
                key="fecha_reporte_dia_input"
            )
        with col_f2:
            opts_sup = ["👥 TODOS LOS CAJEROS"] + [f"👤 {map_cajeros[str(c['id'])]}" for c in cajeros_list]
            sel_sup_label = st.selectbox("👤 Filtrar por Cajero:", opts_sup, key="reporte_dia_sel_cajero_sup")
            if sel_sup_label != "👥 TODOS LOS CAJEROS":
                cname = sel_sup_label.replace("👤 ", "")
                cajero_filtro_target = next((str(c["id"]) for c in cajeros_list if (c.get("nombre_cajero") or c.get("usuario")) == cname), None)
    else:
        c_id_ref = None if es_agencia else cajero_id
        ult_fecha = obtener_ultimo_dia_cerrado(agencia_data['nombre_agencia'], cajero_id=c_id_ref)
        fecha_defecto = ult_fecha if ult_fecha else datetime.now().date()
        if "fecha_reporte_dia" not in st.session_state or st.session_state.get("last_reporte_cajero") != str(cajero_id):
            st.session_state["fecha_reporte_dia"] = fecha_defecto
            st.session_state["last_reporte_cajero"] = str(cajero_id)

        fecha_sel = st.date_input(
            "📅 Seleccione el día:",
            value=st.session_state["fecha_reporte_dia"],
            key="fecha_reporte_dia_input"
        )

    c_target_id = cajero_filtro_target if es_supervisor else cajero_id

    try:
        df_v = cargar_datos_agencia_tabla("cda_reportes_diarios", agencia_data['nombre_agencia'], fecha=fecha_sel)
        df_g = cargar_datos_agencia_tabla("cda_gastos_diarios", agencia_data['nombre_agencia'], fecha=fecha_sel)
        df_t = cargar_datos_agencia_tabla("cda_premios_tickets", agencia_data['nombre_agencia'], fecha=fecha_sel)

        if c_target_id:
            df_v = filtrar_df_por_cajero(df_v, c_target_id)
            df_t = filtrar_df_por_cajero(df_t, c_target_id)
            df_g = filtrar_df_por_cajero(df_g, c_target_id)

        df_p, df_pb = obtener_pagos_unificados(
            agencia_data['nombre_agencia'],
            fecha=fecha_sel,
            cajero_id=c_target_id,
            es_supervisor=(not bool(c_target_id))
        )
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
    saldo_ant = obtener_saldo_anterior(nom, fecha_sel, cajero_id=c_target_id)
    t_saldo_final = saldo_ant + t_saldo

    saldo_operativo = t_venta - t_comis - t_premios
    render_tarjetas_metricas(t_venta, t_comis, t_premios, t_gastos, t_pagos, t_saldo, solo_operativo=True)

    st.markdown(
        f"""
        <div style="background-color: rgba(13, 27, 34, 0.4); padding: 0.85rem 1rem; border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.05); margin-top: 1rem; text-align: center; font-size: 0.85rem;">
            <span style="color: #94a3b8;">Saldo Anterior:</span> <b style="color: #ffffff;">${saldo_ant:,.2f}</b>
            <span style="margin: 0 0.4rem; color: rgba(255,255,255,0.4);">+</span>
            <span style="color: #94a3b8;">Resultado del Día:</span> <b style="color: {'#34d399' if saldo_operativo >= 0 else '#fb7185'};">${saldo_operativo:,.2f}</b>
            <span style="margin: 0 0.4rem; color: rgba(255,255,255,0.4);">-</span>
            <span style="color: #94a3b8;">Gastos:</span> <b style="color: #ffffff;">${t_gastos:,.2f}</b>
            <span style="margin: 0 0.4rem; color: rgba(255,255,255,0.4);">-</span>
            <span style="color: #94a3b8;">Pagos:</span> <b style="color: #ffffff;">${t_pagos:,.2f}</b>
            <span style="margin: 0 0.4rem; color: rgba(255,255,255,0.4);">=</span>
            <span style="color: #94a3b8;">Saldo Actual:</span> <b style="font-size: 1.1rem; color: #00c853;">${t_saldo_final:,.2f}</b>
        </div>
        """,
        unsafe_allow_html=True
    )

    render_titulo_seccion("📋 Detalle por Sistema")
    with st.expander("📋 Ver Detalle por Sistema", expanded=True):
        if not df_v.empty:
            num_cols = [c for c in ["monto_venta", "comision", "monto_premios"] if c in df_v.columns]
            df_v_grouped = df_v.groupby("sistema", as_index=False)[num_cols].sum()
            df_v_grouped = df_v_grouped.rename(columns={"monto_venta": "venta", "monto_premios": "premios"})
            st.dataframe(
                df_v_grouped,
                column_config={
                    "venta": st.column_config.NumberColumn("venta", format="$%,.2f"),
                    "comision": st.column_config.NumberColumn("comision", format="$%,.2f"),
                    "premios": st.column_config.NumberColumn("premios", format="$%,.2f"),
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Sin ventas este dia.")

    if not df_g.empty:
        with st.expander("💸 Ver Detalle de Gastos", expanded=False):
            df_g_disp = df_g.copy()
            if "confirmado" in df_g_disp.columns:
                df_g_disp["Conf."] = df_g_disp["confirmado"].apply(lambda c: "✅ C" if c else "⏳ Pendiente")
            cols_g_show = [c for c in ["concepto", "monto", "moneda", "Conf.", "fecha"] if c in df_g_disp.columns]
            st.dataframe(
                df_g_disp[cols_g_show],
                column_config={"monto": st.column_config.NumberColumn("monto", format="$%,.2f")},
                use_container_width=True,
                hide_index=True
            )

    if not df_p.empty:
        with st.expander("💳 Ver Detalle de Pagos", expanded=False):
            df_p_disp = df_p.copy()
            if "confirmado" in df_p_disp.columns:
                df_p_disp["Conf."] = df_p_disp["confirmado"].apply(lambda c: "✅ C" if c else "⏳ Pendiente")
            cols_p_show = [c for c in ["tipo_pago", "monto", "moneda", "Conf.", "fecha"] if c in df_p_disp.columns]
            st.dataframe(
                df_p_disp[cols_p_show],
                column_config={"monto": st.column_config.NumberColumn("monto", format="$%,.2f")},
                use_container_width=True,
                hide_index=True
            )

    # 80mm print
    line = "=" * 36
    def txt_80mm():
        nom = agencia_data['nombre_agencia']
        c_label = f" ({map_cajeros.get(str(c_target_id), 'Cajero')})" if (es_supervisor and c_target_id) else ""
        lines = []
        lines.append(line)
        lines.append(f"  Reporte Diario: {fecha_sel}")
        lines.append(f"  {nom}{c_label}")
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
                conf_str = " ✅ C" if r.get('confirmado', False) else ""
                lines.append(f"  {r.get('numero_ticket','?'):>8s}  {monto_val:>10,.2f}  {t_mon} {t_sis}  {t_est}{conf_str}")
            lines.append("-" * 36)
            lines.append(f"  TOTAL TICKETS:   ${total_t_pago:>10,.2f}")
            lines.append(line)

        if not df_g.empty:
            lines.append("  GASTOS")
            lines.append("-" * 36)
            for _, r in df_g.iterrows():
                conf_str = " ✅ C" if r.get('confirmado', False) else " ⏳ P"
                lines.append(f"  {r.get('concepto','?')}  ${float(r['monto']):>10,.2f}{conf_str}")
            lines.append("-" * 36)
            lines.append(f"  TOTAL GASTOS:    ${t_gastos:>10,.2f}")
            lines.append(line)

        if not df_p.empty:
            lines.append("  PAGOS")
            lines.append("-" * 36)
            for _, r in df_p.iterrows():
                conf_str = " ✅ C" if r.get('confirmado', False) else " ⏳ P"
                lines.append(f"  {r.get('tipo_pago','?')}  ${float(r['monto']):>10,.2f}{conf_str}")
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
                        u_clean = user_input.strip()
                        p_clean = key_input.strip()

                        matched_user = None
                        matched_agency = None

                        # 1. Search in taquilla_usuarios for Cajero/Supervisor/Agencia assigned audit role FIRST
                        try:
                            res_user = supabase.table("taquilla_usuarios").select("*").ilike("usuario", u_clean).execute()
                            res_data = res_user.data or []
                            for u_rec in res_data:
                                if str(u_rec.get("clave", "")).strip() == p_clean:
                                    matched_user = u_rec
                                    break
                        except Exception:
                            pass

                        # 2. Search in agencias table for Agency access if not explicitly found in taquilla_usuarios
                        if not matched_user:
                            try:
                                res_ag_user = supabase.table("agencias").select("*").ilike("usuario_taquilla", u_clean).execute()
                                ag_data = res_ag_user.data or []
                                for ag_rec in ag_data:
                                    if str(ag_rec.get("clave_taquilla", "")).strip() == p_clean:
                                        matched_agency = ag_rec
                                        matched_user = {
                                            "id": f"ag_{ag_rec['id']}",
                                            "usuario": str(ag_rec.get("usuario_taquilla", u_clean)).strip(),
                                            "clave": p_clean,
                                            "agencia_id": ag_rec["id"],
                                            "nombre_cajero": ag_rec.get("nombre_agencia", u_clean),
                                            "rol": "agencia",
                                            "activo": True
                                        }
                                        break
                            except Exception:
                                pass
                
                if matched_user:
                    user_data = matched_user
                    res_agencia = supabase.table("agencias").select("*").execute()
                    df_todas = pd.DataFrame(res_agencia.data or [])
                    raw_id = str(user_data.get("agencia_id", "")).strip()

                    match = pd.DataFrame()
                    if matched_agency:
                        match = pd.DataFrame([matched_agency])
                    elif not df_todas.empty:
                        if raw_id and raw_id.lower() != "none":
                            match = df_todas[df_todas["id"].astype(str) == raw_id]
                        if match.empty and "nombre_cajero" in user_data:
                            caj_nom = str(user_data.get("nombre_cajero", "")).strip().upper()
                            if caj_nom:
                                match = df_todas[df_todas["nombre_agencia"].astype(str).str.upper().str.strip() == caj_nom]
                        if match.empty and len(df_todas) == 1:
                            match = df_todas.iloc[[0]]

                    if not match.empty:
                        st.session_state.taquilla_autenticada = True
                        st.session_state.agencia_actual = match.iloc[0].to_dict()
                        st.session_state.cajero_actual = {
                            "id": user_data["id"], 
                            "usuario": user_data["usuario"], 
                            "rol": user_data.get("rol", "agencia"), 
                            "nombre": user_data.get("nombre_cajero", user_data["usuario"])
                        }
                        st.session_state["opcion_actual"] = "Inicio"
                        st.rerun()
                    else:
                        status_placeholder.error("Agencia no encontrada.")
                else:
                    status_placeholder.error("Credenciales incorrectas.")
else:
    _check_cerrado_col()
    _check_saldo_taquilla_table()
    _check_cajero_id_cols()
    ag = st.session_state.agencia_actual
    cajero = st.session_state.cajero_actual
    cajero_id_sb = None if str(cajero.get('rol', '')).lower() in ['supervisor', 'agencia'] else cajero.get('id')
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
            z-index: 999990 !important;
        }

        footer, [data-testid="stDecoration"] {
            display: none !important;
        }

        /* Botón de apertura de menú colapsado */
        [data-testid="collapsedControl"],
        [data-testid="stSidebarCollapsedControl"],
        [data-testid="stHeader"] button[aria-label*="sidebar" i],
        [data-testid="stHeader"] button[aria-label*="Sidebar" i],
        button[data-testid="stSidebarCollapsedControl"] {
            display: flex !important;
            visibility: visible !important;
            opacity: 1 !important;
            z-index: 999999 !important;
            position: fixed !important;
            top: 10px !important;
            left: 10px !important;
            background-color: #0d1b22 !important;
            color: #ffffff !important;
            border: 1px solid rgba(0, 200, 83, 0.6) !important;
            border-radius: 8px !important;
            padding: 4px 8px !important;
            box-shadow: 0 4px 14px rgba(0, 0, 0, 0.5) !important;
        }

        [data-testid="collapsedControl"] svg,
        [data-testid="stSidebarCollapsedControl"] svg,
        [data-testid="stHeader"] button[aria-label*="sidebar" i] svg,
        [data-testid="stHeader"] button[aria-label*="Sidebar" i] svg {
            fill: #ffffff !important;
            color: #ffffff !important;
            stroke: #ffffff !important;
            width: 22px !important;
            height: 22px !important;
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
            background-color: #0b1325 !important;
            border-right: 1px solid rgba(255, 255, 255, 0.05) !important;
        }

        /* 🟢 Compact Sidebar Navigation Styling (Zero Background, Zero Borders, Ultra Legible) 🟢 */
        [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
            padding-top: 0.75rem !important;
        }

        [data-testid="stSidebar"] [data-testid="stElementContainer"] {
            margin-bottom: 2px !important;
            margin-top: 0px !important;
        }

        [data-testid="stSidebar"] [data-testid="stButton"] {
            margin-bottom: 2px !important;
        }

        /* 🟢 1. ELIMINAR BORDES Y ROJOS/MORADOS EN TODOS LOS BOTONES DEL MENU 🟢 */
        [data-testid="stSidebar"] [data-testid="stButton"],
        [data-testid="stSidebar"] [data-testid="stButton"] > button,
        [data-testid="stSidebar"] [data-testid="stButton"] button,
        [data-testid="stSidebar"] [data-testid="stElementContainer"] button {
            justify-content: flex-start !important;
            text-align: left !important;
            font-size: 0.88rem !important;
            font-weight: 600 !important;
            padding: 4px 10px !important;
            min-height: 32px !important;
            height: 32px !important;
            line-height: 1.2 !important;
            border-radius: 6px !important;
            transition: all 0.15s ease !important;
            margin: 0 !important;
            background: transparent !important;
            background-color: transparent !important;
            border: none !important;
            border-color: transparent !important;
            outline: none !important;
            box-shadow: none !important;
            color: #ffffff !important;
            width: 100% !important;
        }

        /* 🟢 2. TEXTO ULTRA-LEGIBLE Y RESALTADO PARA EL BOTON ACTIVO (VERDE SOLIDO) 🟢 */
        [data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"],
        [data-testid="stSidebar"] [data-testid="stButton"] button[data-testid="baseButton-primary"] {
            background-color: #00c853 !important;
            background: #00c853 !important;
            color: #ffffff !important;
            font-weight: 800 !important;
            border: none !important;
            border-color: transparent !important;
            border-radius: 6px !important;
            box-shadow: 0 4px 14px rgba(0, 200, 83, 0.4) !important;
        }
        /* Forzar texto blanco nítido y resaltado dentro del botón activo */
        [data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"] *,
        [data-testid="stSidebar"] [data-testid="stButton"] button[data-testid="baseButton-primary"] * {
            color: #ffffff !important;
            font-weight: 800 !important;
            font-size: 0.95rem !important;
            text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5) !important;
        }

        /* 🟢 3. BOTONES INACTIVOS: TOTALMENTE TRANSPARENTES SIN BORDES 🟢 */
        [data-testid="stSidebar"] [data-testid="stButton"] button[kind="secondary"],
        [data-testid="stSidebar"] [data-testid="stButton"] button[data-testid="baseButton-secondary"] {
            background-color: transparent !important;
            background: transparent !important;
            color: #e2e8f0 !important;
            border: none !important;
            border-color: transparent !important;
            box-shadow: none !important;
        }
        [data-testid="stSidebar"] [data-testid="stButton"] button[kind="secondary"] *,
        [data-testid="stSidebar"] [data-testid="stButton"] button[data-testid="baseButton-secondary"] * {
            color: #e2e8f0 !important;
            font-weight: 600 !important;
        }

        /* Hover para inactivos */
        [data-testid="stSidebar"] [data-testid="stButton"] button[kind="secondary"]:hover,
        [data-testid="stSidebar"] [data-testid="stButton"] button[data-testid="baseButton-secondary"]:hover {
            background-color: rgba(255, 255, 255, 0.08) !important;
            background: rgba(255, 255, 255, 0.08) !important;
            color: #ffffff !important;
            border: none !important;
            border-color: transparent !important;
        }
        [data-testid="stSidebar"] [data-testid="stButton"] button[kind="secondary"]:hover * {
            color: #ffffff !important;
        }

        /* 🚪 BOTON CERRAR SESION: TARJETA DELINEADA LIMPIA 🚪 */
        [data-testid="stSidebar"] button[key="btn_logout_sidebar"],
        [data-testid="stSidebar"] button[key="btn_logout_sidebar"]:hover {
            border: 1px solid rgba(255, 255, 255, 0.15) !important;
            background-color: rgba(255, 255, 255, 0.03) !important;
            justify-content: center !important;
            text-align: center !important;
            border-radius: 8px !important;
            min-height: 36px !important;
            height: 36px !important;
            margin-top: 0.25rem !important;
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
            [data-testid="stSidebar"] {
                z-index: 999998 !important;
                top: 0 !important;
            }
            [data-testid="stSidebar"] [data-testid="stButton"] button {
                min-height: 40px !important;
                font-size: 0.92rem !important;
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
            z-index: 999990 !important;
        }

        /* Botón de apertura de menú colapsado */
        [data-testid="collapsedControl"],
        [data-testid="stSidebarCollapsedControl"],
        [data-testid="stHeader"] button[aria-label*="sidebar" i],
        [data-testid="stHeader"] button[aria-label*="Sidebar" i],
        button[data-testid="stSidebarCollapsedControl"] {
            display: flex !important;
            visibility: visible !important;
            opacity: 1 !important;
            z-index: 999999 !important;
            position: fixed !important;
            top: 10px !important;
            left: 10px !important;
            background-color: #ffffff !important;
            color: #0f172a !important;
            border: 1px solid rgba(0, 200, 83, 0.6) !important;
            border-radius: 8px !important;
            padding: 4px 8px !important;
            box-shadow: 0 4px 14px rgba(0, 0, 0, 0.15) !important;
        }

        [data-testid="collapsedControl"] svg,
        [data-testid="stSidebarCollapsedControl"] svg,
        [data-testid="stHeader"] button[aria-label*="sidebar" i] svg,
        [data-testid="stHeader"] button[aria-label*="Sidebar" i] svg {
            fill: #0f172a !important;
            color: #0f172a !important;
            stroke: #0f172a !important;
            width: 22px !important;
            height: 22px !important;
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
            [data-testid="stSidebar"] {
                z-index: 999998 !important;
                top: 0 !important;
            }
            [data-testid="stSidebar"] [data-testid="stButton"] button {
                min-height: 40px !important;
                font-size: 0.92rem !important;
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

    if "opcion_actual" not in st.session_state:
        st.session_state["opcion_actual"] = "Inicio"

    rol_lower = str(cajero.get("rol", "")).lower()

    if rol_lower == "supervisor":
        menu_items = [
            ("🏠 Inicio", "Inicio"),
            ("📌 Pizarra", "Pizarra"),
            ("📊 Reporte", "Reporte por Rango"),
            ("🔒 Cierre Diario", "Cierre Diario")
        ]
    elif rol_lower == "agencia":
        menu_items = [
            ("🏠 Inicio", "Inicio"),
            ("📊 Reporte", "Reporte por Rango"),
            ("💵 Pago Efectivo", "Gestión de Pagos"),
            ("🏦 Gestión Bancaria", "Gestión Bancaria")
        ]
    else:
        menu_items = [
            ("🏠 Inicio", "Inicio"),
            ("📊 Reporte", "Reporte por Rango"),
            ("🎰 Carga de Ventas", "Carga de Ventas"),
            ("🎟️ Tickets Premiados", "Tickets Premiados"),
            ("💸 Gastos Agencias", "Gestión de Gastos"),
            ("💵 Pago Efectivo", "Gestión de Pagos"),
            ("🏦 Gestión Bancaria", "Gestión Bancaria"),
            ("🔒 Cierre Diario", "Cierre Diario")
        ]
        if st.session_state["opcion_actual"] not in [m[1] for m in menu_items]:
            st.session_state["opcion_actual"] = "Inicio"

    u_id_admin_sb = ag.get("user_id")
    ciclo_admin_sb = obtener_periodo_trabajo(u_id_admin_sb)
    
    if rol_lower in ["agencia", "supervisor"]:
        label_periodo_sb = "Periodo de Trabajo"
        def _fmt_f(f_str):
            try: return pd.to_datetime(f_str).strftime("%d/%m/%Y")
            except Exception: return str(f_str)
        if ciclo_admin_sb and ciclo_admin_sb.get("desde"):
            f1_sb = _fmt_f(ciclo_admin_sb.get("desde"))
            f2_sb = _fmt_f(ciclo_admin_sb.get("hasta"))
            val_periodo_sb = f"📅 {f1_sb} al {f2_sb}"
        else:
            val_periodo_sb = "📅 Sin periodo"
        val_color_sb = "#69f0ae"
    else:
        label_periodo_sb = "Último Cierre"
        val_periodo_sb = f"📅 {ultimo_cierre.strftime('%d/%m/%Y')}" if ultimo_cierre else "📅 Sin cierres"
        val_color_sb = '#34d399' if ultimo_cierre else '#fb7185'

    wa_num_raw = str(ag.get("telefono_whatsapp", ag.get("telefono", ""))).strip()
    if not wa_num_raw or wa_num_raw.lower() in ["none", "nan"]:
        wa_num_raw = obtener_whatsapp_agencia_local(u_id_admin_sb, ag.get("nombre_agencia", ""))

    wa_display_html = ""
    if wa_num_raw and wa_num_raw.lower() != "none":
        clean_num = ''.join(c for c in wa_num_raw if c.isdigit())
        if len(clean_num) == 10 and clean_num.startswith("0"):
            clean_num = "58" + clean_num[1:]
        elif len(clean_num) == 11 and clean_num.startswith("58"):
            pass
        wa_link = f"https://wa.me/{clean_num}" if clean_num else "#"
        wa_display_html = f"""
<div style="font-size: 0.7rem; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 0.4rem; margin-bottom: 0.1rem;">Contacto WhatsApp</div>
<div style="font-size: 0.85rem; font-weight: 600; color: #25D366; font-family: inherit;">
    📱 <a href="{wa_link}" target="_blank" style="color: #25D366; text-decoration: none; font-weight: 700;">{wa_num_raw}</a>
</div>
"""

    with st.sidebar:
        sidebar_info = f"""<div style="background-color: {card_bg}; border: 1px solid {card_border}; padding: 0.85rem 1rem; border-radius: 12px; margin-bottom: 0.5rem;">
<div style="font-size: 0.7rem; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.1rem;">Terminal</div>
<div style="font-size: 1rem; font-weight: 700; color: {text_val_color}; margin-bottom: 0.5rem;">🏢 {ag['nombre_agencia'].upper()}</div>
<div style="font-size: 0.7rem; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.1rem;">Usuario</div>
<div style="font-size: 0.9rem; font-weight: 600; color: {text_val_color}; margin-bottom: 0.5rem;">👤 {(cajero.get('nombre') or cajero.get('usuario') or 'USUARIO').upper()}</div>
<div style="font-size: 0.7rem; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.1rem;">Rol</div>
<div style="display: inline-block; background-color: {badge_bg}; border: 1px solid {badge_border}; color: {badge_text}; font-size: 0.7rem; font-weight: 700; padding: 0.15rem 0.4rem; border-radius: 4px; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem;">{cajero['rol'].upper()}</div>
<div style="font-size: 0.7rem; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.1rem;">{label_periodo_sb}</div>
<div style="font-size: 0.85rem; font-weight: 500; color: {val_color_sb}; font-family: inherit;">{val_periodo_sb}</div>
{wa_display_html}
</div>"""
        st.markdown(sidebar_info, unsafe_allow_html=True)

        st.markdown(
            f"""<div style="font-size: 0.7rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.3rem;">📌 MENÚ DE OPERACIONES</div>""",
            unsafe_allow_html=True
        )

        for label_disp, val_opcion in menu_items:
            is_active = (st.session_state["opcion_actual"] == val_opcion)
            btn_type = "primary" if is_active else "secondary"
            if st.button(label_disp, key=f"nav_btn_{val_opcion}", type=btn_type, use_container_width=True):
                st.session_state["opcion_actual"] = val_opcion
                st.rerun()

        st.divider()
        user_rol = str(cajero.get('rol', 'cajero')).lower()
        with st.popover(f"📖 Guía de Uso ({user_rol.upper()})", use_container_width=True):
            st.markdown(f"### 📖 Guía Operativa — Rol {user_rol.upper()}")
            
            if user_rol == "agencia":
                st.markdown("""
                **🏢 Manual de Operación para Agencias:**
                1. **Monitoreo del Ciclo Activo:** Consulta tus ventas brutas, comisiones negociadas, premios y saldo neto por cada moneda (BS, USD, COP).
                2. **Libro de Cobranzas:** Revisa el estado de cuenta semanal, saldo inicial, abonado y balance pendiente.
                3. **Auditoría de Pagos y Gastos:** Verifica los abonos y gastos registrados por tus terminales.
                """)
            elif user_rol == "supervisor":
                st.markdown("""
                **🛡️ Manual de Operación para Supervisores:**
                1. **Gestión de Cierres:** Revisa el balance individual de cada cajero terminal en tiempo real.
                2. **Recepción de Efectivo (Cajero ➔ Supervisor):** Haz clic en `🤝 Confirmar (Supervisor)` al recibir el dinero físico del cajero.
                3. **Caja Chica Acumulada:** Usa `💸 Entregar al Administrador` para liquidar los fondos recaudados hacia la Administración.
                """)
            else:
                st.markdown("""
                **👤 Manual de Operación para Cajeros:**
                1. **Carga de Ventas Diarias:** Selecciona el sistema (ej. BETM3), la moneda y registra tu venta bruta y premios pagados.
                2. **Registro de Gastos:** Ingresa gastos de papelería, combustible, sueldos o servicios.
                3. **Rendición de Efectivo:** Entrega el efectivo cobrado a tu supervisor para que confirme la recepción `🤝`.
                4. **Solicitud de Cierre:** Solicita el cierre de turno al finalizar la jornada.
                """)

            pdf_filename = f"Guia_de_Uso_{user_rol.upper()}.pdf"
            pdf_path = os.path.join(os.path.dirname(__file__), pdf_filename)
            if not os.path.exists(pdf_path):
                pdf_path = os.path.join(os.path.dirname(__file__), "Guia_de_Uso_Taquilla_Movil.pdf")

            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f_pdf:
                    st.download_button(
                        label=f"📥 Descargar Guía Exclusiva {user_rol.upper()} (PDF)",
                        data=f_pdf.read(),
                        file_name=pdf_filename,
                        mime="application/pdf",
                        use_container_width=True
                    )
            
            st.info("💡 Tip: Puedes subir este documento PDF a **NotebookLM (Google)** para generar audios explicativos (Podcast) o hacer preguntas automáticas.")

        if st.button("🚪 Cerrar Sesión", use_container_width=True, key="btn_logout_sidebar"):
            st.session_state.taquilla_autenticada = False
            st.session_state["opcion_actual"] = "Inicio"
            st.rerun()

    opcion = st.session_state["opcion_actual"]

    if opcion == "Inicio": modulo_home(ag)
    elif opcion == "Pizarra": modulo_pizarra(ag)
    elif opcion == "Carga de Ventas": modulo_registro_taquilla(ag)
    elif opcion == "Gestión de Gastos": modulo_gastos(ag)
    elif opcion == "Gestión de Pagos": modulo_pagos(ag)
    elif opcion == "Gestión Bancaria": modulo_gestion_bancaria(ag)
    elif opcion == "Reporte por Rango": modulo_reporte_rango(ag)
    elif opcion == "Tickets Premiados": modulo_premios_tickets(ag)
    elif opcion == "Cierre Diario": modulo_cierre_diario(ag)
    elif opcion == "Reporte Diario": modulo_reporte_diario(ag)
