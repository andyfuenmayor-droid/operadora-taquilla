import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
import time
from utils import supabase, obtener_periodo_trabajo, normalizar_moneda

def _obtener_hora_actual():
    """Retorna la fecha y hora actual en zona horaria UTC-4."""
    return datetime.now(timezone(timedelta(hours=-4)))

def _obtener_user_id(agencia_data=None):
    """Extrae el Tenant / Admin user_id de la sesión o datos de agencia."""
    if agencia_data and isinstance(agencia_data, dict) and agencia_data.get("user_id"):
        return str(agencia_data["user_id"]).strip()
    if "user" in st.session_state and hasattr(st.session_state["user"], "id"):
        return str(st.session_state["user"].id).strip()
    if "user" in st.session_state and isinstance(st.session_state["user"], dict):
        return str(st.session_state["user"].get("id", "")).strip()
    if "agencia_actual" in st.session_state and isinstance(st.session_state["agencia_actual"], dict):
        return str(st.session_state["agencia_actual"].get("user_id", "")).strip()
    return None

def _cargar_agencias(u_id):
    """Carga todas las agencias registradas bajo el user_id del administrador."""
    try:
        query = supabase.table("agencias").select("id, nombre_agencia, activo").order("nombre_agencia")
        if u_id:
            query = query.eq("user_id", u_id)
        res = query.execute()
        df = pd.DataFrame(res.data or [])
        if not df.empty:
            df.columns = [c.lower().strip() for c in df.columns]
        return df
    except Exception as e:
        st.error(f"Error cargando agencias: {e}")
        return pd.DataFrame()

def _cargar_cobradores(u_id):
    """Carga todos los cobradores registrados."""
    try:
        query = supabase.table("cda_cobradores").select("*").order("created_at", desc=True)
        if u_id:
            query = query.eq("user_id", u_id)
        res = query.execute()
        df = pd.DataFrame(res.data or [])
        if not df.empty:
            df.columns = [c.lower().strip() for c in df.columns]
        return df
    except Exception as e:
        st.warning(
            "⚠️ No se pudo acceder a la tabla `cda_cobradores`. "
            "Asegúrate de haber ejecutado el script SQL de creación en Supabase."
        )
        return pd.DataFrame()

def _cargar_cobrador_agencias(u_id):
    """Carga las asignaciones de agencias por cobrador."""
    try:
        query = supabase.table("cda_cobrador_agencias").select("*")
        if u_id:
            query = query.eq("user_id", u_id)
        res = query.execute()
        df = pd.DataFrame(res.data or [])
        if not df.empty:
            df.columns = [c.lower().strip() for c in df.columns]
        return df
    except Exception:
        return pd.DataFrame()

