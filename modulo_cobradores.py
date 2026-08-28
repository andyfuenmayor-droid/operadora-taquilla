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


def decodificar_token_qr_de_imagen(image_file):
    """Decodifica un código QR a partir de una captura de cámara o imagen y extrae el Token limpio."""
    if not image_file:
        return None
    try:
        from PIL import Image
        img = Image.open(image_file)
    except Exception:
        return None

    raw_text = None

    # Método 1: zxingcpp (extremadamente rápido y preciso en fotos de celulares)
    try:
        import zxingcpp
        res = zxingcpp.read_barcode(img)
        if res and res.text:
            raw_text = str(res.text).strip()
    except Exception:
        pass

    # Método 2: pyzbar
    if not raw_text:
        try:
            from pyzbar.pyzbar import decode
            objs = decode(img)
            if objs:
                raw_text = objs[0].data.decode("utf-8").strip()
        except Exception:
            pass

    # Método 3: OpenCV
    if not raw_text:
        try:
            import cv2
            import numpy as np
            open_cv_image = np.array(img.convert('RGB'))
            detector = cv2.QRCodeDetector()
            val, _, _ = detector.detectAndDecode(open_cv_image)
            if val and str(val).strip():
                raw_text = str(val).strip()
        except Exception:
            pass

    if not raw_text:
        return None

    # Limpiar si el QR contiene un payload JSON (ej: {"token": "QR-REC-...", ...})
    try:
        import json
        if "{" in raw_text and "}" in raw_text:
            data = json.loads(raw_text)
            if isinstance(data, dict) and "token" in data:
                return str(data["token"]).strip()
    except Exception:
        pass

    # Si contiene 'QR-REC-' en cualquier parte del texto
    if "QR-REC-" in raw_text:
        for item in raw_text.replace('"', ' ').replace("'", ' ').split():
            if "QR-REC-" in item:
                return item.strip()

    return raw_text.strip()


def _procesar_validacion_entrega(token_input, c_id, c_nombre, u_id):
    """Valida y sella el token de entrega en la base de datos."""
    if not token_input:
        st.error("⚠️ Ingrese o escanee un token válido.")
        return False
    
    token_clean = str(token_input).strip()

    # Si ya fue validado en esta sesión justo ahora, no re-procesar
    ultimo_exito = st.session_state.get("entrega_validada_exito")
    if ultimo_exito and ultimo_exito.get("token") == token_clean:
        return True

    try:
        q_tkn = supabase.table("cda_pagos_diarios").select("*").ilike("qr_token", f"%{token_clean}%")
        if u_id:
            try:
                q_tkn = q_tkn.eq("user_id", u_id)
            except Exception:
                pass
        res_tkn = q_tkn.execute()
        data_tkn = res_tkn.data or []

        if not data_tkn:
            st.error(f"❌ No se encontró ninguna entrega registrada con el Token: `{token_clean}`")
            return False

        rec_pago = data_tkn[0]
        p_id = rec_pago["id"]
        ag_nom_p = str(rec_pago.get("agencia") or rec_pago.get("nombre_agency") or "Agencia").upper()
        mto_p = float(rec_pago.get("monto", 0.0))
        mon_p = normalizar_moneda(rec_pago.get("moneda"))
        f_esc_prev = str(rec_pago.get("fecha_escaneo_cobrador") or "").strip()
        cob_nom_prev = str(rec_pago.get("cobrador_nombre") or "").strip()

        sym = "Bs." if mon_p == "BS" else ("$" if mon_p == "USD" else "COP ")

        if f_esc_prev and cob_nom_prev and cob_nom_prev.lower() not in ["", "none", "cobrador"]:
            st.warning(
                f"⚠️ Este comprobante ya fue escaneado y validado anteriormente por **{cob_nom_prev}** el {f_esc_prev[:19]}.\n\n"
                f"🏢 **Agencia:** {ag_nom_p} | 💰 **Monto:** {sym}{mto_p:,.2f}"
            )
            return False

        ahora_iso = _obtener_hora_actual().isoformat()
        supabase.table("cda_pagos_diarios").update({
            "cobrador_id": c_id,
            "cobrador_nombre": c_nombre,
            "fecha_escaneo_cobrador": ahora_iso,
            "confirmado": True,
            "confirmado_supervisor": True
        }).eq("id", p_id).execute()

        # Guardar en session_state para mostrar tarjeta de éxito persistente
        st.session_state["entrega_validada_exito"] = {
            "token": token_clean,
            "agencia": ag_nom_p,
            "monto": mto_p,
            "moneda": mon_p,
            "simbolo": sym,
            "fecha": ahora_iso[:19].replace("T", " "),
            "cobrador": c_nombre
        }
        # Incrementar versión de cámara para limpiar el buffer en el navegador
        st.session_state["cam_scan_cobrador_version"] = st.session_state.get("cam_scan_cobrador_version", 0) + 1
        st.rerun()
        return True
    except Exception as ex:
        st.error(f"Error procesando token: {ex}")
        return False


