from modulo_firma_digital import renderizar_canvas_firma, renderizar_comprobante_firma
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

def _dummy_old_user_fn():
    
    """Retorna el nombre o identificador legible del usuario que realiza la confirmación."""
    if "sub_user" in st.session_state and st.session_state["sub_user"]:
        u = st.session_state["sub_user"]
        return u.get("nombre") or u.get("usuario") or u.get("email") or "Usuario CMS"
    if "perfil" in st.session_state and st.session_state["perfil"]:
        p = st.session_state["perfil"]
        return p.get("nombre") or p.get("usuario") or p.get("email") or "Usuario CMS"
    if "user" in st.session_state:
        u_obj = st.session_state["user"]
        if hasattr(u_obj, "email") and u_obj.email:
            return u_obj.email.split("@")[0]
    return "Usuario CMS"

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
    try:
        supabase.table("cda_caja_efectivo_supervisor").select("id").limit(1).execute()
    except Exception:
        caja_sup_existe = False

    if tablas_faltantes or cols_sup_faltantes or not caja_sup_existe:
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
            sql_lines.append("ALTER TABLE cda_pagos_diarios ADD COLUMN IF NOT EXISTS firma_supervisor_base64 TEXT;")
            sql_lines.append("ALTER TABLE cda_pagos_diarios ADD COLUMN IF NOT EXISTS firma_cajero_base64 TEXT;")
            sql_lines.append("ALTER TABLE cda_caja_efectivo_supervisor ADD COLUMN IF NOT EXISTS firma_supervisor_base64 TEXT;")

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

def _renderizar_lista_transacciones(df_list, key_prefix="act", es_pizarra_supervisor=False):
    if df_list.empty:
        st.info("ℹ️ No hay transacciones que coincidan con los filtros seleccionados.")
        return

    for idx_pos, (idx, row) in enumerate(df_list.iterrows(), start=1):
        is_c = row["confirmado"]
        conf_por = str(row.get("confirmado_por") or "").strip()
        
        is_c_sup = bool(row.get("confirmado_supervisor", False))
        sup_nom = str(row.get("supervisor_nombre") or "").strip()
        com_sup = str(row.get("comentario_supervisor") or "").strip()

        badge_html = "<span class='badge-confirmed'>✅ CONFIRMADO <sup style='background:#1b4332; color:#52b788; border-radius:3px; padding:1px 4px; font-weight:bold;'>C</sup></span>" if is_c else "<span class='badge-pending'>⏳ PENDIENTE</span>"
        conf_info_html = f"<br><small style='color: #22c55e; font-weight: 600;'>👤 Confirmado Admin: <b>{conf_por}</b></small>" if (is_c and conf_por) else ""
        
        sup_info_html = ""
        if is_c_sup or sup_nom:
            nota_sup = f" | {com_sup}" if com_sup else ""
            sup_info_html = f"<br><small style='color: #38bdf8; font-weight: 700; background: rgba(56, 189, 248, 0.12); padding: 2px 6px; border-radius: 4px; border: 1px solid rgba(56, 189, 248, 0.25); display: inline-block; margin-top: 3px;'>💬 Entregado a Supervisor: <b>{sup_nom or 'Supervisor'}</b>{nota_sup}</small>"
        
        firma_sup_b64 = str(row.get("firma_supervisor_base64") or "").strip()

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
                    badge_sup_state = "<br><span style='background-color: rgba(56, 189, 248, 0.15); color: #38bdf8; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 700;'>🤝 RECIBIDO SUPERVISOR</span>" if is_c_sup else "<br><span style='background-color: rgba(234, 179, 8, 0.15); color: #eab308; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 700;'>⏳ PEND. SUPERVISOR</span>"

                st.markdown(
                    f"<div style='text-align: right; padding-right: 10px;'>"
                    f"<span style='font-size: 16px; font-weight: 800;'>{row['moneda']} {row['monto']:,.2f}</span><br>"
                    f"{badge_html}"
                    f"{badge_sup_state}"
                    f"</div>",
                    unsafe_allow_html=True
                )

            if firma_sup_b64:
                with st.expander("🔏 Ver Comprobante con Firma Digital"):
                    renderizar_comprobante_firma(firma_sup_b64, supervisor_nombre=sup_nom or "Supervisor", fecha_str=str(row.get("fecha") or ""), monto_str=f"{row['monto']:,.2f}", moneda_str=row['moneda'])

            with c_action:
                btn_key = f"btn_conf_{key_prefix}_{row['tabla']}_{row['id']}"
                
                # Flujo Supervisor si estamos en la Pizarra de Efectivo Cajero<->Supervisor
                if es_pizarra_supervisor and row["categoria"] == "Efectivo":
                    if not is_c_sup:
                        with st.popover("🤝 Confirmar con Firma", use_container_width=True):
                            st.markdown(f"##### 🔏 Recepción de Efectivo: {row['moneda']} {row['monto']:,.2f}")
                            st.caption(f"Cajero: **{row['cajero_nombre']}** | Agencia: **{row['agencia']}**")
                            
                            current_usr = obtener_nombre_usuario_actual()
                            com_input = st.text_input("Nota / Comentario del Supervisor:", value=f"Recibido de cajero {row['cajero_nombre']}", key=f"nota_sup_{row['id']}")
                            
                            st.markdown("---")
                            firma_captured = renderizar_canvas_firma(key=f"sig_pizarra_{row['id']}", titulo="✍️ Firma Digital del Supervisor")
                            
                            if st.button("✅ Confirmar y Registrar Recepción", key=f"btn_save_sig_{row['id']}", use_container_width=True, type="primary"):
                                try:
                                    f_time = datetime.now().isoformat()
                                    data_sup = {
                                        "confirmado_supervisor": True,
                                        "supervisor_nombre": current_usr,
                                        "comentario_supervisor": com_input,
                                        "fecha_confirmacion_supervisor": f_time,
                                        "firma_supervisor_base64": firma_captured or None
                                    }
                                    supabase.table("cda_pagos_diarios").update(data_sup).eq("id", row["id"]).execute()
                                    
                                    # Registrar entrada en Caja de Efectivo del Supervisor
                                    try:
                                        supabase.table("cda_caja_efectivo_supervisor").insert({
                                            "user_id": str(st.session_state.get("user", {}).id if hasattr(st.session_state.get("user"), "id") else ""),
                                            "agencia": row["agencia"],
                                            "supervisor_nombre": current_usr,
                                            "tipo_movimiento": "ENTRADA_CAJERO",
                                            "monto": float(row["monto"]),
                                            "moneda": str(row["moneda"]).upper(),
                                            "pago_id": row["id"],
                                            "comentario": com_input,
                                            "firma_supervisor_base64": firma_captured or None
                                        }).execute()
                                    except Exception:
                                        pass

                                    st.success(f"🤝 Efectivo y Firma validados correctamente por Supervisor {current_usr}")
                                    time.sleep(0.5)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Error al confirmar: {e}")
                    else:
                        st.info(f"🤝 Recibido por: {sup_nom or 'Supervisor'}")

                # Flujo Administrador / General
                else:
                    if not is_c:
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

