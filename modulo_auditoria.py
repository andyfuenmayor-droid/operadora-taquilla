import streamlit as st
import pandas as pd
from utils import supabase, obtener_periodo_trabajo, obtener_etiqueta_confirmacion

def modulo_auditoria_hibrida(agencia_data=None):
    st.header("🛡️ Panel de Auditoría Híbrida (Taquilla vs Carga Oficial)")
    st.caption("Comparativa por **ciclo completo**: Oficial vs Taquilla, incluyendo gestión multiusuario integrada.")

    try:
        u_id = None
        if agencia_data and "user_id" in agencia_data and agencia_data["user_id"]:
            u_id = str(agencia_data["user_id"]).strip()
        elif "user" in st.session_state and hasattr(st.session_state["user"], "id"):
            u_id = str(st.session_state["user"].id).strip()
        elif "user" in st.session_state and isinstance(st.session_state["user"], dict):
            u_id = str(st.session_state["user"].get("id", "")).strip()
        elif "agencia_actual" in st.session_state:
            u_id = str(st.session_state["agencia_actual"].get("user_id", "")).strip()

        if not u_id:
            st.warning("⚠️ No se pudo determinar el ID de usuario administrador para la auditoría.")
            return

        ciclo = obtener_periodo_trabajo(u_id)
        f_desde_str, f_hasta_str = ciclo['desde'], ciclo['hasta']

        res_ag = supabase.table("agencias").select("id, nombre_agencia, auditoria_activa, participacion_ag, sistemas, monedas, usuario_taquilla").eq("user_id", u_id).execute()
        df_agencias = pd.DataFrame(res_ag.data or [])

        agencias_auditables = []
        diccionario_part = {}
        if not df_agencias.empty:
            df_agencias.columns = [c.lower().strip() for c in df_agencias.columns]
            df_agencias = df_agencias.sort_values(by="id", ascending=True).reset_index(drop=True)
            agencias_auditables = df_agencias[df_agencias.get("auditoria_activa", False) == True]["nombre_agencia"].astype(str).str.upper().str.strip().tolist()
            df_agencias["agencia_limpia"] = df_agencias["nombre_agencia"].astype(str).str.upper().str.strip()
            df_agencias["participacion_ag"] = pd.to_numeric(df_agencias.get("participacion_ag", 0), errors='coerce').fillna(0.0)
            diccionario_part = dict(zip(df_agencias["agencia_limpia"], df_agencias["participacion_ag"]))

        df_oficial = pd.DataFrame(supabase.table("carga_actual").select("*").eq("user_id", u_id).execute().data or [])
        df_taq_periodo = pd.DataFrame(supabase.table("cda_reportes_diarios").select("*").gte("fecha", f_desde_str).lte("fecha", f_hasta_str).execute().data or [])
        df_gastos_periodo = pd.DataFrame(supabase.table("cda_gastos_diarios").select("*").gte("fecha", f_desde_str).lte("fecha", f_hasta_str).execute().data or [])
        df_pagos_periodo = pd.DataFrame(supabase.table("cda_pagos_diarios").select("*").gte("fecha", f_desde_str).lte("fecha", f_hasta_str).execute().data or [])

        df_taq_periodo = df_taq_periodo[df_taq_periodo['fecha'].apply(lambda x: str(x) >= '2026-06-29')] if not df_taq_periodo.empty else df_taq_periodo
        df_gastos_periodo = df_gastos_periodo[df_gastos_periodo['fecha'].apply(lambda x: str(x) >= '2026-06-29')] if not df_gastos_periodo.empty else df_gastos_periodo
        df_pagos_periodo = df_pagos_periodo[df_pagos_periodo['fecha'].apply(lambda x: str(x) >= '2026-06-29')] if not df_pagos_periodo.empty else df_pagos_periodo

        df_oficial_gastos = pd.DataFrame(supabase.table("gastos").select("*").eq("user_id", u_id).gte("fecha", f_desde_str).lte("fecha", f_hasta_str).execute().data or [])
        res_ofic_p = supabase.table("pagos_semana").select("*").eq("user_id", u_id).execute()
        df_oficial_pagos = pd.DataFrame(res_ofic_p.data or [])
        if not df_oficial_pagos.empty and "fecha" in df_oficial_pagos.columns:
            f_subs = df_oficial_pagos["fecha"].astype(str).str.slice(0, 10)
            df_oficial_pagos = df_oficial_pagos[(f_subs >= f_desde_str) & (f_subs <= f_hasta_str)]

        # Normalizar moneda de reportes de taquilla si la agencia solo opera en una moneda (ej: BS)
        mapa_moneda_unica_ag = {}
        if not df_agencias.empty and "monedas" in df_agencias.columns:
            for _, r_ag in df_agencias.iterrows():
                ag_n = str(r_ag["nombre_agencia"]).strip().upper()
                mons = [m.strip().upper() for m in str(r_ag.get("monedas", "")).split(",") if m.strip()]
                if len(mons) == 1:
                    mapa_moneda_unica_ag[ag_n] = mons[0]

        if not df_taq_periodo.empty:
            col_ag_ref = "agencia" if "agencia" in df_taq_periodo.columns else ("nombre_agency" if "nombre_agency" in df_taq_periodo.columns else None)
            def fix_moneda_taq(row):
                m_actual = str(row.get("moneda") or "").strip().upper()
                ag_n = str(row.get(col_ag_ref) or "").strip().upper() if col_ag_ref else ""
                if ag_n in mapa_moneda_unica_ag and (not m_actual or (m_actual == "COP" and mapa_moneda_unica_ag[ag_n] != "COP")):
                    return mapa_moneda_unica_ag[ag_n]
                return m_actual if m_actual else mapa_moneda_unica_ag.get(ag_n, "BS")

            df_taq_periodo["moneda"] = df_taq_periodo.apply(fix_moneda_taq, axis=1)

        for df in [df_oficial, df_taq_periodo, df_gastos_periodo, df_pagos_periodo, df_oficial_gastos, df_oficial_pagos]:
            if not df.empty:
                df.columns = [c.lower().strip() for c in df.columns]

        if not df_taq_periodo.empty and 'fecha' in df_taq_periodo.columns:
            df_taq_periodo['fecha'] = pd.to_datetime(df_taq_periodo['fecha']).dt.date
        if not df_gastos_periodo.empty and 'fecha' in df_gastos_periodo.columns:
            df_gastos_periodo['fecha'] = pd.to_datetime(df_gastos_periodo['fecha']).dt.date
        if not df_pagos_periodo.empty and 'fecha' in df_pagos_periodo.columns:
            df_pagos_periodo['fecha'] = pd.to_datetime(df_pagos_periodo['fecha']).dt.date

    except Exception as e:
        st.error(f"Error de conexion o datos: {e}")
        return

    with st.expander("Gestion de Credenciales por Terminal", expanded=False):
        st.caption("Administra, crea y modifica las credenciales individuales de cajeros o supervisores por agencia.")
        if not df_agencias.empty:
            for idx, row in df_agencias.iterrows():
                ag_id = row['id']
                ag_nombre = str(row['nombre_agencia']).upper()
                usuarios_agencia = []
                try:
                    res_u = supabase.table("taquilla_usuarios").select("*").eq("agencia_id", ag_id).execute()
                    usuarios_agencia = res_u.data or []
                except Exception:
                    pass
                with st.container(border=True):
                    c_main, c_usuarios, c_accion = st.columns([3, 4, 2])
                    with c_main:
                        st.markdown(f"**{ag_nombre}**")
                    with c_usuarios:
                        if usuarios_agencia:
                            def _get_rol_tag_taq(r_val):
                                r_c = str(r_val or '').lower().strip()
                                if r_c == 'supervisor': return 'S'
                                elif r_c == 'agencia': return 'A'
                                return 'C'
                            txt = ", ".join([f"`{u['usuario']}` ({_get_rol_tag_taq(u.get('rol'))})" for u in usuarios_agencia if u.get('activo')])
                            st.markdown(txt if txt else "Sin usuarios activos")
                        else:
                            st.markdown("Sin usuarios")
                    with c_accion:
                        if st.button("➕ Nuevo", key=f"nuevo_{ag_id}", use_container_width=True):
                            st.session_state[f"show_form_{ag_id}"] = True
                    if st.session_state.get(f"show_form_{ag_id}", False):
                        with st.form(key=f"form_create_{ag_id}", clear_on_submit=True):
                            col1, col2 = st.columns(2)
                            with col1:
                                nu = st.text_input("Usuario", key=f"nu_{ag_id}", placeholder="ej: cajero01")
                                np_ = st.text_input("Clave", type="password", key=f"np_{ag_id}")
                            with col2:
                                n_cajero = st.text_input("Nombre (opcional)", key=f"nom_{ag_id}")
                                rol_new = st.selectbox("Rol", ["cajero", "supervisor", "agencia"], key=f"rol_{ag_id}")
                            col_btn1, col_btn2 = st.columns([1, 1])
                            with col_btn1:
                                if st.form_submit_button("💾 Guardar", use_container_width=True):
                                    if nu and np_:
                                        try:
                                            data = {"usuario": nu.strip(), "clave": np_.strip(), "rol": rol_new, "agencia_id": int(ag_id), "activo": True}
                                            if n_cajero.strip():
                                                data["nombre_cajero"] = n_cajero.strip()
                                            supabase.table("taquilla_usuarios").insert(data).execute()
                                            st.success(f"Usuario '{nu}' creado")
                                            st.session_state[f"show_form_{ag_id}"] = False
                                            st.rerun()
                                        except Exception as ex:
                                            st.error(f"Error: {ex}")
                                    else:
                                        st.warning("Usuario y clave requeridos")
                            with col_btn2:
                                if st.form_submit_button("❌ Cancelar", use_container_width=True):
                                    st.session_state[f"show_form_{ag_id}"] = False
                                    st.rerun()
                    for u in usuarios_agencia:
                        uid = u['id']
                        with st.popover(f"✏️ {u['usuario']}", key=f"pop_{ag_id}_{uid}"):
                            col_a, col_b = st.columns(2)
                            with col_a:
                                roles_lista = ["cajero", "supervisor", "agencia"]
                                u_rol = str(u.get('rol', 'cajero')).lower()
                                idx_r = roles_lista.index(u_rol) if u_rol in roles_lista else 0
                                nuevo_rol = st.selectbox("Rol", roles_lista, index=idx_r, key=f"rol_edit_{uid}")
                                nuevo_activo = st.checkbox("Activo", value=u.get('activo', True), key=f"act_{uid}")
                                if st.button("💾 Actualizar", key=f"upd_{uid}", use_container_width=True):
                                    try:
                                        supabase.table("taquilla_usuarios").update({"rol": nuevo_rol, "activo": nuevo_activo}).eq("id", uid).execute()
                                        st.success("Actualizado")
                                        st.rerun()
                                    except Exception as ex:
                                        st.error(f"Error: {ex}")
                            with col_b:
                                nueva_clave = st.text_input("Nueva clave", type="password", key=f"clave_{uid}", placeholder="dejar vacio = sin cambio")
                                if st.button("🔑 Cambiar Clave", key=f"chpwd_{uid}", use_container_width=True):
                                    if nueva_clave:
                                        try:
                                            supabase.table("taquilla_usuarios").update({"clave": nueva_clave.strip()}).eq("id", uid).execute()
                                            st.success("Clave actualizada")
                                            st.rerun()
                                        except Exception as ex:
                                            st.error(f"Error: {ex}")
                                    else:
                                        st.warning("Ingresa una nueva clave")
                            if st.button("🗑️ Eliminar", key=f"del_{uid}", use_container_width=True, type="secondary"):
                                try:
                                    supabase.table("taquilla_usuarios").delete().eq("id", uid).execute()
                                    st.success(f"Usuario '{u['usuario']}' eliminado")
                                    st.rerun()
                                except Exception as ex:
                                    st.error(f"Error: {ex}")

    st.markdown("---")
    st.subheader(f"Comparativa por Ciclo Completo: {f_desde_str} al {f_hasta_str}")

    def agrupar(df, moneda, cols, ag_col):
        if df.empty:
            return pd.DataFrame(columns=["agencia", "sistema"] + cols)
        df_w = df.copy()
        for c in cols:
            if c not in df_w.columns:
                df_w[c] = 0.0
        if "moneda" in df_w.columns:
            df_w = df_w[df_w["moneda"].astype(str).str.upper().str.strip() == str(moneda).upper()].copy()
        if ag_col in df_w.columns and ag_col != "agencia":
            if "agencia" in df_w.columns:
                df_w = df_w.drop(columns=["agencia"])
            df_w = df_w.rename(columns={ag_col: "agencia"})
        elif "agencia" not in df_w.columns:
            df_w["agencia"] = "N/A"
        df_w["agencia"] = df_w["agencia"].astype(str).str.upper().str.strip()
        df_w["sistema"] = df_w["sistema"].astype(str).str.upper().str.strip() if "sistema" in df_w.columns else "N/A"
        for c in cols:
            df_w[c] = pd.to_numeric(df_w[c], errors='coerce').fillna(0)
        return df_w.groupby(["agencia", "sistema"])[cols].sum().reset_index()

    def proc_simple(df, moneda, val_col, ag_col):
        if df.empty:
            return pd.DataFrame(columns=["agencia", val_col])
        df_w = df.copy()
        if "moneda" in df_w.columns:
            df_w = df_w[df_w["moneda"].astype(str).str.upper().str.strip() == str(moneda).upper()].copy()
        if ag_col in df_w.columns and ag_col != "agencia":
            if "agencia" in df_w.columns:
                df_w = df_w.drop(columns=["agencia"])
            df_w = df_w.rename(columns={ag_col: "agencia"})
        elif "agencia" not in df_w.columns:
            df_w["agencia"] = "N/A"
        df_w["agencia"] = df_w["agencia"].astype(str).str.upper().str.strip()
        if val_col not in df_w.columns:
            df_w[val_col] = 0.0
        df_w[val_col] = pd.to_numeric(df_w[val_col], errors='coerce').fillna(0)
        return df_w.groupby("agencia")[val_col].sum().reset_index()

    monedas_disponibles = ["BS", "USD", "COP"]
    pestanas = st.tabs([f"{m}" for m in monedas_disponibles])

    for i, m_search in enumerate(monedas_disponibles):
        with pestanas[i]:
            df_of = agrupar(df_oficial, m_search, ["venta", "premios", "comision", "util_ag"], "agencia")
            df_taq_agrupado = agrupar(df_taq_periodo, m_search, ["monto_venta", "monto_premios", "comision"], "nombre_agency").rename(
                columns={"monto_venta": "venta_taq", "monto_premios": "premios_taq", "comision": "comision_taq"}
            )
            df_g = proc_simple(df_gastos_periodo, m_search, "monto", "agencia").rename(columns={"monto": "gastos_taq"})
            df_p = proc_simple(df_pagos_periodo, m_search, "monto", "agencia").rename(columns={"monto": "pagos_taq"})
            df_g_oficial = proc_simple(df_oficial_gastos, m_search, "monto", "agencia").rename(columns={"monto": "gastos_ofi"})
            df_p_oficial = proc_simple(df_oficial_pagos, m_search, "monto", "agencia").rename(columns={"monto": "pagos_ofi"})

            df_final = pd.merge(df_of, df_taq_agrupado, on=["agencia", "sistema"], how="outer").fillna(0.0)
            df_final = pd.merge(df_final, df_g, on="agencia", how="left").fillna(0.0)
            df_final = pd.merge(df_final, df_p, on="agencia", how="left").fillna(0.0)
            df_final = pd.merge(df_final, df_g_oficial, on="agencia", how="left").fillna(0.0)
            df_final = pd.merge(df_final, df_p_oficial, on="agencia", how="left").fillna(0.0)

            if agencias_auditables:
                df_final = df_final[df_final["agencia"].isin(agencias_auditables)]

            for col in ["gastos_ofi", "pagos_ofi", "gastos_taq", "pagos_taq", "util_ag"]:
                if col not in df_final.columns:
                    df_final[col] = 0.0

            df_final["pct"] = df_final["agencia"].map(diccionario_part).fillna(0.0)
            df_final["part_taq"] = (df_final["venta_taq"] - df_final["comision_taq"] - df_final["premios_taq"]) * (df_final["pct"] / 100)

            if df_final.empty or len(df_final) == 0:
                st.info(f"No hay movimientos registrados en {m_search} para este ciclo.")
            else:
                cols_display = {
                    "agencia": "Agencia", "sistema": "Sistema",
                    "venta": "Venta Ofi", "venta_taq": "Venta Taq",
                    "comision": "Com Ofi", "comision_taq": "Com Taq",
                    "premios": "Prem Ofi", "premios_taq": "Prem Taq",
                    "util_ag": "Part Ofi", "part_taq": "Part Taq",
                    "gastos_ofi": "Gto Ofi", "gastos_taq": "Gto Taq",
                    "pagos_ofi": "Pag Ofi", "pagos_taq": "Pag Taq",
                }
                cols_presentes = [v for v in cols_display.values() if list(cols_display.keys())[list(cols_display.values()).index(v)] in df_final.columns]
                df_show = df_final.rename(columns=cols_display)[cols_presentes]
                st.dataframe(
                    df_show.style.format("{:,.2f}", subset=[c for c in cols_presentes if c not in ("Agencia", "Sistema")]),
                    use_container_width=True, hide_index=True
                )

                st.markdown(f"#### Totales por Sistema en {m_search} (Ciclo Completo)")
                metric_pairs = [
                    ("Ventas",  "venta",      "venta_taq"),
                    ("Comis.",  "comision",   "comision_taq"),
                    ("Premios", "premios",    "premios_taq"),
                ]
                sistemas = sorted(set(df_final["sistema"].astype(str).str.upper().str.strip().replace("", "N/A").unique().tolist()))
                if sistemas:
                    for sis in sistemas:
                        df_sis = df_final[df_final["sistema"].str.upper().str.strip() == sis]
                        st.markdown(f"**Sistema: {sis}**")
                        h1, h2, h3, h4 = st.columns([2, 2, 2, 2])
                        h1.markdown("**Metrica**")
                        h2.markdown("**Oficial**")
                        h3.markdown("**Taquilla**")
                        h4.markdown("**Diferencia**")

                        for label, col_ofi, col_taq in metric_pairs:
                            v_ofi = float(df_sis.get(col_ofi, pd.Series([0])).sum())
                            v_taq = float(df_sis.get(col_taq, pd.Series([0])).sum())
                            diff = v_ofi - v_taq
                            c1, c2, c3, c4 = st.columns([2, 2, 2, 2])
                            c1.markdown(label)
                            c2.markdown(f"{v_ofi:,.0f}")
                            c3.markdown(f"{v_taq:,.0f}")
                            if abs(diff) < 0.5:
                                c4.markdown("---")
                            else:
                                color = "#dc2626" if diff > 0 else "#16a34a"
                                icono = "▲" if diff > 0 else "▼"
                                c4.markdown(f"<span style='color:{color};'>{icono} {abs(diff):,.0f}</span>", unsafe_allow_html=True)

                st.markdown(f"#### Gastos y Pagos Acumulados en {m_search} (Ciclo)")
                h1, h2, h3, h4 = st.columns([2, 2, 2, 2])
                h1.markdown("**Concepto**")
                h2.markdown("**Oficial**")
                h3.markdown("**Taquilla**")
                h4.markdown("**Diferencia**")

                t_gastos_ofi = float(df_g_oficial['gastos_ofi'].sum()) if not df_g_oficial.empty else 0.0
                t_gastos_taq = float(df_g['gastos_taq'].sum()) if not df_g.empty else 0.0
                t_pagos_ofi = float(df_p_oficial['pagos_ofi'].sum()) if not df_p_oficial.empty else 0.0
                t_pagos_taq = float(df_p['pagos_taq'].sum()) if not df_p.empty else 0.0

                for label, v_ofi, v_taq in [("Gastos", t_gastos_ofi, t_gastos_taq), ("Pagos", t_pagos_ofi, t_pagos_taq)]:
                    diff = v_ofi - v_taq
                    c1, c2, c3, c4 = st.columns([2, 2, 2, 2])
                    c1.markdown(label)
                    c2.markdown(f"{v_ofi:,.0f}")
                    c3.markdown(f"{v_taq:,.0f}")
                    if abs(diff) < 0.5:
                        c4.markdown("---")
                    else:
                        color = "#dc2626" if diff > 0 else "#16a34a"
                        icono = "▲" if diff > 0 else "▼"
                        c4.markdown(f"<span style='color:{color};'>{icono} {abs(diff):,.0f}</span>", unsafe_allow_html=True)

                st.markdown("---")

            df_v_moneda = df_taq_periodo[df_taq_periodo["moneda"].astype(str).str.upper().str.strip() == m_search].copy() if not df_taq_periodo.empty and "moneda" in df_taq_periodo.columns else pd.DataFrame()
            df_g_moneda = df_gastos_periodo[df_gastos_periodo["moneda"].astype(str).str.upper().str.strip() == m_search].copy() if not df_gastos_periodo.empty and "moneda" in df_gastos_periodo.columns else pd.DataFrame()
            df_p_moneda = df_pagos_periodo[df_pagos_periodo["moneda"].astype(str).str.upper().str.strip() == m_search].copy() if not df_pagos_periodo.empty and "moneda" in df_pagos_periodo.columns else pd.DataFrame()

            fmt_mon = "Bs. %,.2f" if m_search == "BS" else ("$%,.2f" if m_search == "USD" else "COP %,.2f")
            simbolo_mon = "Bs. " if m_search == "BS" else ("$" if m_search == "USD" else "COP ")

            nombre_terminal = "General"
            if agencia_data and isinstance(agencia_data, dict) and "nombre_agencia" in agencia_data:
                nombre_terminal = agencia_data["nombre_agencia"]
            elif "agencia_actual" in st.session_state and isinstance(st.session_state["agencia_actual"], dict):
                nombre_terminal = st.session_state["agencia_actual"].get("nombre_agencia", "General")

            st.subheader("Reporte Detallado del Periodo")
            st.markdown(f"**Terminal:** {nombre_terminal} | **Ciclo:** {f_desde_str} al {f_hasta_str} | **Moneda:** {m_search}")

            t_v_total = float(df_v_moneda['monto_venta'].sum()) if not df_v_moneda.empty and 'monto_venta' in df_v_moneda.columns else 0.0
            t_c_total = float(df_v_moneda['comision'].sum()) if not df_v_moneda.empty and 'comision' in df_v_moneda.columns else 0.0
            t_p_total = float(df_v_moneda['monto_premios'].sum()) if not df_v_moneda.empty and 'monto_premios' in df_v_moneda.columns else 0.0
            t_g_total = float(df_g_moneda['monto'].sum()) if not df_g_moneda.empty and 'monto' in df_g_moneda.columns else 0.0
            t_pg_total = float(df_p_moneda['monto'].sum()) if not df_p_moneda.empty and 'monto' in df_p_moneda.columns else 0.0
            saldo_f = (t_v_total - t_c_total - t_p_total - t_g_total - t_pg_total)

            m1, m2, m3, m4, m5, m6 = st.columns(6)
            m1.metric("Total Ventas", f"{simbolo_mon}{t_v_total:,.2f}")
            m2.metric("Total Comision", f"{simbolo_mon}{t_c_total:,.2f}")
            m3.metric("Total Premios", f"{simbolo_mon}{t_p_total:,.2f}")
            m4.metric("Total Gastos", f"{simbolo_mon}{t_g_total:,.2f}")
            m5.metric("Total Pagos", f"{simbolo_mon}{t_pg_total:,.2f}")
            m6.metric("Saldo Final", f"{simbolo_mon}{saldo_f:,.2f}")

            tab1, tab2, tab3 = st.tabs(["Ventas", "Gastos", "Pagos"])
            with tab1:
                cols_v = ["id", "agencia", "nombre_agency", "sistema", "moneda", "monto_venta", "comision", "monto_premios", "neto", "fecha"]
                cols_v_existentes = [c for c in cols_v if c in df_v_moneda.columns]
                if not df_v_moneda.empty:
                    st.dataframe(
                        df_v_moneda[cols_v_existentes],
                        column_config={
                            "monto_venta": st.column_config.NumberColumn("Venta", format=fmt_mon),
                            "comision": st.column_config.NumberColumn("Comisión", format=fmt_mon),
                            "monto_premios": st.column_config.NumberColumn("Premios", format=fmt_mon),
                            "neto": st.column_config.NumberColumn("Neto", format=fmt_mon),
                        },
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("No hay ventas registradas en el periodo.")
            with tab2:
                if not df_g_moneda.empty:
                    df_g_disp = df_g_moneda.copy()
                    df_g_disp["Conf."] = df_g_disp.apply(obtener_etiqueta_confirmacion, axis=1)
                    if "agencia" not in df_g_disp.columns and "nombre_agency" in df_g_disp.columns:
                        df_g_disp["agencia"] = df_g_disp["nombre_agency"]
                    elif "nombre_agency" in df_g_disp.columns:
                        df_g_disp["agencia"] = df_g_disp["agencia"].fillna(df_g_disp["nombre_agency"])
                    cols_g = ["agencia", "concepto", "moneda", "monto", "Conf."]
                    if "motivo_rechazo" in df_g_disp.columns and df_g_disp["motivo_rechazo"].dropna().astype(str).str.strip().ne("").any():
                        df_g_disp["motivo_rechazo"] = df_g_disp["motivo_rechazo"].fillna("")
                        cols_g.append("motivo_rechazo")
                    cols_g.append("fecha")
                    cols_g_existentes = [c for c in cols_g if c in df_g_disp.columns]
                    st.dataframe(
                        df_g_disp[cols_g_existentes],
                        column_config={
                            "monto": st.column_config.NumberColumn("monto", format=fmt_mon),
                            "motivo_rechazo": st.column_config.TextColumn("Motivo Rechazo")
                        },
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("No hay gastos registrados en el periodo.")
            with tab3:
                if not df_p_moneda.empty:
                    df_p_disp = df_p_moneda.copy()
                    df_p_disp["Conf."] = df_p_disp.apply(obtener_etiqueta_confirmacion, axis=1)
                    if "agencia" not in df_p_disp.columns and "nombre_agency" in df_p_disp.columns:
                        df_p_disp["agencia"] = df_p_disp["nombre_agency"]
                    elif "nombre_agency" in df_p_disp.columns:
                        df_p_disp["agencia"] = df_p_disp["agencia"].fillna(df_p_disp["nombre_agency"])
                    df_p_disp = df_p_disp.rename(columns={"tipo_pago": "pagos registrados"})
                    cols_p = ["agencia", "pagos registrados", "moneda", "monto", "Conf."]
                    if "motivo_rechazo" in df_p_disp.columns and df_p_disp["motivo_rechazo"].dropna().astype(str).str.strip().ne("").any():
                        df_p_disp["motivo_rechazo"] = df_p_disp["motivo_rechazo"].fillna("")
                        cols_p.append("motivo_rechazo")
                    cols_p.append("fecha")
                    cols_p_existentes = [c for c in cols_p if c in df_p_disp.columns]
                    st.dataframe(
                        df_p_disp[cols_p_existentes],
                        column_config={
                            "monto": st.column_config.NumberColumn("monto", format=fmt_mon),
                            "motivo_rechazo": st.column_config.TextColumn("Motivo Rechazo")
                        },
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("No hay pagos registrados en el periodo.")
