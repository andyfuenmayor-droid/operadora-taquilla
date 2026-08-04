import streamlit as st
import pandas as pd
from datetime import datetime
import time
from utils import supabase
from utils import obtener_periodo_trabajo

def obtener_nombre_usuario_actual():
    if "cajero_actual" in st.session_state and st.session_state["cajero_actual"]:
        c = st.session_state["cajero_actual"]
        return c.get("nombre") or c.get("usuario") or "Supervisor"
    elif "user" in st.session_state:
        u_obj = st.session_state["user"]
        if hasattr(u_obj, "email") and u_obj.email:
            return u_obj.email.split("@")[0]
    return "Supervisor"

def normalizar_moneda(mon):
    m = str(mon or "").upper().strip()
    if m in ["BS", "VES", "BOLIVARES", "BOLÍVARES", "BS.", "BOLIVAR", "VES."]:
        return "BS"
    if m in ["USD", "DOLARES", "DÓLARES", "$", "DOLAR", "USD."]:
        return "USD"
    if m in ["COP", "PESOS", "PESO", "COP."]:
        return "COP"
    return m

def verificar_existe_supervisor(u_id=None):
    """Verifica si en la base de datos existe al menos un usuario activo con rol 'supervisor'."""
    try:
        query = supabase.table("taquilla_usuarios").select("id, rol").eq("rol", "supervisor")
        if u_id:
            query = query.eq("user_id", u_id)
        res = query.execute()
        if res.data and len(res.data) > 0:
            return True
    except Exception:
        pass
    
    cajero_info = st.session_state.get("cajero_actual", {})
    if isinstance(cajero_info, dict) and str(cajero_info.get("rol", "")).lower() == "supervisor":
        return True

    return False

def _sincronizar_efectivo_supervisor_con_pagos(existe_supervisor=True):
    """Garantiza que todos los pagos en efectivo confirmados por el supervisor (o todos los de los cajeros si no hay supervisor)
    tengan su movimiento correspondiente registrado en cda_caja_efectivo_supervisor."""
    try:
        if existe_supervisor:
            res_pd = supabase.table("cda_pagos_diarios").select("*").eq("confirmado_supervisor", True).execute()
        else:
            res_pd = supabase.table("cda_pagos_diarios").select("*").execute()

        if not res_pd.data:
            return

        res_movs = supabase.table("cda_caja_efectivo_supervisor").select("*").execute()
        pagos_registrados = set()
        if res_movs.data:
            for rm in res_movs.data:
                if rm.get("pago_id"):
                    pagos_registrados.add(rm["pago_id"])

        mapa_cajeros = {}
        try:
            res_usr = supabase.table("taquilla_usuarios").select("id, usuario, nombre_cajero").execute()
            if res_usr.data:
                for u in res_usr.data:
                    cid = str(u["id"])
                    mapa_cajeros[cid] = u.get("nombre_cajero") or u.get("usuario") or f"Cajero {cid}"
        except Exception:
            pass

        for pago in res_pd.data:
            pid = pago.get("id")
            tipo = str(pago.get("tipo_pago") or "").upper()
            es_efectivo = "EFECTIVO" in tipo or ("REF:" not in tipo and "PUNTO" not in tipo and "TRANSFERENCIA" not in tipo and "ZELLE" not in tipo and "PAGO MÓVIL" not in tipo)

            if pid and es_efectivo and pid not in pagos_registrados:
                cid = str(pago.get("cajero_id") or pago.get("user_id") or "")
                c_nombre = mapa_cajeros.get(cid, f"ID {cid}" if cid else "Cajero")
                sup_nom = str(pago.get("supervisor_nombre") or c_nombre or "Cajero").strip()
                u_id_val = str(pago.get("user_id") or "SYSTEM").strip()
                monto_val = float(pago.get("monto") or 0.0)
                moneda_val = normalizar_moneda(pago.get("moneda"))

                comentario_text = f"Recibido de cajero {c_nombre} (Auto-sincronizado)" if existe_supervisor else f"Recaudado por cajero {c_nombre} (Caja Chica Cajero)"

                try:
                    supabase.table("cda_caja_efectivo_supervisor").insert({
                        "user_id": u_id_val,
                        "agencia": str(pago.get("agencia") or "TODAS").upper(),
                        "supervisor_nombre": sup_nom,
                        "tipo_movimiento": "ENTRADA_CAJERO",
                        "monto": monto_val,
                        "moneda": moneda_val,
                        "pago_id": pid,
                        "comentario": comentario_text
                    }).execute()
                    pagos_registrados.add(pid)
                except Exception:
                    try:
                        supabase.table("cda_caja_efectivo_supervisor").insert({
                            "user_id": u_id_val,
                            "agencia": str(pago.get("agencia") or "TODAS").upper(),
                            "supervisor_nombre": sup_nom,
                            "tipo_movimiento": "ENTRADA_CAJERO",
                            "monto": monto_val,
                            "moneda": moneda_val,
                            "comentario": comentario_text
                        }).execute()
                    except Exception:
                        pass
    except Exception:
        pass

def _check_confirmado_cols_cms():
    """Verifica si las columnas `confirmado` y `confirmado_por` existen en cda_gastos_diarios, cda_pagos_diarios y cda_pagos_bancarios."""
    tablas_faltantes = []
    for tabla in ["cda_gastos_diarios", "cda_pagos_diarios", "cda_pagos_bancarios"]:
        try:
            supabase.table(tabla).select("confirmado").limit(1).execute()
        except Exception:
            tablas_faltantes.append(tabla)

    cols_sup_faltantes = []
    try:
        supabase.table("cda_pagos_diarios").select("confirmado_supervisor").limit(1).execute()
    except Exception:
        cols_sup_faltantes.append("cda_pagos_diarios")

    caja_sup_existe = True
    pago_id_caja_existe = True
    try:
        supabase.table("cda_caja_efectivo_supervisor").select("id").limit(1).execute()
        try:
            supabase.table("cda_caja_efectivo_supervisor").select("pago_id").limit(1).execute()
        except Exception:
            pago_id_caja_existe = False
    except Exception:
        caja_sup_existe = False
        pago_id_caja_existe = False

    if tablas_faltantes or cols_sup_faltantes or not caja_sup_existe or not pago_id_caja_existe:
        sql_lines = []
        for t in tablas_faltantes:
            sql_lines.append(f"ALTER TABLE {t} ADD COLUMN IF NOT EXISTS confirmado BOOLEAN DEFAULT FALSE;")
            sql_lines.append(f"ALTER TABLE {t} ADD COLUMN IF NOT EXISTS confirmado_por TEXT;")
        
        if cols_sup_faltantes:
            sql_lines.append("ALTER TABLE cda_pagos_diarios ADD COLUMN IF NOT EXISTS confirmado_supervisor BOOLEAN DEFAULT FALSE;")
            sql_lines.append("ALTER TABLE cda_pagos_diarios ADD COLUMN IF NOT EXISTS supervisor_nombre TEXT;")
            sql_lines.append("ALTER TABLE cda_pagos_diarios ADD COLUMN IF NOT EXISTS fecha_confirmacion_supervisor TIMESTAMP WITH TIME ZONE;")
            sql_lines.append("ALTER TABLE cda_pagos_diarios ADD COLUMN IF NOT EXISTS comentario_supervisor TEXT;")
            sql_lines.append("ALTER TABLE cda_pagos_diarios ADD COLUMN IF NOT EXISTS entregado_admin BOOLEAN DEFAULT FALSE;")

        if not caja_sup_existe:
            sql_lines.append("""
CREATE TABLE IF NOT EXISTS cda_caja_efectivo_supervisor (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    agencia TEXT NOT NULL,
    supervisor_nombre TEXT NOT NULL,
    tipo_movimiento TEXT NOT NULL,
    monto NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    moneda TEXT NOT NULL,
    pago_id BIGINT,
    comentario TEXT,
    fecha TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
            """.strip())
        elif not pago_id_caja_existe:
            sql_lines.append("ALTER TABLE cda_caja_efectivo_supervisor ADD COLUMN IF NOT EXISTS pago_id BIGINT;")

        sql_script = "\n".join(sql_lines)
        st.warning(
            f"⚠️ **Atención Supabase:** Es posible que falten columnas o tablas de supervisión en tu base de datos.\n\n"
            f"Para habilitar el flujo completo de **Confirmaciones y Caja del Supervisor**, ejecuta este comando en el **SQL Editor** de tu panel de Supabase:\n\n"
            f"```sql\n{sql_script}\n```"
        )