def modulo_cobradores(agencia_data=None):
    is_dark = st.session_state.get("tema_oscuro", True)
    text_color = "#ffffff" if is_dark else "#0f172a"
    sub_color = "#94a3b8" if is_dark else "#64748b"
    card_bg = "rgba(13, 27, 34, 0.55)" if is_dark else "#ffffff"
    card_border = "rgba(255, 255, 255, 0.08)" if is_dark else "rgba(15, 23, 42, 0.12)"

    st.markdown(
        f"""
        <div style="margin-bottom: 1.25rem;">
            <h2 style="margin: 0; font-size: 1.75rem; font-weight: 700; color: {text_color};">
                🛵 Gestión y Liquidación de Cobradores
            </h2>
            <p style="margin: 4px 0 0 0; font-size: 0.9rem; color: {sub_color};">
                Administra los perfiles de cobradores de ruta, sus agencias asignadas y la liquidación de recaudación QR.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    u_id = _obtener_user_id(agencia_data)
    if not u_id:
        st.warning("⚠️ No se pudo determinar el identificador del Administrador (user_id).")
        return

    df_agencias = _cargar_agencias(u_id)
    df_cobradores = _cargar_cobradores(u_id)
    df_asignaciones = _cargar_cobrador_agencias(u_id)

    # Tabs de operación
    tab_lista, tab_nuevo, tab_rutas, tab_liquidacion = st.tabs([
        "👥 Cobradores Registrados",
        "➕ Registrar Nuevo",
        "🗺️ Asignación de Rutas",
        "💰 Liquidación de Recaudaciones"
    ])

    # ==========================================
    # TAB 1: LISTA Y EDICIÓN DE COBRADORES
    # ==========================================
    with tab_lista:
        if df_cobradores.empty:
            st.info("ℹ️ No hay cobradores registrados aún. Usa la pestaña **➕ Registrar Nuevo** para dar de alta al primero.")
        else:
            col_search, col_filter = st.columns([3, 1])
            with col_search:
                filtro_txt = st.text_input("🔍 Buscar cobrador", placeholder="Nombre, usuario, cédula...", label_visibility="collapsed")
            with col_filter:
                filtro_estado = st.selectbox("Estado", ["Todos", "Solo Activos", "Solo Inactivos"], label_visibility="collapsed")

            df_show = df_cobradores.copy()
            if filtro_txt:
                q = filtro_txt.strip().lower()
                df_show = df_show[
                    df_show["nombre"].astype(str).str.lower().str.contains(q) |
                    df_show["usuario"].astype(str).str.lower().str.contains(q) |
                    df_show.get("cedula_identidad", pd.Series(dtype=str)).astype(str).str.lower().str.contains(q) |
                    df_show.get("telefono", pd.Series(dtype=str)).astype(str).str.lower().str.contains(q)
                ]

            if filtro_estado == "Solo Activos":
                df_show = df_show[df_show.get("activo", True) == True]
            elif filtro_estado == "Solo Inactivos":
                df_show = df_show[df_show.get("activo", True) == False]

            st.write(f"Mostrando **{len(df_show)}** de **{len(df_cobradores)}** cobradores.")

            for _, cob in df_show.iterrows():
                cob_id = cob["id"]
                cob_nom = str(cob.get("nombre", "Sin Nombre")).strip()
                cob_usr = str(cob.get("usuario", "")).strip()
                cob_ced = str(cob.get("cedula_identidad", "") or "No registrada").strip()
                cob_tel = str(cob.get("telefono", "") or "No registrado").strip()
                cob_act = bool(cob.get("activo", True))

                # Agencias asociadas a este cobrador
                agencias_cob = []
                if not df_asignaciones.empty and "cobrador_id" in df_asignaciones.columns:
                    match_asig = df_asignaciones[df_asignaciones["cobrador_id"] == cob_id]
                    if not match_asig.empty:
                        agencias_cob = match_asig["nombre_agencia"].astype(str).str.upper().tolist()

                badge_color = "#10b981" if cob_act else "#ef4444"
                badge_bg = "rgba(16, 185, 129, 0.15)" if cob_act else "rgba(239, 68, 68, 0.15)"
                badge_lbl = "ACTIVO" if cob_act else "INACTIVO"

                with st.container(border=True):
                    c_main, c_agencias, c_actions = st.columns([3, 4, 3])

                    with c_main:
                        st.markdown(
                            f"""
                            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                                <span style="font-size: 1.1rem; font-weight: 700; color: {text_color};">{cob_nom}</span>
                                <span style="background: {badge_bg}; color: {badge_color}; border: 1px solid {badge_color}40; border-radius: 4px; padding: 2px 6px; font-size: 0.7rem; font-weight: 700;">{badge_lbl}</span>
                            </div>
                            <div style="font-size: 0.82rem; color: {sub_color}; line-height: 1.4;">
                                👤 <b>Usuario:</b> <code>{cob_usr}</code><br/>
                                🪪 <b>Cédula:</b> {cob_ced} | 📱 <b>Tel:</b> {cob_tel}
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                    with c_agencias:
                        st.markdown(f"<div style='font-size: 0.75rem; font-weight: 700; color: {sub_color}; text-transform: uppercase;'>Ruta Asignada ({len(agencias_cob)} agencias)</div>", unsafe_allow_html=True)
                        if agencias_cob:
                            chips = " ".join([f"<span style='display: inline-block; background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 4px; padding: 2px 6px; font-size: 0.75rem; margin: 2px;'>🏢 {ag}</span>" for ag in agencias_cob])
                            st.markdown(chips, unsafe_allow_html=True)
                        else:
                            st.markdown("<span style='font-size: 0.8rem; color: #fbbf24;'>⚠️ Sin agencias en su ruta</span>", unsafe_allow_html=True)

                    with c_actions:
                        pop_key = f"pop_edit_{cob_id}"
                        with st.popover("⚙️ Editar / Gestionar", use_container_width=True):
                            st.markdown(f"#### Editar: {cob_nom}")
                            with st.form(key=f"form_edit_cob_{cob_id}"):
                                e_nom = st.text_input("Nombre Completo", value=cob_nom)
                                e_ced = st.text_input("Cédula de Identidad", value="" if cob_ced == "No registrada" else cob_ced)
                                e_tel = st.text_input("Teléfono / WhatsApp", value="" if cob_tel == "No registrado" else cob_tel)
                                e_act = st.toggle("Cobrador Activo", value=cob_act)
                                e_pwd = st.text_input("Nueva Clave (dejar en blanco para no cambiar)", type="password", placeholder="Dejar en blanco = sin cambio")

                                if st.form_submit_button("💾 Guardar Cambios", use_container_width=True):
                                    try:
                                        upd_data = {
                                            "nombre": e_nom.strip(),
                                            "cedula_identidad": e_ced.strip(),
                                            "telefono": e_tel.strip(),
                                            "activo": e_act
                                        }
                                        if e_pwd.strip():
                                            upd_data["clave"] = e_pwd.strip()

                                        supabase.table("cda_cobradores").update(upd_data).eq("id", cob_id).execute()
                                        st.success("✅ Datos actualizados exitosamente!")
                                        time.sleep(0.8)
                                        st.rerun()
                                    except Exception as ex:
                                        st.error(f"Error al actualizar: {ex}")

                            st.markdown("---")
                            # Sección de eliminación con confirmación
                            with st.expander("🗑️ Eliminar Cobrador", expanded=False):
                                st.warning("Esta acción eliminará el cobrador y sus asignaciones de ruta.")
                                if st.button("Confirmar Eliminación", key=f"btn_del_{cob_id}", type="primary", use_container_width=True):
                                    try:
                                        supabase.table("cda_cobradores").delete().eq("id", cob_id).execute()
                                        st.success(f"Cobrador '{cob_nom}' eliminado.")
                                        time.sleep(0.8)
                                        st.rerun()
                                    except Exception as ex:
                                        st.error(f"Error al eliminar: {ex}")

    # ==========================================
    # TAB 2: REGISTRAR NUEVO COBRADOR
    # ==========================================
    with tab_nuevo:
        st.markdown("### ➕ Alta de Nuevo Cobrador")
        st.caption("Ingresa los datos de acceso para que el cobrador pueda autenticarse en la app móvil y escanear comprobantes QR.")

        with st.form("form_nuevo_cobrador", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                n_nombre = st.text_input("Nombre Completo *", placeholder="Ej: Carlos Mendoza")
                n_cedula = st.text_input("Cédula de Identidad", placeholder="Ej: V-18234567")
                n_telefono = st.text_input("Teléfono / WhatsApp", placeholder="Ej: 04141234567")
            with c2:
                n_usuario = st.text_input("Usuario de Acceso *", placeholder="Ej: cobrador_carlos")
                n_clave = st.text_input("Contraseña / Clave *", type="password", placeholder="Clave segura")
                n_activo = st.checkbox("Habilitar Cobrador Inmediatamente", value=True)

            # Selector de Agencias para su ruta inicial
            opciones_agencias = []
            mapa_ag_id = {}
            if not df_agencias.empty:
                for _, r_ag in df_agencias.iterrows():
                    ag_label = str(r_ag["nombre_agencia"]).strip().upper()
                    opciones_agencias.append(ag_label)
                    mapa_ag_id[ag_label] = r_ag["id"]

            st.markdown("#### 🏢 Agencias Asignadas a su Ruta")
            agencias_seleccionadas = st.multiselect(
                "Selecciona las agencias que visitará este cobrador:",
                options=opciones_agencias,
                placeholder="Elige una o más agencias..."
            )

            btn_submit = st.form_submit_button("🚀 CREAR COBRADOR", use_container_width=True)

            if btn_submit:
                if not n_nombre.strip() or not n_usuario.strip() or not n_clave.strip():
                    st.error("⚠️ El Nombre, Usuario y Clave son obligatorios.")
                else:
                    try:
                        u_clean = n_usuario.strip().lower()
                        # 1. Insertar cobrador
                        cob_data = {
                            "user_id": u_id,
                            "nombre": n_nombre.strip(),
                            "cedula_identidad": n_cedula.strip(),
                            "telefono": n_telefono.strip(),
                            "usuario": u_clean,
                            "clave": n_clave.strip(),
                            "activo": n_activo
                        }
                        res_cob = supabase.table("cda_cobradores").insert(cob_data).execute()
                        if res_cob and res_cob.data:
                            nuevo_cob_id = res_cob.data[0]["id"]

                            # 2. Insertar asignación de agencias si seleccionó
                            if agencias_seleccionadas:
                                asig_rows = []
                                for ag_nom in agencias_seleccionadas:
                                    asig_rows.append({
                                        "cobrador_id": nuevo_cob_id,
                                        "agencia_id": mapa_ag_id.get(ag_nom),
                                        "nombre_agencia": ag_nom,
                                        "user_id": u_id
                                    })
                                supabase.table("cda_cobrador_agencias").insert(asig_rows).execute()

                            st.success(f"🎉 ¡Cobrador '{n_nombre}' registrado exitosamente con {len(agencias_seleccionadas)} agencias!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("No se pudo crear el cobrador. Verifica que el usuario no esté duplicado.")
                    except Exception as ex:
                        st.error(f"Error al registrar cobrador: {ex}")

    # ==========================================
    # TAB 3: ASIGNACIÓN DE RUTAS
    # ==========================================
    with tab_rutas:
        st.markdown("### 🗺️ Matriz y Reasignación de Rutas por Cobrador")
        st.caption("Configura qué agencias pertenecen a la ruta de cobranza de cada cobrador.")

        if df_cobradores.empty:
            st.info("No hay cobradores para asignar rutas.")
        elif df_agencias.empty:
            st.warning("No hay agencias disponibles en la base de datos.")
        else:
            opciones_cobs = {f"{c['nombre']} (@{c['usuario']})": c["id"] for _, c in df_cobradores.iterrows()}
            cob_sel_label = st.selectbox("Seleccione un cobrador para modificar su ruta:", list(opciones_cobs.keys()))
            cob_sel_id = opciones_cobs[cob_sel_label]

            # Agencias actuales asignadas
            agencias_actuales = []
            if not df_asignaciones.empty and "cobrador_id" in df_asignaciones.columns:
                match_asig = df_asignaciones[df_asignaciones["cobrador_id"] == cob_sel_id]
                if not match_asig.empty:
                    agencias_actuales = match_asig["nombre_agencia"].astype(str).str.upper().tolist()

            todas_agencias = sorted(df_agencias["nombre_agencia"].astype(str).str.upper().tolist())
            mapa_ag_id = dict(zip(df_agencias["nombre_agencia"].astype(str).str.upper(), df_agencias["id"]))

            with st.form(key=f"form_rutas_{cob_sel_id}"):
                nuevas_asignaciones = st.multiselect(
                    f"Agencias autorizadas para {cob_sel_label}:",
                    options=todas_agencias,
                    default=[ag for ag in agencias_actuales if ag in todas_agencias]
                )

                if st.form_submit_button("💾 Actualizar Ruta de Agencias", use_container_width=True):
                    try:
                        # 1. Eliminar asignaciones previas de este cobrador
                        supabase.table("cda_cobrador_agencias").delete().eq("cobrador_id", cob_sel_id).execute()

                        # 2. Insertar nuevas asignaciones
                        if nuevas_asignaciones:
                            nuevas_filas = []
                            for ag_nom in nuevas_asignaciones:
                                nuevas_filas.append({
                                    "cobrador_id": cob_sel_id,
                                    "agencia_id": mapa_ag_id.get(ag_nom),
                                    "nombre_agencia": ag_nom,
                                    "user_id": u_id
                                })
                            supabase.table("cda_cobrador_agencias").insert(nuevas_filas).execute()

                        st.success(f"✅ Ruta actualizada exitosamente con {len(nuevas_asignaciones)} agencias.")
                        time.sleep(0.8)
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Error al actualizar rutas: {ex}")

    # ==========================================
    # TAB 4: TRAZABILIDAD Y LIQUIDACIÓN QR
    # ==========================================
    with tab_liquidacion:
        st.markdown("### 💰 Trazabilidad y Liquidación de Fondos QR")
        st.caption("Verifica las entregas realizadas por las agencias, los escaneos de los cobradores y realiza la liquidación de fondos hacia la Administración.")

        ciclo = obtener_periodo_trabajo(u_id)
        f_desde = ciclo.get("desde", str(datetime.now().date()))
        f_hasta = ciclo.get("hasta", str(datetime.now().date()))

        col_f1, col_f2, col_f3 = st.columns([2, 2, 2])
        with col_f1:
            filtro_desde = st.date_input("Desde", value=pd.to_datetime(f_desde).date())
        with col_f2:
            filtro_hasta = st.date_input("Hasta", value=pd.to_datetime(f_hasta).date())
        with col_f3:
            estado_liq_sel = st.selectbox("Estado de Liquidación", ["Todos", "Pendientes de Liquidar", "Liquidados"])

        try:
            q_pagos = supabase.table("cda_pagos_diarios").select("*")\
                .gte("fecha", str(filtro_desde))\
                .lte("fecha", f"{str(filtro_hasta)}T23:59:59")
            if u_id:
                q_pagos = q_pagos.eq("user_id", u_id)
            res_pagos = q_pagos.execute()
            df_pagos = pd.DataFrame(res_pagos.data or [])
        except Exception as ex:
            st.error(f"Error consultando pagos: {ex}")
            df_pagos = pd.DataFrame()

        # Filtrar pagos de tipo Cobrador o con QR
        if not df_pagos.empty:
            df_pagos.columns = [c.lower().strip() for c in df_pagos.columns]
            mask_cob = (
                df_pagos["tipo_pago"].astype(str).str.contains("COBRADOR", case=False, na=False) |
                df_pagos.get("qr_token", pd.Series(dtype=str)).fillna("").ne("")
            )
            df_cobs_pagos = df_pagos[mask_cob].copy()
        else:
            df_cobs_pagos = pd.DataFrame()

        if df_cobs_pagos.empty:
            st.info("ℹ️ No hay registros de entregas a cobrador en el rango de fechas seleccionado.")
        else:
            df_cobs_pagos["monto"] = pd.to_numeric(df_cobs_pagos["monto"], errors="coerce").fillna(0.0)
            df_cobs_pagos["liquidado_admin"] = df_cobs_pagos.get("liquidado_admin", False).fillna(False).astype(bool)

            if estado_liq_sel == "Pendientes de Liquidar":
                df_cobs_pagos = df_cobs_pagos[df_cobs_pagos["liquidado_admin"] == False]
            elif estado_liq_sel == "Liquidados":
                df_cobs_pagos = df_cobs_pagos[df_cobs_pagos["liquidado_admin"] == True]

            # Tarjetas de Métricas por Moneda
            total_bs = df_cobs_pagos[df_cobs_pagos["moneda"].astype(str).str.upper().isin(["BS", "VES"])]["monto"].sum()
            total_usd = df_cobs_pagos[df_cobs_pagos["moneda"].astype(str).str.upper() == "USD"]["monto"].sum()
            total_cop = df_cobs_pagos[df_cobs_pagos["moneda"].astype(str).str.upper() == "COP"]["monto"].sum()

            m1, m2, m3 = st.columns(3)
            m1.metric("Total Recaudado (BS)", f"Bs. {total_bs:,.2f}")
            m2.metric("Total Recaudado (USD)", f"${total_usd:,.2f}")
            m3.metric("Total Recaudado (COP)", f"COP {total_cop:,.2f}")

            st.markdown("---")

            # Botón de liquidación masiva si hay pendientes
            pendientes = df_cobs_pagos[df_cobs_pagos["liquidado_admin"] == False]
            if not pendientes.empty:
                col_btn_liq, _ = st.columns([2, 3])
                with col_btn_liq:
                    if st.button(f"⚡ Liquidar Todos los Pendientes ({len(pendientes)} registros)", type="primary", use_container_width=True):
                        try:
                            ahora_iso = _obtener_hora_actual().isoformat()
                            ids_pendientes = pendientes["id"].tolist()
                            for p_id in ids_pendientes:
                                supabase.table("cda_pagos_diarios").update({
                                    "liquidado_admin": True,
                                    "fecha_liquidacion_admin": ahora_iso
                                }).eq("id", p_id).execute()
                            st.success(f"✅ Se liquidaron {len(ids_pendientes)} entregas con la Administración.")
                            time.sleep(1)
                            st.rerun()
                        except Exception as ex:
                            st.error(f"Error liquidando: {ex}")

            # Listado de Entregas
            for _, r_pg in df_cobs_pagos.iterrows():
                pid = r_pg["id"]
                ag_n = str(r_pg.get("agencia") or r_pg.get("nombre_agency") or "Agencia").upper()
                mon = str(r_pg.get("moneda", "BS")).upper()
                mto = float(r_pg.get("monto", 0.0))
                fch = str(r_pg.get("fecha", ""))[:10]
                tkn = str(r_pg.get("qr_token", "") or "Sin Token")
                c_nom = str(r_pg.get("cobrador_nombre", "") or "No escaneado").strip()
                f_esc = str(r_pg.get("fecha_escaneo_cobrador", "") or "")
                is_liq = bool(r_pg.get("liquidado_admin", False))
                f_liq = str(r_pg.get("fecha_liquidacion_admin", "") or "")

                sym = "Bs." if mon == "BS" else ("$" if mon == "USD" else "COP ")

                # Estado
                if is_liq:
                    badge_status = "<span style='background: rgba(16, 185, 129, 0.2); color: #10b981; border-radius: 4px; padding: 2px 8px; font-weight: 700; font-size: 0.75rem;'>💰 LIQUIDADO POR ADMIN</span>"
                elif f_esc:
                    badge_status = "<span style='background: rgba(56, 189, 248, 0.2); color: #38bdf8; border-radius: 4px; padding: 2px 8px; font-weight: 700; font-size: 0.75rem;'>🛵 ESCANEADO EN RUTA</span>"
                else:
                    badge_status = "<span style='background: rgba(251, 191, 36, 0.2); color: #fbbf24; border-radius: 4px; padding: 2px 8px; font-weight: 700; font-size: 0.75rem;'>⏳ PENDIENTE POR ESCANEO</span>"

                with st.container(border=True):
                    c_info, c_escaneo, c_btn = st.columns([4, 4, 3])
                    with c_info:
                        st.markdown(
                            f"""
                            <div style="font-weight: 700; font-size: 1.05rem; color: {text_color};">{ag_n}</div>
                            <div style="font-size: 0.85rem; color: {sub_color};">
                                📅 <b>Fecha:</b> {fch} | 🔑 <code>{tkn}</code><br/>
                                💵 <span style="color: #10b981; font-weight: 700; font-size: 1.1rem;">{sym}{mto:,.2f}</span>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                    with c_escaneo:
                        detalles_esc = f"🛵 <b>Cobrador:</b> {c_nom}<br/>"
                        if f_esc:
                            detalles_esc += f"🕒 <b>Escaneado:</b> {f_esc[:19]}<br/>"
                        if is_liq and f_liq:
                            detalles_esc += f"💼 <b>Liquidado:</b> {f_liq[:19]}"
                        st.markdown(f"<div style='font-size: 0.82rem; color: {sub_color};'>{badge_status}<br/>{detalles_esc}</div>", unsafe_allow_html=True)

                    with c_btn:
                        if not is_liq:
                            if st.button("🤝 Liquidar a Admin", key=f"btn_liq_indiv_{pid}", use_container_width=True):
                                try:
                                    supabase.table("cda_pagos_diarios").update({
                                        "liquidado_admin": True,
                                        "fecha_liquidacion_admin": _obtener_hora_actual().isoformat()
                                    }).eq("id", pid).execute()
                                    st.success("✅ Liquidado")
                                    time.sleep(0.5)
                                    st.rerun()
                                except Exception as ex:
                                    st.error(f"Error: {ex}")
                        else:
                            if st.button("↩️ Revertir Liquidación", key=f"btn_rev_liq_{pid}", use_container_width=True):
                                try:
                                    supabase.table("cda_pagos_diarios").update({
                                        "liquidado_admin": False,
                                        "fecha_liquidacion_admin": None
                                    }).eq("id", pid).execute()
                                    st.info("Liquidación revertida.")
                                    time.sleep(0.5)
                                    st.rerun()
                                except Exception as ex:
                                    st.error(f"Error: {ex}")