def _renderizar_caja_acumulada_supervisor(u_id):
    """Muestra la Caja Chica / Caja Acumulable de Efectivo del Supervisor con botón de liquidación a Administración."""
    st.markdown("<h4 style='font-size: 16px; font-weight: 800; color: #38bdf8; margin-top: 10px;'>📦 Caja Acumulable de Efectivo del Supervisor</h4>", unsafe_allow_html=True)
    st.caption("Efectivo recibido de Cajeros pendiente por entregar / liquidar al Administrador.")

    totales_caja = {"BS": 0.0, "USD": 0.0, "COP": 0.0}
    
    try:
        res_movs = supabase.table("cda_caja_efectivo_supervisor").select("*").execute()
        if res_movs.data:
            df_movs = pd.DataFrame(res_movs.data)
            for m in ["BS", "USD", "COP"]:
                entradas = df_movs[(df_movs["moneda"].str.upper() == m) & (df_movs["tipo_movimiento"] == "ENTRADA_CAJERO")]["monto"].sum()
                salidas = df_movs[(df_movs["moneda"].str.upper() == m) & (df_movs["tipo_movimiento"] == "ENTREGA_ADMIN")]["monto"].sum()
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
        with st.popover("💸 Entregar al Administrador", use_container_width=True):
            st.markdown("##### 💸 Liquidación de Efectivo al Administrador")
            moneda_liq = st.selectbox("Moneda:", ["USD", "BS", "COP"], key="liq_moneda_sup")
            monto_liq = st.number_input(f"Monto a Entregar ({moneda_liq}):", min_value=0.0, value=float(totales_caja.get(moneda_liq, 0.0)), key="liq_monto_sup")
            nota_liq = st.text_input("Nota / Comentario:", value=f"Entrega de caja acumulada a Administración", key="liq_nota_sup")
            
            if st.button("🚀 Confirmar Entrega a Admin", key="btn_confirm_liq_admin", use_container_width=True):
                if monto_liq <= 0:
                    st.error("⚠️ El monto a entregar debe ser mayor a 0.")
                else:
                    curr_usr = obtener_nombre_usuario_actual()
                    try:
                        supabase.table("cda_caja_efectivo_supervisor").insert({
                            "user_id": u_id,
                            "agencia": "TODAS",
                            "supervisor_nombre": curr_usr,
                            "tipo_movimiento": "ENTREGA_ADMIN",
                            "monto": float(monto_liq),
                            "moneda": moneda_liq,
                            "comentario": nota_liq
                        }).execute()
                        st.success(f"✅ Liquidación de {moneda_liq} {monto_liq:,.2f} registrada correctamente al Administrador por {curr_usr}.")
                        time.sleep(0.5)
                        st.rerun()
                    except Exception as ex_l:
                        st.error(f"❌ Error al registrar liquidación: {ex_l}")

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
                    "comentario_supervisor": com_sup,
                    "firma_supervisor_base64": r.get("firma_supervisor_base64") or "",
                    "firma_cajero_base64": r.get("firma_cajero_base64") or ""
                })

    df_raw = pd.DataFrame(registros)

    if df_raw.empty:
        st.info("ℹ️ No hay transacciones registradas.")
        return

    df_raw["fecha_str"] = df_raw["fecha"].astype(str).str.slice(0, 10)

    df_activo = df_raw[(df_raw["confirmado"] == False) | (df_raw["fecha_str"] >= ciclo_desde_str)].copy()
    df_historial = df_raw[(df_raw["confirmado"] == True) & (df_raw["fecha_str"] < ciclo_desde_str)].copy()

    # ORGANIZACIÓN EN PESTAÑAS
    tab_pizarra, tab_efectivo_sup, tab_historial = st.tabs([
        "📌 Pizarra Ciclo Activo", 
        "💵 Pizarra Efectivo (Cajero ↔ Supervisor) & Caja", 
        "📜 Historial Mensual / Cierres Anteriores"
    ])

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
            df_act_work = df_act_work[df_act_work["confirmado"] == False]
        elif sel_estado == "✅ Confirmados" and not df_act_work.empty:
            df_act_work = df_act_work[df_act_work["confirmado"] == True]

        if "fecha" in df_act_work.columns and not df_act_work.empty:
            df_act_work = df_act_work.sort_values(by="fecha", ascending=False)

        st.markdown("---")
        _renderizar_resumen_metricas(df_act_metricas)
        st.markdown("---")

        st.markdown("<h4 style='font-size: 16px; font-weight: 700; margin-top: 10px;'>📋 Detalle de Transacciones (Ciclo Activo)</h4>", unsafe_allow_html=True)
        _renderizar_lista_transacciones(df_act_work, key_prefix="act", es_pizarra_supervisor=False)

    # -------------------------------------------------------------
    # PESTAÑA 2: 💵 PIZARRA EFECTIVO (CAJERO <-> SUPERVISOR) & CAJA
    # -------------------------------------------------------------
    with tab_efectivo_sup:
        st.markdown("<h4 style='font-size: 17px; font-weight: 800; color: #22c55e;'>💵 Control de Efectivo: Cajero ➔ Supervisor ➔ Administrador</h4>", unsafe_allow_html=True)
        st.caption("Confirmación de entrega de efectivo por parte del Supervisor y acumulación en la Caja Chica del Supervisor antes de entregar al Administrador.")

        # Sección Superior: Caja de Efectivo Acumulada del Supervisor
        _renderizar_caja_acumulada_supervisor(u_id)
        st.markdown("---")

        st.markdown("<h4 style='font-size: 16px; font-weight: 800; color: #eab308;'>📋 Entregas de Efectivo por Confirmar / Recibir (Supervisor)</h4>", unsafe_allow_html=True)

        col_es1, col_es2, col_es3 = st.columns([2, 2, 2])
        sel_ag_sup = col_es1.selectbox("🏢 Agencia (Efectivo):", lista_agencias, key="pizarra_ef_ag_sel")
        sel_caj_sup = col_es2.selectbox("👤 Cajero (Efectivo):", lista_cajeros, key="pizarra_ef_caj_sel")
        sel_est_sup = col_es3.selectbox("🚦 Estado Supervisor:", ["⏳ Pendientes por Recibir", "🤝 Recibidos por Supervisor", "Todos"], key="pizarra_ef_est_sel")

        df_ef_work = df_activo[df_activo["categoria"] == "Efectivo"].copy()

        if sel_ag_sup != "Todas" and not df_ef_work.empty:
            df_ef_work = df_ef_work[df_ef_work["agencia"] == sel_ag_sup]

        if sel_caj_sup != "Todos" and not df_ef_work.empty:
            df_ef_work = df_ef_work[df_ef_work["cajero_nombre"] == sel_caj_sup]

        if sel_est_sup == "⏳ Pendientes por Recibir" and not df_ef_work.empty:
            df_ef_work = df_ef_work[df_ef_work["confirmado_supervisor"] == False]
        elif sel_est_sup == "🤝 Recibidos por Supervisor" and not df_ef_work.empty:
            df_ef_work = df_ef_work[df_ef_work["confirmado_supervisor"] == True]

        if "fecha" in df_ef_work.columns and not df_ef_work.empty:
            df_ef_work = df_ef_work.sort_values(by="fecha", ascending=False)

        _renderizar_lista_transacciones(df_ef_work, key_prefix="ef_sup", es_pizarra_supervisor=True)

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
        _renderizar_lista_transacciones(df_hist_work, key_prefix="hist", es_pizarra_supervisor=False)