def obtener_badge_confirmado_html(confirmado):
    """Devuelve la letra resaltada verde pequeña 'C' encima si está confirmado."""
    if confirmado:
        return "<sup style='background-color:#1b4332; color:#52b788; border-radius:3px; padding:1px 5px; font-size:10px; font-weight:800; font-family:sans-serif; margin-left:3px; border:1px solid #2d6a4f;' title='Confirmado en Pizarra'>C</sup>"
    return ""

def _renderizar_resumen_metricas(df_target):
    if df_target.empty:
        df_pagos = pd.DataFrame()
        df_gastos = pd.DataFrame()
    else:
        df_pagos = df_target[df_target["categoria"] != "Gastos"]
        df_gastos = df_target[df_target["categoria"] == "Gastos"]

    pagos_pend = df_pagos[df_pagos["confirmado"] == False] if not df_pagos.empty else pd.DataFrame()
    pagos_conf = df_pagos[df_pagos["confirmado"] == True] if not df_pagos.empty else pd.DataFrame()

    gastos_pend = df_gastos[df_gastos["confirmado"] == False] if not df_gastos.empty else pd.DataFrame()
    gastos_conf = df_gastos[df_gastos["confirmado"] == True] if not df_gastos.empty else pd.DataFrame()

    bs_p_pagos = pagos_pend[pagos_pend["moneda"].isin(["BS", "BOLIVARES", "VES"])]["monto"].sum() if not pagos_pend.empty else 0.0
    bs_c_pagos = pagos_conf[pagos_conf["moneda"].isin(["BS", "BOLIVARES", "VES"])]["monto"].sum() if not pagos_conf.empty else 0.0

    usd_p_pagos = pagos_pend[pagos_pend["moneda"].isin(["USD", "DOLARES", "$"])]["monto"].sum() if not pagos_pend.empty else 0.0
    usd_c_pagos = pagos_conf[pagos_conf["moneda"].isin(["USD", "DOLARES", "$"])]["monto"].sum() if not pagos_conf.empty else 0.0

    cop_p_pagos = pagos_pend[pagos_pend["moneda"].isin(["COP", "PESOS"])]["monto"].sum() if not pagos_pend.empty else 0.0
    cop_c_pagos = pagos_conf[pagos_conf["moneda"].isin(["COP", "PESOS"])]["monto"].sum() if not pagos_conf.empty else 0.0

    bs_p_gastos = gastos_pend[gastos_pend["moneda"].isin(["BS", "BOLIVARES", "VES"])]["monto"].sum() if not gastos_pend.empty else 0.0
    bs_c_gastos = gastos_conf[gastos_conf["moneda"].isin(["BS", "BOLIVARES", "VES"])]["monto"].sum() if not gastos_conf.empty else 0.0

    usd_p_gastos = gastos_pend[gastos_pend["moneda"].isin(["USD", "DOLARES", "$"])]["monto"].sum() if not gastos_pend.empty else 0.0
    usd_c_gastos = gastos_conf[gastos_conf["moneda"].isin(["USD", "DOLARES", "$"])]["monto"].sum() if not gastos_conf.empty else 0.0

    cop_p_gastos = gastos_pend[gastos_pend["moneda"].isin(["COP", "PESOS"])]["monto"].sum() if not gastos_pend.empty else 0.0
    cop_c_gastos = gastos_conf[gastos_conf["moneda"].isin(["COP", "PESOS"])]["monto"].sum() if not gastos_conf.empty else 0.0

    st.markdown("<div style='font-size: 15px; font-weight: 800; color: #38bdf8; margin-bottom: 8px; font-family: sans-serif;'>💳 RESUMEN DE PAGOS (Transferencias / POS / Efectivo)</div>", unsafe_allow_html=True)
    col_p1, col_p2, col_p3, col_p4, col_p5 = st.columns(5)
    with col_p1:
        st.markdown(f"""
            <div style="background: rgba(14, 165, 233, 0.08); border: 1px solid rgba(56, 189, 248, 0.22); border-radius: 10px; padding: 10px 14px; min-height: 82px;">
                <div style="font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase;">⏳ Pendientes</div>
                <div style="font-size: 18px; font-weight: 800; color: #eab308; margin-top: 6px;">{len(pagos_pend)} reg.</div>
            </div>
        """, unsafe_allow_html=True)
    with col_p2:
        st.markdown(f"""
            <div style="background: rgba(14, 165, 233, 0.08); border: 1px solid rgba(56, 189, 248, 0.22); border-radius: 10px; padding: 10px 14px; min-height: 82px;">
                <div style="font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase;">✅ Confirmados</div>
                <div style="font-size: 18px; font-weight: 800; color: #22c55e; margin-top: 6px;">{len(pagos_conf)} reg.</div>
            </div>
        """, unsafe_allow_html=True)
    with col_p3:
        st.markdown(f"""
            <div style="background: rgba(14, 165, 233, 0.08); border: 1px solid rgba(56, 189, 248, 0.22); border-radius: 10px; padding: 10px 14px; min-height: 82px;">
                <div style="font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase;">🇻🇪 Bolívares BS</div>
                <div style="font-size: 13px; font-weight: 700; color: #eab308; margin-top: 4px;">Pend: Bs {bs_p_pagos:,.2f}</div>
                <div style="font-size: 13px; font-weight: 700; color: #38bdf8; margin-top: 2px;">Conf: Bs {bs_c_pagos:,.2f}</div>
            </div>
        """, unsafe_allow_html=True)
    with col_p4:
        st.markdown(f"""
            <div style="background: rgba(14, 165, 233, 0.08); border: 1px solid rgba(56, 189, 248, 0.22); border-radius: 10px; padding: 10px 14px; min-height: 82px;">
                <div style="font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase;">💵 Dólares USD</div>
                <div style="font-size: 13px; font-weight: 700; color: #eab308; margin-top: 4px;">Pend: ${usd_p_pagos:,.2f}</div>
                <div style="font-size: 13px; font-weight: 700; color: #38bdf8; margin-top: 2px;">Conf: ${usd_c_pagos:,.2f}</div>
            </div>
        """, unsafe_allow_html=True)
    with col_p5:
        st.markdown(f"""
            <div style="background: rgba(14, 165, 233, 0.08); border: 1px solid rgba(56, 189, 248, 0.22); border-radius: 10px; padding: 10px 14px; min-height: 82px;">
                <div style="font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase;">🇨🇴 Pesos COP</div>
                <div style="font-size: 13px; font-weight: 700; color: #eab308; margin-top: 4px;">Pend: COP {cop_p_pagos:,.2f}</div>
                <div style="font-size: 13px; font-weight: 700; color: #38bdf8; margin-top: 2px;">Conf: COP {cop_c_pagos:,.2f}</div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)

    st.markdown("<div style='font-size: 15px; font-weight: 800; color: #f43f5e; margin-bottom: 8px; font-family: sans-serif;'>💸 RESUMEN DE GASTOS</div>", unsafe_allow_html=True)
    col_g1, col_g2, col_g3, col_g4, col_g5 = st.columns(5)
    with col_g1:
        st.markdown(f"""
            <div style="background: rgba(244, 63, 94, 0.08); border: 1px solid rgba(244, 63, 94, 0.22); border-radius: 10px; padding: 10px 14px; min-height: 82px;">
                <div style="font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase;">⏳ Pendientes</div>
                <div style="font-size: 18px; font-weight: 800; color: #eab308; margin-top: 6px;">{len(gastos_pend)} reg.</div>
            </div>
        """, unsafe_allow_html=True)
    with col_g2:
        st.markdown(f"""
            <div style="background: rgba(244, 63, 94, 0.08); border: 1px solid rgba(244, 63, 94, 0.22); border-radius: 10px; padding: 10px 14px; min-height: 82px;">
                <div style="font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase;">✅ Confirmados</div>
                <div style="font-size: 18px; font-weight: 800; color: #22c55e; margin-top: 6px;">{len(gastos_conf)} reg.</div>
            </div>
        """, unsafe_allow_html=True)
    with col_g3:
        st.markdown(f"""
            <div style="background: rgba(244, 63, 94, 0.08); border: 1px solid rgba(244, 63, 94, 0.22); border-radius: 10px; padding: 10px 14px; min-height: 82px;">
                <div style="font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase;">🇻🇪 Bolívares BS</div>
                <div style="font-size: 13px; font-weight: 700; color: #eab308; margin-top: 4px;">Pend: Bs {bs_p_gastos:,.2f}</div>
                <div style="font-size: 13px; font-weight: 700; color: #f43f5e; margin-top: 2px;">Conf: Bs {bs_c_gastos:,.2f}</div>
            </div>
        """, unsafe_allow_html=True)
    with col_g4:
        st.markdown(f"""
            <div style="background: rgba(244, 63, 94, 0.08); border: 1px solid rgba(244, 63, 94, 0.22); border-radius: 10px; padding: 10px 14px; min-height: 82px;">
                <div style="font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase;">💵 Dólares USD</div>
                <div style="font-size: 13px; font-weight: 700; color: #eab308; margin-top: 4px;">Pend: ${usd_p_gastos:,.2f}</div>
                <div style="font-size: 13px; font-weight: 700; color: #f43f5e; margin-top: 2px;">Conf: ${usd_c_gastos:,.2f}</div>
            </div>
        """, unsafe_allow_html=True)
    with col_g5:
        st.markdown(f"""
            <div style="background: rgba(244, 63, 94, 0.08); border: 1px solid rgba(244, 63, 94, 0.22); border-radius: 10px; padding: 10px 14px; min-height: 82px;">
                <div style="font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase;">🇨🇴 Pesos COP</div>
                <div style="font-size: 13px; font-weight: 700; color: #eab308; margin-top: 4px;">Pend: COP {cop_p_gastos:,.2f}</div>
                <div style="font-size: 13px; font-weight: 700; color: #f43f5e; margin-top: 2px;">Conf: COP {cop_c_gastos:,.2f}</div>
            </div>
        """, unsafe_allow_html=True)

def _renderizar_lista_transacciones(df_list, key_prefix="act", es_pizarra_supervisor=False, existe_supervisor=True):
    if df_list.empty:
        st.info("ℹ️ No hay transacciones que coincidan con los filtros seleccionados.")
        return

    for idx_pos, (idx, row) in enumerate(df_list.iterrows(), start=1):
        is_c = bool(row["confirmado"])
        conf_por = str(row.get("confirmado_por") or "").strip()
        
        is_c_sup = bool(row.get("confirmado_supervisor", False))
        sup_nom = str(row.get("supervisor_nombre") or "").strip()
        com_sup = str(row.get("comentario_supervisor") or "").strip()
        es_efectivo = (row.get("categoria") == "Efectivo")

        # Insignias de Estado
        if es_efectivo:
            if is_c:
                badge_html = "<span class='badge-confirmed'>✅ CONFIRMADO ADMIN <sup style='background:#1b4332; color:#52b788; border-radius:3px; padding:1px 4px; font-weight:bold;'>C</sup></span>"
            elif is_c_sup:
                badge_html = "<span class='badge-pending' style='background-color: rgba(234, 179, 8, 0.15); color: #eab308; border: 1px solid rgba(234, 179, 8, 0.3); padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700;'>⏳ PEND. ADMIN</span>"
            else:
                badge_html = "<span style='background-color: rgba(148, 163, 184, 0.15); color: #94a3b8; border: 1px solid rgba(148, 163, 184, 0.3); padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 700;'>⏳ ESPERANDO SUPERVISOR</span>"
        else:
            badge_html = "<span class='badge-confirmed'>✅ CONFIRMADO <sup style='background:#1b4332; color:#52b788; border-radius:3px; padding:1px 4px; font-weight:bold;'>C</sup></span>" if is_c else "<span class='badge-pending'>⏳ PENDIENTE</span>"

        conf_info_html = f"<br><small style='color: #22c55e; font-weight: 600;'>👤 Confirmado Admin: <b>{conf_por}</b></small>" if (is_c and conf_por) else ""
        
        sup_info_html = ""
        if es_efectivo:
            if is_c_sup and not is_c:
                nota_sup = f" ({com_sup})" if com_sup else ""
                sup_info_html = f"<br><small style='color: #38bdf8; font-weight: 700; background: rgba(56, 189, 248, 0.12); padding: 2px 6px; border-radius: 4px; border: 1px solid rgba(56, 189, 248, 0.25); display: inline-block; margin-top: 3px;'>🤝 Recibido Supervisor (<b>{sup_nom or 'Supervisor'}</b>{nota_sup}) — ⏳ Pendiente por confirmar Admin</small>"
            elif is_c_sup and is_c:
                nota_sup = f" ({com_sup})" if com_sup else ""
                sup_info_html = f"<br><small style='color: #38bdf8; font-weight: 700; background: rgba(56, 189, 248, 0.12); padding: 2px 6px; border-radius: 4px; border: 1px solid rgba(56, 189, 248, 0.25); display: inline-block; margin-top: 3px;'>💬 Recibido por Supervisor: <b>{sup_nom or 'Supervisor'}</b>{nota_sup}</small>"
            else:
                sup_info_html = f"<br><small style='color: #f59e0b; font-weight: 600; background: rgba(245, 158, 11, 0.1); padding: 2px 6px; border-radius: 4px; border: 1px solid rgba(245, 158, 11, 0.2); display: inline-block; margin-top: 3px;'>⏳ Pendiente por ser confirmado / recibido por Supervisor</small>"
        elif existe_supervisor and (is_c_sup or sup_nom):
            nota_sup = f" | {com_sup}" if com_sup else ""
            sup_info_html = f"<br><small style='color: #38bdf8; font-weight: 700; background: rgba(56, 189, 248, 0.12); padding: 2px 6px; border-radius: 4px; border: 1px solid rgba(56, 189, 248, 0.25); display: inline-block; margin-top: 3px;'>💬 Entregado a Supervisor: <b>{sup_nom or 'Supervisor'}</b>{nota_sup}</small>"
        elif not existe_supervisor and row["categoria"] == "Efectivo":
            sup_info_html = f"<br><small style='color: #22c55e; font-weight: 700; background: rgba(34, 197, 94, 0.12); padding: 2px 6px; border-radius: 4px; border: 1px solid rgba(34, 197, 94, 0.25); display: inline-block; margin-top: 3px;'>📦 En Caja Chica de Cajero (Listo para Liquidación)</small>"

        num_badge = f"<span style='background-color: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); padding: 1px 6px; border-radius: 4px; font-size: 12px; font-weight: 800; margin-right: 6px;'>#{idx_pos}</span>"

        with st.container(border=True):
            c_info, c_monto, c_action = st.columns([5, 3, 2])

            with c_info:
                badge_c_letter = obtener_badge_confirmado_html(is_c)
                st.markdown(
                    f"{num_badge} **{row['agencia']}** | Cajero: **{row['cajero_nombre']}** | 📅 {row['fecha']} {badge_c_letter}<br>"
                    f"<small style='color: #94a3b8;'>Categoría: <b>{row['categoria']}</b> | Método: <b>{row['metodo']}</b></small><br>"
                    f"<small>Concepto: <b>{row['concepto']}</b> | Ref: <b>{row['referencia']}</b> | Pagador: <b>{row['pagador']}</b></small>"
                    f"{sup_info_html}"
                    f"{conf_info_html}",
                    unsafe_allow_html=True
                )

            with c_monto:
                badge_sup_state = ""
                if row["categoria"] == "Efectivo":
                    if existe_supervisor:
                        badge_sup_state = "<br><span style='background-color: rgba(56, 189, 248, 0.15); color: #38bdf8; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 700; border: 1px solid rgba(56, 189, 248, 0.3);'>🤝 RECIBIDO SUPERVISOR</span>" if is_c_sup else "<br><span style='background-color: rgba(234, 179, 8, 0.15); color: #eab308; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 700; border: 1px solid rgba(234, 179, 8, 0.3);'>⏳ PEND. RECIBIR SUPERVISOR</span>"
                    else:
                        badge_sup_state = "<br><span style='background-color: rgba(34, 197, 94, 0.15); color: #22c55e; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 700;'>📦 EN CAJA DE CAJERO</span>"

                st.markdown(
                    f"<div style='text-align: right; padding-right: 10px;'>"
                    f"<span style='font-size: 16px; font-weight: 800;'>{row['moneda']} {row['monto']:,.2f}</span><br>"
                    f"{badge_html}"
                    f"{badge_sup_state}"
                    f"</div>",
                    unsafe_allow_html=True
                )

            with c_action:
                btn_key = f"btn_conf_{key_prefix}_{row['tabla']}_{row['id']}"
                
                # Flujo Supervisor si estamos en la Pizarra de Efectivo Cajero<->Supervisor
                if es_pizarra_supervisor and row["categoria"] == "Efectivo":
                    if existe_supervisor:
                        if not is_c_sup:
                            if st.button("🤝 Confirmar (Supervisor)", key=f"sup_{btn_key}", use_container_width=True):
                                current_usr = obtener_nombre_usuario_actual()
                                try:
                                    data_sup = {
                                        "confirmado_supervisor": True,
                                        "supervisor_nombre": current_usr,
                                        "comentario_supervisor": f"Entregado a Supervisor {current_usr}",
                                        "fecha_confirmacion_supervisor": datetime.now().isoformat()
                                    }
                                    supabase.table("cda_pagos_diarios").update(data_sup).eq("id", row["id"]).execute()
                                    
                                    # Registrar entrada en Caja de Efectivo del Supervisor
                                    u_id_val = str(row.get("cajero_id") or row.get("user_id") or "SYSTEM")
                                    mon_norm = normalizar_moneda(row["moneda"])
                                    try:
                                        supabase.table("cda_caja_efectivo_supervisor").insert({
                                            "user_id": u_id_val,
                                            "agencia": str(row.get("agencia") or "TODAS").upper(),
                                            "supervisor_nombre": current_usr,
                                            "tipo_movimiento": "ENTRADA_CAJERO",
                                            "monto": float(row["monto"]),
                                            "moneda": mon_norm,
                                            "pago_id": row["id"],
                                            "comentario": f"Recibido de cajero {row['cajero_nombre']}"
                                        }).execute()
                                    except Exception:
                                        try:
                                            supabase.table("cda_caja_efectivo_supervisor").insert({
                                                "user_id": u_id_val,
                                                "agencia": str(row.get("agencia") or "TODAS").upper(),
                                                "supervisor_nombre": current_usr,
                                                "tipo_movimiento": "ENTRADA_CAJERO",
                                                "monto": float(row["monto"]),
                                                "moneda": mon_norm,
                                                "comentario": f"Recibido de cajero {row['cajero_nombre']}"
                                            }).execute()
                                        except Exception:
                                            pass

                                    st.success(f"🤝 Efectivo recibido por Supervisor {current_usr}")
                                    time.sleep(0.5)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Error al confirmar por Supervisor: {e}")
                        else:
                            st.info(f"🤝 Recibido por: {sup_nom or 'Supervisor'}")
                            if st.button("↩️ Revertir (Supervisor)", key=f"sup_rev_{btn_key}", use_container_width=True):
                                try:
                                    data_rev_sup = {
                                        "confirmado_supervisor": False,
                                        "supervisor_nombre": None,
                                        "comentario_supervisor": None,
                                        "fecha_confirmacion_supervisor": None
                                    }
                                    supabase.table("cda_pagos_diarios").update(data_rev_sup).eq("id", row["id"]).execute()
                                    
                                    try:
                                        supabase.table("cda_caja_efectivo_supervisor").delete().eq("pago_id", row["id"]).execute()
                                    except Exception:
                                        pass

                                    st.info("↩️ Confirmación de supervisor revertida.")
                                    time.sleep(0.5)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Error al revertir supervisor: {e}")
                    else:
                        st.info("📦 En Caja de Cajero")

                # Flujo Administrador / General
                else:
                    if not is_c:
                        if es_efectivo and not is_c_sup:
                            st.button("✅ Confirmar", key=btn_key, disabled=True, use_container_width=True, help="⚠️ El Supervisor debe confirmar la recepción del efectivo primero")
                        else:
                            if st.button("✅ Confirmar", key=btn_key, use_container_width=True):
                                current_usr = obtener_nombre_usuario_actual()
                                data_conf = {"confirmado": True, "confirmado_por": current_usr}
                                try:
                                    try:
                                        supabase.table(row["tabla"]).update(data_conf).eq("id", row["id"]).execute()
                                    except Exception as ex1:
                                        err_str1 = str(ex1).lower()
                                        if "confirmado_por" in err_str1:
                                            supabase.table(row["tabla"]).update({"confirmado": True}).eq("id", row["id"]).execute()
                                        else:
                                            raise ex1

                                    if row["tabla"] == "cda_pagos_bancarios":
                                        try:
                                            supabase.table("cda_pagos_diarios").update(data_conf).eq("agencia", row["agencia"]).eq("fecha", row["fecha"]).eq("monto", row["monto"]).execute()
                                        except Exception:
                                            try:
                                                supabase.table("cda_pagos_diarios").update({"confirmado": True}).eq("agencia", row["agencia"]).eq("fecha", row["fecha"]).eq("monto", row["monto"]).execute()
                                            except Exception:
                                                pass

                                    st.success(f"✅ Confirmado por {current_usr}")
                                    time.sleep(0.5)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Error al confirmar: {e}")
                    else:
                        if st.button("↩️ Revertir", key=btn_key, use_container_width=True):
                            data_rev = {"confirmado": False, "confirmado_por": None}
                            try:
                                try:
                                    supabase.table(row["tabla"]).update(data_rev).eq("id", row["id"]).execute()
                                except Exception as ex2:
                                    err_str2 = str(ex2).lower()
                                    if "confirmado_por" in err_str2:
                                        supabase.table(row["tabla"]).update({"confirmado": False}).eq("id", row["id"]).execute()
                                    else:
                                        raise ex2

                                if row["tabla"] == "cda_pagos_bancarios":
                                    try:
                                        supabase.table("cda_pagos_diarios").update(data_rev).eq("agencia", row["agencia"]).eq("fecha", row["fecha"]).eq("monto", row["monto"]).execute()
                                    except Exception:
                                        try:
                                            supabase.table("cda_pagos_diarios").update({"confirmado": False}).eq("agencia", row["agencia"]).eq("fecha", row["fecha"]).eq("monto", row["monto"]).execute()
                                        except Exception:
                                            pass

                                st.info("Revertido")
                                time.sleep(0.5)
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error al revertir: {e}")

def _renderizar_caja_acumulada_supervisor(u_id, existe_supervisor=True):
    """Muestra la Caja Chica / Caja Acumulable de Efectivo (del Supervisor o del Cajero si no existe rol Supervisor) con botón de liquidación a Administración."""
    
    # Auto-sincronizar pagos confirmados por supervisor o de cajeros según corresponda
    _sincronizar_efectivo_supervisor_con_pagos(existe_supervisor=existe_supervisor)

    titulo_caja = "📦 Caja Acumulable de Efectivo del Supervisor" if existe_supervisor else "📦 Caja Acumulable de Efectivo del Cajero (Caja Chica)"
    caption_caja = "Efectivo recibido de Cajeros pendiente por entregar / liquidar al Administrador." if existe_supervisor else "Efectivo recaudado por Cajeros pendiente por entregar / liquidar al Administrador."
    popover_btn_label = "💸 Entregar al Administrador"
    popover_title = "##### 💸 Liquidación de Efectivo al Administrador" if existe_supervisor else "##### 💸 Liquidación de Caja Chica de Cajero a Administración"
    nota_default = "Entrega de caja acumulada a Administración" if existe_supervisor else "Entrega de caja chica del Cajero a Administración"

    st.markdown(f"<h4 style='font-size: 16px; font-weight: 800; color: #38bdf8; margin-top: 10px;'>{titulo_caja}</h4>", unsafe_allow_html=True)
    st.caption(caption_caja)

    totales_caja = {"BS": 0.0, "USD": 0.0, "COP": 0.0}
    df_movs = pd.DataFrame()
    
    try:
        res_movs = supabase.table("cda_caja_efectivo_supervisor").select("*").execute()
        if res_movs.data:
            df_movs = pd.DataFrame(res_movs.data)
            if "moneda" in df_movs.columns:
                df_movs["moneda_norm"] = df_movs["moneda"].apply(normalizar_moneda)
                for m in ["BS", "USD", "COP"]:
                    entradas = df_movs[(df_movs["moneda_norm"] == m) & (df_movs["tipo_movimiento"] == "ENTRADA_CAJERO")]["monto"].sum()
                    salidas = df_movs[(df_movs["moneda_norm"] == m) & (df_movs["tipo_movimiento"] == "ENTREGA_ADMIN")]["monto"].sum()
                    totales_caja[m] = float(entradas - salidas)
    except Exception:
        pass

    col_cs1, col_cs2, col_cs3, col_cs4 = st.columns([3, 3, 3, 3])
    with col_cs1:
        st.markdown(f"""
            <div style="background: rgba(34, 197, 94, 0.08); border: 1px solid rgba(34, 197, 94, 0.25); border-radius: 10px; padding: 10px 14px;">
                <div style="font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase;">🇻🇪 Efectivo BS en Caja</div>
                <div style="font-size: 17px; font-weight: 800; color: #22c55e; margin-top: 4px;">Bs {totales_caja['BS']:,.2f}</div>
            </div>
        """, unsafe_allow_html=True)
    with col_cs2:
        st.markdown(f"""
            <div style="background: rgba(34, 197, 94, 0.08); border: 1px solid rgba(34, 197, 94, 0.25); border-radius: 10px; padding: 10px 14px;">
                <div style="font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase;">💵 Efectivo USD en Caja</div>
                <div style="font-size: 17px; font-weight: 800; color: #22c55e; margin-top: 4px;">${totales_caja['USD']:,.2f}</div>
            </div>
        """, unsafe_allow_html=True)
    with col_cs3:
        st.markdown(f"""
            <div style="background: rgba(34, 197, 94, 0.08); border: 1px solid rgba(34, 197, 94, 0.25); border-radius: 10px; padding: 10px 14px;">
                <div style="font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase;">🇨🇴 Efectivo COP en Caja</div>
                <div style="font-size: 17px; font-weight: 800; color: #22c55e; margin-top: 4px;">COP {totales_caja['COP']:,.2f}</div>
            </div>
        """, unsafe_allow_html=True)
    with col_cs4:
        with st.popover(popover_btn_label, use_container_width=True):
            st.markdown(popover_title)
            moneda_liq = st.selectbox("Moneda:", ["USD", "BS", "COP"], key="liq_moneda_sup")
            monto_liq = st.number_input(f"Monto a Entregar ({moneda_liq}):", min_value=0.0, value=float(totales_caja.get(moneda_liq, 0.0)), key="liq_monto_sup")
            nota_liq = st.text_input("Nota / Comentario:", value=nota_default, key="liq_nota_sup")
            
            if st.button("🚀 Confirmar Entrega a Admin", key="btn_confirm_liq_admin", use_container_width=True):
                if monto_liq <= 0:
                    st.error("⚠️ El monto a entregar debe ser mayor a 0.")
                else:
                    curr_usr = obtener_nombre_usuario_actual()
                    u_id_val = str(u_id or "SYSTEM")
                    mon_norm = normalizar_moneda(moneda_liq)
                    try:
                        supabase.table("cda_caja_efectivo_supervisor").insert({
                            "user_id": u_id_val,
                            "agencia": "TODAS",
                            "supervisor_nombre": curr_usr,
                            "tipo_movimiento": "ENTREGA_ADMIN",
                            "monto": float(monto_liq),
                            "moneda": mon_norm,
                            "comentario": nota_liq
                        }).execute()
                        st.success(f"✅ Liquidación de {mon_norm} {monto_liq:,.2f} registrada correctamente al Administrador por {curr_usr}.")
                        time.sleep(0.5)
                        st.rerun()
                    except Exception as ex_l:
                        st.error(f"❌ Error al registrar liquidación: {ex_l}")

    # --- LISTA / DESGLOSE DE EFECTIVO POR CAJA Y AGENCIA ---
    with st.expander("📋 Ver Lista / Desglose de Efectivo por Caja (Agencia y Cajero)", expanded=False):
        if not df_movs.empty:
            df_movs["moneda_norm"] = df_movs["moneda"].apply(normalizar_moneda)
            df_movs["agencia_norm"] = df_movs["agencia"].astype(str).str.upper().str.strip()
            
            st.markdown("<h5 style='font-size: 14px; font-weight: 700; color: #38bdf8;'>🏛️ Total de Efectivo Acumulado por Agencia</h5>", unsafe_allow_html=True)
            
            resumen_agencias = []
            for ag, group in df_movs.groupby("agencia_norm"):
                bs_in = group[(group["moneda_norm"] == "BS") & (group["tipo_movimiento"] == "ENTRADA_CAJERO")]["monto"].sum()
                bs_out = group[(group["moneda_norm"] == "BS") & (group["tipo_movimiento"] == "ENTREGA_ADMIN")]["monto"].sum()
                
                usd_in = group[(group["moneda_norm"] == "USD") & (group["tipo_movimiento"] == "ENTRADA_CAJERO")]["monto"].sum()
                usd_out = group[(group["moneda_norm"] == "USD") & (group["tipo_movimiento"] == "ENTREGA_ADMIN")]["monto"].sum()

                cop_in = group[(group["moneda_norm"] == "COP") & (group["tipo_movimiento"] == "ENTRADA_CAJERO")]["monto"].sum()
                cop_out = group[(group["moneda_norm"] == "COP") & (group["tipo_movimiento"] == "ENTREGA_ADMIN")]["monto"].sum()

                resumen_agencias.append({
                    "Agencia": ag,
                    "Efectivo BS": f"Bs {float(bs_in - bs_out):,.2f}",
                    "Efectivo USD": f"${float(usd_in - usd_out):,.2f}",
                    "Efectivo COP": f"COP {float(cop_in - cop_out):,.2f}",
                    "Total Movs": len(group)
                })

            if resumen_agencias:
                st.dataframe(pd.DataFrame(resumen_agencias), use_container_width=True, hide_index=True)

            st.markdown("<h5 style='font-size: 14px; font-weight: 700; color: #eab308; margin-top: 12px;'>📜 Movimientos Recientes en Caja Supervisor</h5>", unsafe_allow_html=True)
            df_disp_movs = df_movs[["fecha", "agencia", "supervisor_nombre", "tipo_movimiento", "monto", "moneda_norm", "comentario"]].copy()
            df_disp_movs.columns = ["Fecha / Hora", "Agencia", "Supervisor", "Tipo Movimiento", "Monto", "Moneda", "Comentario / Cajero"]
            df_disp_movs["Monto"] = df_disp_movs["Monto"].apply(lambda m: f"{float(m):,.2f}")
            df_disp_movs = df_disp_movs.sort_values(by="Fecha / Hora", ascending=False)
            st.dataframe(df_disp_movs.head(50), use_container_width=True, hide_index=True)
        else:
            st.info("ℹ️ No hay movimientos registrados en la Caja de Efectivo del Supervisor aún.")

def modulo_pizarra(agencia_data=None):
    return modulo_pizarra_confirmaciones(agencia_data)

def modulo_pizarra_confirmaciones(agencia_data=None):
    st.markdown("""
        <style>
        .stMetric { background: rgba(255, 255, 255, 0.03); padding: 8px 12px !important; border-radius: 8px; border: 1px solid rgba(255,255,255,0.08); }
        .stMetric label { font-size: 0.75rem !important; opacity: 0.8; }
        .stMetric div[data-testid="stMetricValue"] { font-size: 1.2rem !important; font-weight: 700 !important; }
        .badge-pending { background-color: rgba(234, 179, 8, 0.15); color: #eab308; border: 1px solid rgba(234, 179, 8, 0.3); padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; }
        .badge-confirmed { background-color: rgba(34, 197, 94, 0.15); color: #22c55e; border: 1px solid rgba(34, 197, 94, 0.3); padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("<h3 style='font-size: 22px; font-weight: 700; margin-bottom: 2px;'>📌 Pizarra de Confirmaciones de Pagos y Gastos</h3>", unsafe_allow_html=True)
    st.caption("Verificación, auditoría y aprobación de **Transferencias**, **Punto de Venta**, **Gastos** y **Caja de Efectivo (Cajero ↔ Supervisor ↔ Admin)**.")

    cajero_info = st.session_state.get("cajero_actual", {})
    ag_info = agencia_data or st.session_state.get("agencia_actual", {})
    u_id = str(ag_info.get("user_id") or cajero_info.get("id") or "").strip()

    if not u_id and "user" in st.session_state and hasattr(st.session_state["user"], "id"):
        u_id = str(st.session_state["user"].id).strip()
    _check_confirmado_cols_cms()

    # Obtener período de trabajo actual (desde el último cierre)
    periodo_ciclo = obtener_periodo_trabajo(u_id)
    hoy = datetime.now().date()

    try:
        ciclo_desde_dt = datetime.strptime(str(periodo_ciclo.get("desde", "")).strip(), "%Y-%m-%d").date()
    except Exception:
        ciclo_desde_dt = hoy

    try:
        ciclo_hasta_dt = datetime.strptime(str(periodo_ciclo.get("hasta", "")).strip(), "%Y-%m-%d").date()
    except Exception:
        ciclo_hasta_dt = hoy

    ciclo_desde_str = str(ciclo_desde_dt)

    # Cargar agencias del usuario
    lista_agencias = ["Todas"]
    try:
        res_ag = supabase.table("agencias").select("nombre_agencia").eq("user_id", u_id).execute()
        if res_ag.data:
            ags = sorted([str(r["nombre_agencia"]).strip().upper() for r in res_ag.data if r.get("nombre_agencia")])
            lista_agencias.extend(ags)
    except Exception:
        pass

    # Cargar usuarios cajeros del usuario
    mapa_cajeros = {}
    lista_cajeros = ["Todos"]
    try:
        res_usr = supabase.table("taquilla_usuarios").select("id, usuario, nombre_cajero").eq("user_id", u_id).execute()
        if res_usr.data:
            for u in res_usr.data:
                cid = str(u["id"])
                unombre = u.get("nombre_cajero") or u.get("usuario") or f"Cajero {cid}"
                mapa_cajeros[cid] = unombre
                if unombre not in lista_cajeros:
                    lista_cajeros.append(unombre)
    except Exception:
        pass

    # Fetch total data from Supabase
    df_bancarios = pd.DataFrame()
    df_gastos = pd.DataFrame()
    df_pagos_diarios = pd.DataFrame()

    try:
        res_pb = supabase.table("cda_pagos_bancarios").select("*").execute()
        df_bancarios = pd.DataFrame(res_pb.data or [])
    except Exception:
        pass

    try:
        res_g = supabase.table("cda_gastos_diarios").select("*").execute()
        df_gastos = pd.DataFrame(res_g.data or [])
    except Exception:
        pass

    try:
        res_pd = supabase.table("cda_pagos_diarios").select("*").execute()
        df_pagos_diarios = pd.DataFrame(res_pd.data or [])
    except Exception:
        pass

    # Normalizar registros en una lista única de transacciones
    registros = []

    # 1. Pagos Bancarios
    if not df_bancarios.empty:
        df_bancarios.columns = [c.lower().strip() for c in df_bancarios.columns]
        for _, r in df_bancarios.iterrows():
            cid = str(r.get("cajero_id") or r.get("user_id") or "")
            c_nombre = mapa_cajeros.get(cid, f"ID {cid}" if cid else "Desconocido")
            metodo_raw = str(r.get("metodo_pago") or "Bancario").strip().upper()
            if "TRANSFERENCIA" in metodo_raw:
                metodo = "TRANSFERENCIA"
            else:
                metodo = metodo_raw
            
            cat_db = str(r.get("categoria") or "").strip()
            if cat_db:
                cat = cat_db
            elif "PUNTO" in metodo:
                cat = "Punto de Venta (Punde)"
            else:
                cat = "Transferencia / Zelle / Pago Móvil"

            is_conf = bool(r.get("confirmado", False))
            conf_por = str(r.get("confirmado_por") or r.get("confirmado_usuario") or r.get("usuario_confirmacion") or "").strip()

            registros.append({
                "id": r.get("id"),
                "tabla": "cda_pagos_bancarios",
                "fecha": str(r.get("fecha") or ""),
                "agencia": str(r.get("agencia") or "").upper(),
                "cajero_id": cid,
                "cajero_nombre": c_nombre,
                "categoria": cat,
                "metodo": metodo,
                "concepto": str(r.get("concepto") or "Pago Bancario"),
                "referencia": str(r.get("referencia") or "N/A"),
                "pagador": str(r.get("datos_pagador") or "N/A"),
                "dispositivo": str(r.get("pos_o_cuenta") or "N/A"),
                "monto": float(r.get("monto") or 0.0),
                "moneda": str(r.get("moneda") or "USD").upper(),
                "confirmado": is_conf,
                "confirmado_por": conf_por,
                "confirmado_supervisor": False,
                "supervisor_nombre": "",
                "comentario_supervisor": ""
            })

    # 2. Gastos
    if not df_gastos.empty:
        df_gastos.columns = [c.lower().strip() for c in df_gastos.columns]
        for _, r in df_gastos.iterrows():
            cid = str(r.get("cajero_id") or r.get("user_id") or "")
            c_nombre = mapa_cajeros.get(cid, f"ID {cid}" if cid else "Desconocido")
            ag_nom = str(r.get("agencia") or r.get("nombre_agency") or "").upper()
            is_conf = bool(r.get("confirmado", False))
            conf_por = str(r.get("confirmado_por") or r.get("confirmado_usuario") or r.get("usuario_confirmacion") or "").strip()

            registros.append({
                "id": r.get("id"),
                "tabla": "cda_gastos_diarios",
                "fecha": str(r.get("fecha") or ""),
                "agencia": ag_nom,
                "cajero_id": cid,
                "cajero_nombre": c_nombre,
                "categoria": "Gastos",
                "metodo": "GASTO",
                "concepto": str(r.get("concepto") or "Gasto"),
                "referencia": "N/A",
                "pagador": "N/A",
                "dispositivo": "N/A",
                "monto": float(r.get("monto") or 0.0),
                "moneda": str(r.get("moneda") or "USD").upper(),
                "confirmado": is_conf,
                "confirmado_por": conf_por,
                "confirmado_supervisor": False,
                "supervisor_nombre": "",
                "comentario_supervisor": ""
            })

    # 3. Pagos Efectivo de cda_pagos_diarios
    if not df_pagos_diarios.empty:
        df_pagos_diarios.columns = [c.lower().strip() for c in df_pagos_diarios.columns]
        for _, r in df_pagos_diarios.iterrows():
            tipo = str(r.get("tipo_pago") or "").upper()
            if "EFECTIVO" in tipo or ("REF:" not in tipo and "PUNTO" not in tipo and "TRANSFERENCIA" not in tipo and "ZELLE" not in tipo and "PAGO MÓVIL" not in tipo):
                cid = str(r.get("cajero_id") or r.get("user_id") or "")
                c_nombre = mapa_cajeros.get(cid, f"ID {cid}" if cid else "Desconocido")
                ag_nom = str(r.get("agencia") or r.get("nombre_agency") or "").upper()
                is_conf = bool(r.get("confirmado", False))
                conf_por = str(r.get("confirmado_por") or r.get("confirmado_usuario") or r.get("usuario_confirmacion") or "").strip()

                is_conf_sup = bool(r.get("confirmado_supervisor", False))
                sup_nom = str(r.get("supervisor_nombre") or "").strip()
                com_sup = str(r.get("comentario_supervisor") or "").strip()

                registros.append({
                    "id": r.get("id"),
                    "tabla": "cda_pagos_diarios",
                    "fecha": str(r.get("fecha") or ""),
                    "agencia": ag_nom,
                    "cajero_id": cid,
                    "cajero_nombre": c_nombre,
                    "categoria": "Efectivo",
                    "metodo": tipo or "EFECTIVO",
                    "concepto": "Pago Efectivo",
                    "referencia": "N/A",
                    "pagador": "N/A",
                    "dispositivo": "N/A",
                    "monto": float(r.get("monto") or 0.0),
                    "moneda": str(r.get("moneda") or "USD").upper(),
                    "confirmado": is_conf,
                    "confirmado_por": conf_por,
                    "confirmado_supervisor": is_conf_sup,
                    "supervisor_nombre": sup_nom,
                    "comentario_supervisor": com_sup
                })

    df_raw = pd.DataFrame(registros)

    if df_raw.empty:
        st.info("ℹ️ No hay transacciones registradas.")
        return

    df_raw["fecha_str"] = df_raw["fecha"].astype(str).str.slice(0, 10)

    df_activo = df_raw[(df_raw["confirmado"] == False) | (df_raw["fecha_str"] >= ciclo_desde_str)].copy()
    df_historial = df_raw[(df_raw["confirmado"] == True) & (df_raw["fecha_str"] < ciclo_desde_str)].copy()

    # Verificar si existe el rol supervisor en el sistema
    existe_sup = verificar_existe_supervisor(u_id)

    # ORGANIZACIÓN EN PESTAÑAS
    tab_names = [
        "📌 Pizarra Ciclo Activo", 
        "💵 Pizarra Efectivo (Cajero ↔ Supervisor) & Caja" if existe_sup else "💵 Pizarra Efectivo (Cajero) & Caja Chica", 
        "📜 Historial Mensual / Cierres Anteriores"
    ]
    tab_pizarra, tab_efectivo_sup, tab_historial = st.tabs(tab_names)

    # -------------------------------------------------------------
    # PESTAÑA 1: 📌 PIZARRA CICLO ACTIVO (ADMINISTRADOR / GENERAL)
    # -------------------------------------------------------------
    with tab_pizarra:
        f_hasta_default = max(hoy, ciclo_hasta_dt)
        col_chk, col_f1, col_f2, col_btn = st.columns([2, 2, 2, 2])
        with col_chk:
            usar_fechas = st.checkbox("📅 Filtrar por Fechas", value=True, key="pizarra_use_dates_act")
        with col_f1:
            f_desde = st.date_input("📅 Fecha Desde:", value=ciclo_desde_dt, key="pizarra_f_desde_act", disabled=not usar_fechas)
        with col_f2:
            f_hasta = st.date_input("📅 Fecha Hasta:", value=f_hasta_default, key="pizarra_f_hasta_act", disabled=not usar_fechas)
        with col_btn:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            if st.button("📌 Cargar Ciclo Actual", key="btn_reload_ciclo_act", use_container_width=True, help=f"Cargar desde el último cierre: {ciclo_desde_dt} al {f_hasta_default}"):
                st.session_state["pizarra_use_dates_act"] = True
                st.session_state["pizarra_f_desde_act"] = ciclo_desde_dt
                st.session_state["pizarra_f_hasta_act"] = f_hasta_default
                st.rerun()

        f_desde_str, f_hasta_str = str(f_desde), str(f_hasta)

        col_sel1, col_sel2, col_sel3, col_sel4 = st.columns([2, 2, 2, 2])
        sel_agencia = col_sel1.selectbox("🏢 Agencia:", lista_agencias, key="pizarra_agencia_sel_act")
        sel_cajero = col_sel2.selectbox("👤 Cajero:", lista_cajeros, key="pizarra_cajero_sel_act")
        sel_categoria = col_sel3.selectbox("💳 Categoría:", ["Todas", "Transferencia / Zelle / Pago Móvil", "Punto de Venta (Punde)", "Gastos", "Efectivo"], key="pizarra_cat_sel_act")
        sel_estado = col_sel4.selectbox("🚦 Estado:", ["⏳ Pendientes", "✅ Confirmados", "Todos"], key="pizarra_est_sel_act")

        df_act_work = df_activo.copy()

        if usar_fechas and not df_act_work.empty:
            df_act_work = df_act_work[(df_act_work["fecha_str"] >= f_desde_str) & (df_act_work["fecha_str"] <= f_hasta_str)]

        if sel_agencia != "Todas" and not df_act_work.empty:
            df_act_work = df_act_work[df_act_work["agencia"] == sel_agencia]

        if sel_cajero != "Todos" and not df_act_work.empty:
            df_act_work = df_act_work[df_act_work["cajero_nombre"] == sel_cajero]

        if sel_categoria != "Todas" and not df_act_work.empty:
            df_act_work = df_act_work[df_act_work["categoria"] == sel_categoria]

        df_act_metricas = df_act_work.copy()

        if sel_estado == "⏳ Pendientes" and not df_act_work.empty:
            # Los pagos en efectivo solo cuentan como pendientes del Admin si YA los recibió el Supervisor.
            # Si el supervisor no los ha recibido (confirmado_supervisor == False), pertenecen únicamente a la Pizarra del Supervisor.
            is_not_cash = df_act_work["categoria"] != "Efectivo"
            is_cash_ready_admin = (df_act_work["categoria"] == "Efectivo") & (df_act_work["confirmado_supervisor"] == True)
            df_act_work = df_act_work[(df_act_work["confirmado"] == False) & (is_not_cash | is_cash_ready_admin)]
        elif sel_estado == "✅ Confirmados" and not df_act_work.empty:
            df_act_work = df_act_work[df_act_work["confirmado"] == True]

        if "fecha" in df_act_work.columns and not df_act_work.empty:
            df_act_work = df_act_work.sort_values(by="fecha", ascending=False)

        st.markdown("---")
        _renderizar_resumen_metricas(df_act_metricas)
        st.markdown("---")

        st.markdown("<h4 style='font-size: 16px; font-weight: 700; margin-top: 10px;'>📋 Detalle de Transacciones (Ciclo Activo)</h4>", unsafe_allow_html=True)
        _renderizar_lista_transacciones(df_act_work, key_prefix="act", es_pizarra_supervisor=False, existe_supervisor=existe_sup)

    # -------------------------------------------------------------
    # PESTAÑA 2: 💵 PIZARRA EFECTIVO & CAJA CHICA (CAJERO / SUPERVISOR)
    # -------------------------------------------------------------
    with tab_efectivo_sup:
        if existe_sup:
            st.markdown("<h4 style='font-size: 17px; font-weight: 800; color: #22c55e;'>💵 Control de Efectivo: Cajero ➔ Supervisor ➔ Administrador</h4>", unsafe_allow_html=True)
            st.caption("Confirmación de entrega de efectivo por parte del Supervisor y acumulación en la Caja Chica del Supervisor antes de entregar al Administrador.")
        else:
            st.markdown("<h4 style='font-size: 17px; font-weight: 800; color: #22c55e;'>💵 Control de Efectivo: Cajero ➔ Administrador</h4>", unsafe_allow_html=True)
            st.caption("Control de caja chica de efectivo recaudado por el Cajero y acumulación para su liquidación al Administrador.")

        # Sección Superior: Caja de Efectivo Acumulada (Supervisor o Cajero)
        _renderizar_caja_acumulada_supervisor(u_id, existe_supervisor=existe_sup)
        st.markdown("---")

        if existe_sup:
            st.markdown("<h4 style='font-size: 16px; font-weight: 800; color: #eab308;'>📋 Entregas de Efectivo por Confirmar / Recibir (Supervisor)</h4>", unsafe_allow_html=True)
        else:
            st.markdown("<h4 style='font-size: 16px; font-weight: 800; color: #eab308;'>📋 Entregas de Efectivo en Caja del Cajero</h4>", unsafe_allow_html=True)

        col_es1, col_es2, col_es3 = st.columns([2, 2, 2])
        sel_ag_sup = col_es1.selectbox("🏢 Agencia (Efectivo):", lista_agencias, key="pizarra_ef_ag_sel")
        sel_caj_sup = col_es2.selectbox("👤 Cajero (Efectivo):", lista_cajeros, key="pizarra_ef_caj_sel")
        
        if existe_sup:
            sel_est_sup = col_es3.selectbox("🚦 Estado Supervisor:", ["⏳ Pendientes por Recibir", "🤝 Recibidos por Supervisor", "Todos"], key="pizarra_ef_est_sel")
        else:
            sel_est_sup = col_es3.selectbox("🚦 Estado Caja:", ["📦 En Caja de Cajero", "✅ Confirmados Admin", "Todos"], key="pizarra_ef_est_sel")

        df_ef_work = df_activo[df_activo["categoria"] == "Efectivo"].copy()

        if sel_ag_sup != "Todas" and not df_ef_work.empty:
            df_ef_work = df_ef_work[df_ef_work["agencia"] == sel_ag_sup]

        if sel_caj_sup != "Todos" and not df_ef_work.empty:
            df_ef_work = df_ef_work[df_ef_work["cajero_nombre"] == sel_caj_sup]

        if existe_sup:
            if sel_est_sup == "⏳ Pendientes por Recibir" and not df_ef_work.empty:
                df_ef_work = df_ef_work[(df_ef_work["confirmado_supervisor"] == False) & (df_ef_work["confirmado"] == False)]
            elif sel_est_sup == "🤝 Recibidos por Supervisor" and not df_ef_work.empty:
                df_ef_work = df_ef_work[df_ef_work["confirmado_supervisor"] == True]
        else:
            if sel_est_sup == "📦 En Caja de Cajero" and not df_ef_work.empty:
                df_ef_work = df_ef_work[df_ef_work["confirmado"] == False]
            elif sel_est_sup == "✅ Confirmados Admin" and not df_ef_work.empty:
                df_ef_work = df_ef_work[df_ef_work["confirmado"] == True]

        if "fecha" in df_ef_work.columns and not df_ef_work.empty:
            df_ef_work = df_ef_work.sort_values(by="fecha", ascending=False)

        _renderizar_lista_transacciones(df_ef_work, key_prefix="ef_sup", es_pizarra_supervisor=True, existe_supervisor=existe_sup)

    # -------------------------------------------------------------
    # PESTAÑA 3: 📜 HISTORIAL MENSUAL / CIERRES ANTERIORES
    # -------------------------------------------------------------
    with tab_historial:
        st.caption("📜 Transacciones confirmadas de cierres y meses anteriores al último ciclo activo.")

        col_h1, col_h2, col_h3, col_h4 = st.columns([2, 2, 2, 2])
        sel_ag_hist = col_h1.selectbox("🏢 Agencia:", lista_agencias, key="hist_ag_sel")
        sel_caj_hist = col_h2.selectbox("👤 Cajero:", lista_cajeros, key="hist_caj_sel")
        sel_cat_hist = col_h3.selectbox("💳 Categoría:", ["Todas", "Transferencia / Zelle / Pago Móvil", "Punto de Venta (Punde)", "Gastos", "Efectivo"], key="hist_cat_sel")
        
        hoy_hist = datetime.now().date()
        f_hist_desde = col_h4.date_input("📅 Desde (Historial):", value=hoy_hist.replace(day=1), key="hist_f_desde")

        df_hist_work = df_historial.copy()

        if not df_hist_work.empty:
            f_h_str = str(f_hist_desde)
            df_hist_work = df_hist_work[df_hist_work["fecha_str"] >= f_h_str]

            if sel_ag_hist != "Todas":
                df_hist_work = df_hist_work[df_hist_work["agencia"] == sel_ag_hist]

            if sel_caj_hist != "Todos":
                df_hist_work = df_hist_work[df_hist_work["cajero_nombre"] == sel_caj_hist]

            if sel_cat_hist != "Todas":
                df_hist_work = df_hist_work[df_hist_work["categoria"] == sel_cat_hist]

            if "fecha" in df_hist_work.columns:
                df_hist_work = df_hist_work.sort_values(by="fecha", ascending=False)

        st.markdown("---")
        st.markdown("<h5 style='font-size: 15px; font-weight: 800; color: #a855f7; margin-bottom: 8px;'>🏛️ Totales Confirmados en Historial Anteriores</h5>", unsafe_allow_html=True)
        _renderizar_resumen_metricas(df_hist_work)
        st.markdown("---")

        st.markdown("<h4 style='font-size: 16px; font-weight: 700; margin-top: 10px;'>📜 Transacciones Confirmadas (Historial)</h4>", unsafe_allow_html=True)
        _renderizar_lista_transacciones(df_hist_work, key_prefix="hist", es_pizarra_supervisor=False, existe_supervisor=existe_sup)