def modulo_portal_cobrador(cobrador_info, agencia_ctx=None, vista_inicial="Portal Cobrador"):
    """
    Portal Móvil y de Escritorio optimizado para el Cobrador de Calle.
    Permite validar códigos QR de entregas, confirmar recepción de efectivo de agencias en su ruta,
    consultar su lista de agencias y totalizar sus recaudaciones activas.
    """
    is_dark = st.session_state.get("tema_oscuro", True)
    text_color = "#ffffff" if is_dark else "#0f172a"
    sub_color = "#94a3b8" if is_dark else "#64748b"
    card_bg = "rgba(13, 27, 34, 0.65)" if is_dark else "#ffffff"
    card_border = "rgba(255, 255, 255, 0.08)" if is_dark else "rgba(15, 23, 42, 0.12)"

    c_id = cobrador_info.get("id")
    c_nombre = str(cobrador_info.get("nombre") or cobrador_info.get("nombre_cajero") or cobrador_info.get("usuario") or "Cobrador").strip()
    c_usuario = str(cobrador_info.get("usuario", "")).strip()
    u_id = cobrador_info.get("user_id") or (agencia_ctx.get("user_id") if isinstance(agencia_ctx, dict) else None)

    st.markdown(
        f"""
        <div style="background: linear-gradient(135deg, rgba(0, 200, 83, 0.12) 0%, rgba(56, 189, 248, 0.1) 100%); border: 1px solid rgba(0, 200, 83, 0.25); border-radius: 14px; padding: 1.1rem 1.4rem; margin-bottom: 1.25rem;">
            <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px;">
                <div>
                    <div style="font-size: 0.75rem; font-weight: 700; color: #00c853; text-transform: uppercase; letter-spacing: 0.05em;">🛵 PORTAL MÓVIL DE COBRANZA</div>
                    <h2 style="margin: 2px 0 0 0; font-size: 1.5rem; font-weight: 800; color: {text_color};">
                        Hola, {c_nombre.title()}
                    </h2>
                    <div style="font-size: 0.85rem; color: {sub_color}; margin-top: 2px;">
                        Usuario: <code>@{c_usuario}</code> | Validador de entregas y recaudaciones QR en ruta
                    </div>
                </div>
                <div style="background: rgba(0, 200, 83, 0.15); border: 1px solid #00c853; color: #00c853; font-weight: 700; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem;">
                    🟢 EN TURNO ACTIVO
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # 1. Cargar Agencias Asignadas a este Cobrador
    df_asig = _cargar_cobrador_agencias(u_id)
    agencias_en_ruta = []
    if not df_asig.empty and "cobrador_id" in df_asig.columns:
        sub_asig = df_asig[df_asig["cobrador_id"] == c_id]
        if not sub_asig.empty:
            agencias_en_ruta = sub_asig["nombre_agencia"].astype(str).str.upper().tolist()

    # 2. Cargar Período Activo y Pagos
    ciclo = obtener_periodo_trabajo(u_id)
    f_desde = ciclo.get("desde", str(datetime.now().date()))
    f_hasta = ciclo.get("hasta", str(datetime.now().date()))

    # Cargar pagos relevantes: del periodo o cualquier entrega pendiente de cobro
    df_pagos_cob = pd.DataFrame()
    try:
        q = supabase.table("cda_pagos_diarios").select("*")
        if u_id:
            try:
                q = q.eq("user_id", u_id)
            except Exception:
                pass
        res_p = q.execute()
        df_pagos_cob = pd.DataFrame(res_p.data or [])
        if not df_pagos_cob.empty:
            df_pagos_cob.columns = [c.lower().strip() for c in df_pagos_cob.columns]
    except Exception as ex:
        st.warning(f"Nota al consultar pagos: {ex}")

    # Tabs del Portal
    tab_pin, tab_ruta, tab_mis_recs = st.tabs([
        "🔢 Validar PIN de Entrega",
        f"🗺️ Mi Ruta ({len(agencias_en_ruta)} Agencias)",
        "💰 Mis Recaudaciones y Custodia"
    ])

    # ==============================================================
    # TAB 1: VALIDACIÓN RÁPIDA POR PIN
    # ==============================================================
    with tab_pin:
        # Mostrar tarjeta de éxito si se validó una entrega
        exito_data = st.session_state.get("entrega_validada_exito")
        if exito_data:
            st.markdown(
                f"""
                <div style="background: linear-gradient(135deg, rgba(0, 200, 83, 0.22) 0%, rgba(56, 189, 248, 0.15) 100%); border: 2px solid #00c853; border-radius: 14px; padding: 1.25rem; margin-bottom: 1.25rem; text-align: center;">
                    <div style="font-size: 2.5rem; margin-bottom: 4px;">🎉</div>
                    <h3 style="color: #00c853; margin: 0 0 8px 0; font-size: 1.4rem; font-weight: 800;">¡ENTREGA VALIDADA CON ÉXITO!</h3>
                    <div style="font-size: 1.7rem; font-weight: 900; color: #ffffff; margin: 8px 0;">{exito_data.get('simbolo')}{exito_data.get('monto'):,.2f} {exito_data.get('moneda')}</div>
                    <div style="font-size: 0.95rem; color: #cbd5e1; line-height: 1.7;">
                        🏢 <b>Agencia:</b> {exito_data.get('agencia')}<br/>
                        🕒 <b>Fecha/Hora:</b> {exito_data.get('fecha')}<br/>
                        🛵 <b>Registrado a nombre de:</b> {exito_data.get('cobrador')}<br/>
                        🔢 <b>PIN Validado:</b> <b style="color: #38bdf8; font-family: monospace;">{exito_data.get('token')}</b>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
            col_b1, col_b2 = st.columns([1, 1])
            with col_b1:
                if st.button("🔑 Validar Siguiente Entrega", type="primary", use_container_width=True, key="btn_scan_next_qr"):
                    st.session_state.pop("entrega_validada_exito", None)
                    st.rerun()
            with col_b2:
                if st.button("💰 Actualizar y Continuar", use_container_width=True, key="btn_cont_qr"):
                    st.session_state.pop("entrega_validada_exito", None)
                    st.rerun()
            st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)

        st.markdown("#### 🔢 Validación de Entrega por Código PIN (6 Dígitos)")
        st.caption("Ingresa los 6 números que te dicte o muestre el supervisor para validar la entrega en 1 segundo:")

        with st.form("form_val_pin_cobrador", clear_on_submit=False):
            c_pin1, c_pin2 = st.columns([2.5, 1.5])
            with c_pin1:
                pin_input = st.text_input(
                    "Código PIN de Entrega (6 dígitos)", 
                    placeholder="Ej: 482910",
                    max_chars=20,
                    key="input_pin_cob_val"
                ).strip()
            with c_pin2:
                st.write("")
                st.write("")
                btn_val_pin = st.form_submit_button("⚡ VALIDAR PIN", type="primary", use_container_width=True)

        if btn_val_pin and pin_input:
            _procesar_validacion_entrega(pin_input, c_id, c_nombre, u_id)

        st.markdown("---")

        # Entregas Pendientes de Agencias en su Ruta
        st.markdown("#### 📋 Entregas en Efectivo Pendientes por Cobrar (En tu Ruta)")
        st.caption("Comprobantes emitidos por las agencias de tu ruta asignada que aún no han sido sellados:")

        if df_pagos_cob.empty:
            st.info("ℹ️ No hay registros de pagos en el período actual.")
        else:
            # Filtrar: agencias en ruta (o todas si no tiene asignación estricta), tipo cobrador/qr, no escaneados aún
            mask_pend = (
                (df_pagos_cob.get("fecha_escaneo_cobrador", pd.Series(dtype=str)).fillna("").eq("")) &
                (
                    df_pagos_cob["tipo_pago"].astype(str).str.contains("COBRADOR", case=False, na=False) |
                    df_pagos_cob.get("qr_token", pd.Series(dtype=str)).fillna("").ne("")
                )
            )

            df_pends = df_pagos_cob[mask_pend].copy()
            if agencias_en_ruta:
                df_pends = df_pends[df_pends["agencia"].astype(str).str.upper().isin(agencias_en_ruta)]

            if df_pends.empty:
                st.success("✅ **¡Al día!** No tienes entregas pendientes de confirmación en tus agencias asignadas.")
            else:
                st.write(f"Mostrando **{len(df_pends)}** entrega(s) pendiente(s) de escaneo:")
                for _, r_pend in df_pends.iterrows():
                    pid_p = r_pend["id"]
                    ag_n = str(r_pend.get("agencia") or r_pend.get("nombre_agency") or "Agencia").upper()
                    mon_n = normalizar_moneda(r_pend.get("moneda"))
                    mto_n = float(r_pend.get("monto", 0.0))
                    fch_n = str(r_pend.get("fecha", ""))[:10]
                    caj_raw = r_pend.get("cajero_id")
                    if pd.isna(caj_raw) or not str(caj_raw).strip() or str(caj_raw).lower() in ["nan", "none"]:
                        caj_n = "Supervisor / Caja"
                    else:
                        caj_n = str(caj_raw).upper()

                    sym_n = "Bs." if mon_n == "BS" else ("$" if mon_n == "USD" else "COP ")
                    tkn_n = str(r_pend.get("qr_token") or "").strip()
                    pin_n = tkn_n.replace("QR-REC-", "") if tkn_n else "N/A"

                    with st.container(border=True):
                        c1, c2, c3 = st.columns([4, 3, 3])
                        with c1:
                            st.markdown(
                                f"""
                                <div style="font-weight: 700; font-size: 1.1rem; color: {text_color};">🏢 {ag_n}</div>
                                <div style="font-size: 0.82rem; color: {sub_color}; margin-top: 2px;">
                                    📅 <b>Fecha:</b> {fch_n} | 👤 <b>Cajero:</b> {caj_n}<br/>
                                    🔢 <b>PIN:</b> <b style="color: #38bdf8; font-size: 1rem; font-family: monospace;">{pin_n}</b>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
                        with c2:
                            st.markdown(
                                f"""
                                <div style="font-size: 0.75rem; font-weight: 700; color: {sub_color}; text-transform: uppercase;">MONTO A RECIBIR</div>
                                <div style="color: #00c853; font-weight: 800; font-size: 1.25rem;">{sym_n}{mto_n:,.2f}</div>
                                <span style="background: rgba(251, 191, 36, 0.15); color: #fbbf24; border: 1px solid rgba(251, 191, 36, 0.3); border-radius: 4px; padding: 2px 6px; font-size: 0.72rem; font-weight: 700;">⏳ PENDIENTE RECEPCIÓN</span>
                                """,
                                unsafe_allow_html=True
                            )
                        with c3:
                            st.write("")
                            if st.button("🤝 Recibir Efectivo", key=f"btn_recibir_pend_{pid_p}", type="primary", use_container_width=True):
                                try:
                                    ahora_iso = _obtener_hora_actual().isoformat()
                                    supabase.table("cda_pagos_diarios").update({
                                        "cobrador_id": c_id,
                                        "cobrador_nombre": c_nombre,
                                        "fecha_escaneo_cobrador": ahora_iso,
                                        "confirmado": True,
                                        "confirmado_supervisor": True
                                    }).eq("id", pid_p).execute()
                                    st.success(f"✅ ¡Efectivo de {ag_n} ({sym_n}{mto_n:,.2f}) recibido correctamente!")
                                    time.sleep(1)
                                    st.rerun()
                                except Exception as ex:
                                    st.error(f"Error confirmando: {ex}")

    # ==============================================================
    # TAB 2: MI RUTA DE AGENCIAS
    # ==============================================================
    with tab_ruta:
        st.markdown("#### 🗺️ Directorio de Agencias Asignadas")
        st.caption("Estas son las agencias configuradas en tu ruta de cobranza por la Administración:")

        df_ag_all = _cargar_agencias(u_id)
        if not agencias_en_ruta:
            st.info("ℹ️ Aún no tienes agencias vinculadas a tu ruta. Comunícate con la Administración para que te asigne tus agencias.")
        else:
            for ag_nom in agencias_en_ruta:
                info_ag = {}
                if not df_ag_all.empty:
                    match_ag = df_ag_all[df_ag_all["nombre_agencia"].astype(str).str.upper() == ag_nom]
                    if not match_ag.empty:
                        info_ag = match_ag.iloc[0].to_dict()

                with st.container(border=True):
                    col_ag1, col_ag2 = st.columns([3, 2])
                    with col_ag1:
                        st.markdown(
                            f"""
                            <div style="font-size: 1.15rem; font-weight: 700; color: {text_color};">🏢 {ag_nom}</div>
                            <div style="font-size: 0.85rem; color: {sub_color}; margin-top: 4px;">
                                Estado: <span style="color: #10b981; font-weight: 700;">🟢 Habilitada en Ruta</span>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    with col_ag2:
                        wa_ag = str(info_ag.get("telefono_whatsapp") or info_ag.get("telefono") or "").strip()
                        if wa_ag and wa_ag.lower() not in ["none", "nan", ""]:
                            clean_wa = ''.join(c for c in wa_ag if c.isdigit())
                            if len(clean_wa) == 10 and clean_wa.startswith("0"): clean_wa = "58" + clean_wa[1:]
                            wa_url = f"https://wa.me/{clean_wa}"
                            st.markdown(
                                f"""
                                <a href="{wa_url}" target="_blank" style="display: block; text-align: center; background: rgba(37, 211, 102, 0.15); color: #25D366; border: 1px solid #25D366; border-radius: 8px; padding: 6px 12px; font-weight: 700; text-decoration: none; font-size: 0.85rem;">
                                    📱 WhatsApp ({wa_ag})
                                </a>
                                """,
                                unsafe_allow_html=True
                            )
                        else:
                            st.caption("Sin teléfono registrado")

    # ==============================================================
    # TAB 3: MIS RECAUDACIONES Y CUSTODIA
    # ==============================================================
    with tab_mis_recs:
        st.markdown("#### 💰 Fondos Recaudados y Liquidación")
        st.caption("Resumen del dinero físico que has cobrado y se encuentra actualmente bajo tu custodia:")

        if df_pagos_cob.empty:
            st.info("ℹ️ No hay registros de pagos para mostrar.")
        else:
            # Filtrar pagos cobrados por este cobrador (por ID o por Nombre)
            mask_mis = (
                (df_pagos_cob.get("cobrador_id", pd.Series(dtype=object)).astype(str) == str(c_id)) |
                (df_pagos_cob.get("cobrador_nombre", pd.Series(dtype=str)).astype(str).str.upper() == c_nombre.upper())
            )
            df_mis = df_pagos_cob[mask_mis].copy()

            if df_mis.empty:
                st.info("ℹ️ Aún no has validado recaudaciones en este período.")
            else:
                df_mis["monto"] = pd.to_numeric(df_mis["monto"], errors="coerce").fillna(0.0)
                df_mis["moneda_norm"] = df_mis["moneda"].apply(normalizar_moneda)
                df_mis["liquidado_admin"] = df_mis.get("liquidado_admin", False).fillna(False).astype(bool)

                # Totales en Custodia (Pendientes de liquidar)
                df_custodia = df_mis[df_mis["liquidado_admin"] == False]
                tot_bs_cust = df_custodia[df_custodia["moneda_norm"] == "BS"]["monto"].sum()
                tot_usd_cust = df_custodia[df_custodia["moneda_norm"] == "USD"]["monto"].sum()
                tot_cop_cust = df_custodia[df_custodia["moneda_norm"] == "COP"]["monto"].sum()

                # Totales Ya Liquidados
                df_liq = df_mis[df_mis["liquidado_admin"] == True]
                tot_bs_liq = df_liq[df_liq["moneda_norm"] == "BS"]["monto"].sum()
                tot_usd_liq = df_liq[df_liq["moneda_norm"] == "USD"]["monto"].sum()
                tot_cop_liq = df_liq[df_liq["moneda_norm"] == "COP"]["monto"].sum()

                st.markdown("##### 💼 Dinero en Custodia Activa (Por entregar a Administración)")
                km1, km2, km3 = st.columns(3)
                km1.metric("Bolívares (BS)", f"Bs. {tot_bs_cust:,.2f}")
                km2.metric("Dólares (USD)", f"${tot_usd_cust:,.2f}")
                km3.metric("Pesos (COP)", f"COP {tot_cop_cust:,.2f}")

                if not df_liq.empty:
                    with st.expander("✅ Ver Totales Ya Liquidados a la Administración", expanded=False):
                        kl1, kl2, kl3 = st.columns(3)
                        kl1.metric("Bs. Liquidados", f"Bs. {tot_bs_liq:,.2f}")
                        kl2.metric("USD Liquidados", f"${tot_usd_liq:,.2f}")
                        kl3.metric("COP Liquidados", f"COP {tot_cop_liq:,.2f}")

                st.markdown("---")
                st.markdown("##### 📜 Historial Detallado de Recaudaciones")
                for _, r_m in df_mis.iterrows():
                    m_ag = str(r_m.get("agencia") or "Agencia").upper()
                    m_mon = normalizar_moneda(r_m.get("moneda"))
                    m_mto = float(r_m.get("monto", 0.0))
                    m_fch = str(r_m.get("fecha", ""))[:10]
                    m_fesc = str(r_m.get("fecha_escaneo_cobrador", "") or "")
                    m_liq = bool(r_m.get("liquidado_admin", False))
                    m_sym = "Bs." if m_mon == "BS" else ("$" if m_mon == "USD" else "COP ")

                    status_badge = (
                        "<span style='background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid #10b981; border-radius: 4px; padding: 2px 6px; font-size: 0.75rem; font-weight: 700;'>✅ LIQUIDADO A ADMIN</span>"
                        if m_liq else
                        "<span style='background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid #38bdf8; border-radius: 4px; padding: 2px 6px; font-size: 0.75rem; font-weight: 700;'>🛵 EN CUSTODIA</span>"
                    )

                    with st.container(border=True):
                        st.markdown(
                            f"""
                            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                                <div>
                                    <div style="font-weight: 700; font-size: 1.05rem; color: {text_color};">🏢 {m_ag}</div>
                                    <div style="font-size: 0.82rem; color: {sub_color}; margin-top: 2px;">
                                        📅 {m_fch} {f' | 🕒 Cobrado: {m_fesc[:19].replace("T", " ")}' if m_fesc else ''}
                                    </div>
                                </div>
                                <div style="text-align: right;">
                                    <div style="font-weight: 800; font-size: 1.2rem; color: #00c853;">{m_sym}{m_mto:,.2f}</div>
                                    {status_badge}
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
