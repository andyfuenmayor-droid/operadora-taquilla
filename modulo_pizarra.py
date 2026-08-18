import streamlit as st
import pandas as pd
from datetime import datetime
import time
from utils import supabase, obtener_periodo_trabajo

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

def obtener_agencias_paraguas_usuario(u_id, agencia_data=None):
    """
    Retorna la lista de agencias autorizadas bajo el paraguas del usuario actual.
    - Para supervisores, cajeros y terminales de agencia: se restringe estrictamente a la agencia activa o asignadas.
    - Para administradores: se incluyen todas las agencias asociadas a la cuenta.
    """
    cajero_info = st.session_state.get("cajero_actual", {})
    ag_info = agencia_data or st.session_state.get("agencia_actual", {})
    rol = str(cajero_info.get("rol", "")).lower().strip()
    
    agencias_paraguas = []
    
    # 1. Agencia actual del terminal en sesión
    if ag_info and isinstance(ag_info, dict) and ag_info.get("nombre_agencia"):
        ag_nom_terminal = str(ag_info["nombre_agencia"]).strip().upper()
        if ag_nom_terminal and ag_nom_terminal not in agencias_paraguas:
            agencias_paraguas.append(ag_nom_terminal)

    # 2. Si es usuario con rol operativo (supervisor, cajero, agencia)
    if rol in ["supervisor", "cajero", "agencia"]:
        cajero_id = cajero_info.get("id")
        usuario_str = cajero_info.get("usuario")
        
        try:
            q_user = supabase.table("taquilla_usuarios").select("agencia_id, usuario").eq("activo", True)
            if cajero_id:
                res_u = q_user.or_(f"id.eq.{cajero_id},usuario.eq.{usuario_str}").execute()
            else:
                res_u = q_user.eq("usuario", usuario_str).execute()
                
            ag_ids_asignados = [r["agencia_id"] for r in (res_u.data or []) if r.get("agencia_id")]
            if ag_ids_asignados:
                res_ag = supabase.table("agencias").select("nombre_agencia").in_("id", ag_ids_asignados).execute()
                for r in (res_ag.data or []):
                    nom = str(r.get("nombre_agencia", "")).strip().upper()
                    if nom and nom not in agencias_paraguas:
                        agencias_paraguas.append(nom)
        except Exception:
            pass

        if agencias_paraguas:
            return sorted(agencias_paraguas)

    # 3. Si es Administrador General
    try:
        query_all = supabase.table("agencias").select("nombre_agencia")
        if u_id:
            query_all = query_all.eq("user_id", u_id)
        res_all = query_all.execute()
        for r in (res_all.data or []):
            nom = str(r.get("nombre_agencia", "")).strip().upper()
            if nom and nom not in agencias_paraguas:
                agencias_paraguas.append(nom)
    except Exception:
        pass

    return sorted(agencias_paraguas)

def obtener_mapa_cajeros(u_id=None):
    mapa = {}
    try:
        query = supabase.table("taquilla_usuarios").select("id, usuario, nombre_cajero")
        if u_id:
            query = query.eq("user_id", u_id)
        res_usr = query.execute()
        rows = res_usr.data or []
        if not rows and u_id:
            rows = supabase.table("taquilla_usuarios").select("id, usuario, nombre_cajero").execute().data or []

        for u in rows:
            nom = u.get("nombre_cajero") or u.get("usuario") or ""
            if nom:
                if u.get("id"):
                    mapa[str(u["id"]).strip()] = nom
                if u.get("usuario"):
                    mapa[str(u["usuario"]).strip()] = nom
                if u.get("nombre_cajero"):
                    mapa[str(u["nombre_cajero"]).strip()] = nom
    except Exception:
        pass

    cajero_actual = st.session_state.get("cajero_actual", {})
    if isinstance(cajero_actual, dict):
        nom_act = cajero_actual.get("nombre") or cajero_actual.get("usuario")
        if nom_act:
            if cajero_actual.get("id"):
                mapa[str(cajero_actual["id"]).strip()] = nom_act
            if cajero_actual.get("usuario"):
                mapa[str(cajero_actual["usuario"]).strip()] = nom_act

    return mapa

def resolver_nombre_cajero(cid_or_user, pago_dict=None, mapa=None):
    """Resuelve el nombre del cajero/usuario para evitar que aparezca como 'Cajero' genérico."""
    if pago_dict and isinstance(pago_dict, dict):
        for k in ["cajero_nombre", "nombre_cajero", "cajero"]:
            val = str(pago_dict.get(k) or "").strip()
            if val and val.lower() not in ["none", "nan", "system", "cajero", "desconocido", ""]:
                return val

    c_str = str(cid_or_user or "").strip()
    if mapa and isinstance(mapa, dict) and c_str:
        if c_str in mapa and mapa[c_str]:
            return mapa[c_str]
        for k, v in mapa.items():
            if str(k).strip() == c_str and v:
                return v

    if c_str and c_str.lower() not in ["none", "nan", "system", "cajero", "desconocido", ""]:
        return c_str

    if pago_dict and isinstance(pago_dict, dict):
        usr_val = str(pago_dict.get("usuario") or "").strip()
        if usr_val and usr_val.lower() not in ["none", "nan", "system", "cajero", "desconocido", ""]:
            return usr_val

    return "Cajero"

def _sincronizar_efectivo_supervisor_con_pagos(u_id=None, existe_supervisor=True, agencias_permitidas=None):
    """Garantiza que todos los pagos en efectivo confirmados tengan su movimiento en cda_caja_efectivo_supervisor, restringido al paraguas de agencias."""
    try:
        q_pd = supabase.table("cda_pagos_diarios").select("*")
        if u_id:
            try:
                q_pd = q_pd.eq("user_id", u_id)
            except Exception:
                pass

        if existe_supervisor:
            res_pd = q_pd.or_("confirmado.eq.true,confirmado_supervisor.eq.true").execute()
        else:
            res_pd = q_pd.execute()

        if not res_pd.data:
            return

        q_movs = supabase.table("cda_caja_efectivo_supervisor").select("*")
        if u_id:
            try:
                q_movs = q_movs.eq("user_id", u_id)
            except Exception:
                pass
        res_movs = q_movs.execute()
        pagos_registrados = set()
        if res_movs.data:
            for rm in res_movs.data:
                if rm.get("pago_id") is not None:
                    pagos_registrados.add(str(rm["pago_id"]))

        mapa_cajeros = obtener_mapa_cajeros(u_id)

        for pago in res_pd.data:
            pid = pago.get("id")
            ag_pago = str(pago.get("agencia") or "").upper().strip()
            
            # Filtro por paraguas de agencias
            if agencias_permitidas and ag_pago not in agencias_permitidas:
                continue

            cat_val = str(pago.get("categoria") or "").upper()
            tipo = str(pago.get("tipo_pago") or pago.get("metodo") or "").upper()
            es_efectivo = "EFECTIVO" in cat_val or "EFECTIVO" in tipo or ("REF:" not in tipo and "PUNTO" not in tipo and "TRANSFERENCIA" not in tipo and "ZELLE" not in tipo and "PAGO MÓVIL" not in tipo)

            if pid is not None and es_efectivo and str(pid) not in pagos_registrados:
                cid = str(pago.get("cajero_id") or pago.get("user_id") or "").strip()
                c_nombre = resolver_nombre_cajero(cid, pago_dict=pago, mapa=mapa_cajeros)
                sup_nom = str(pago.get("supervisor_nombre") or c_nombre).strip()
                if sup_nom in ["", "None", "Cajero", "SYSTEM"]:
                    sup_nom = c_nombre
                u_id_val = str(pago.get("user_id") or u_id or "SYSTEM").strip()
                monto_val = float(pago.get("monto") or 0.0)
                moneda_val = normalizar_moneda(pago.get("moneda"))

                comentario_text = f"Recibido de cajero {c_nombre} (Confirmado)"

                try:
                    supabase.table("cda_caja_efectivo_supervisor").insert({
                        "user_id": u_id_val,
                        "agencia": ag_pago,
                        "supervisor_nombre": sup_nom,
                        "tipo_movimiento": "ENTRADA_CAJERO",
                        "monto": monto_val,
                        "moneda": moneda_val,
                        "pago_id": pid,
                        "comentario": comentario_text
                    }).execute()
                    pagos_registrados.add(str(pid))
                except Exception:
                    try:
                        supabase.table("cda_caja_efectivo_supervisor").insert({
                            "user_id": u_id_val,
                            "agencia": ag_pago,
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
    """Verifica si las columnas y permisos necesarios existen en Supabase."""
    tablas_faltantes = []
    for tabla in ["cda_gastos_diarios", "cda_pagos_diarios", "cda_pagos_bancarios"]:
        try:
            supabase.table(tabla).select("confirmado").limit(1).execute()
        except Exception:
            tablas_faltantes.append(tabla)

    cols_sup_faltantes = []
    for tabla in ["cda_gastos_diarios", "cda_pagos_diarios", "cda_pagos_bancarios"]:
        try:
            supabase.table(tabla).select("confirmado_supervisor").limit(1).execute()
        except Exception:
            cols_sup_faltantes.append(tabla)

    caja_sup_existe = True
    pago_id_caja_existe = True
    rls_caja_bloqueada = False
    try:
        res_chk = supabase.table("cda_caja_efectivo_supervisor").select("id").limit(1).execute()
        try:
            supabase.table("cda_caja_efectivo_supervisor").select("pago_id").limit(1).execute()
        except Exception:
            pago_id_caja_existe = False
    except Exception as ex_chk:
        err_msg_chk = str(ex_chk).lower()
        if "42501" in err_msg_chk or "row-level security" in err_msg_chk:
            rls_caja_bloqueada = True
        else:
            caja_sup_existe = False
            pago_id_caja_existe = False

    if tablas_faltantes or cols_sup_faltantes or not caja_sup_existe or not pago_id_caja_existe or rls_caja_bloqueada:
        sql_lines = []
        for t in tablas_faltantes:
            sql_lines.append(f"ALTER TABLE {t} ADD COLUMN IF NOT EXISTS confirmado BOOLEAN DEFAULT FALSE;")
            sql_lines.append(f"ALTER TABLE {t} ADD COLUMN IF NOT EXISTS confirmado_por TEXT;")
        
        for t in cols_sup_faltantes:
            sql_lines.append(f"ALTER TABLE {t} ADD COLUMN IF NOT EXISTS confirmado_supervisor BOOLEAN DEFAULT FALSE;")
            sql_lines.append(f"ALTER TABLE {t} ADD COLUMN IF NOT EXISTS supervisor_nombre TEXT;")
            sql_lines.append(f"ALTER TABLE {t} ADD COLUMN IF NOT EXISTS fecha_confirmacion_supervisor TIMESTAMP WITH TIME ZONE;")
            sql_lines.append(f"ALTER TABLE {t} ADD COLUMN IF NOT EXISTS comentario_supervisor TEXT;")
            sql_lines.append(f"ALTER TABLE {t} ADD COLUMN IF NOT EXISTS entregado_admin BOOLEAN DEFAULT FALSE;")

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
        sql_lines.append("""
-- 1. Habilitar RLS de forma segura
ALTER TABLE cda_caja_efectivo_supervisor ENABLE ROW LEVEL SECURITY;

-- 2. Eliminar políticas anteriores
DROP POLICY IF EXISTS "cda_caja_sup_select_policy" ON cda_caja_efectivo_supervisor;
DROP POLICY IF EXISTS "cda_caja_sup_insert_policy" ON cda_caja_efectivo_supervisor;
DROP POLICY IF EXISTS "cda_caja_sup_update_policy" ON cda_caja_efectivo_supervisor;
DROP POLICY IF EXISTS "cda_caja_sup_delete_policy" ON cda_caja_efectivo_supervisor;

-- 3. Políticas granulares y seguras por Tenant (user_id)
CREATE POLICY "cda_caja_sup_select_policy" ON cda_caja_efectivo_supervisor
    FOR SELECT USING (user_id IS NOT NULL AND length(user_id) > 0);

CREATE POLICY "cda_caja_sup_insert_policy" ON cda_caja_efectivo_supervisor
    FOR INSERT WITH CHECK (
        (user_id IS NOT NULL AND length(user_id) > 0)
        AND monto >= 0
        AND moneda IN ('BS', 'USD', 'COP', 'VES')
    );

CREATE POLICY "cda_caja_sup_update_policy" ON cda_caja_efectivo_supervisor
    FOR UPDATE USING (user_id IS NOT NULL AND length(user_id) > 0)
    WITH CHECK (monto >= 0 AND moneda IN ('BS', 'USD', 'COP', 'VES'));

CREATE POLICY "cda_caja_sup_delete_policy" ON cda_caja_efectivo_supervisor
    FOR DELETE USING (user_id IS NOT NULL AND length(user_id) > 0);
""".strip())

        sql_script = "\n".join(sql_lines)
        st.warning(
            f"⚠️ **Configuración de Políticas RLS Requerida:** Para proteger la tabla `cda_caja_efectivo_supervisor` con políticas seguras por tenant, ejecuta este script en el **SQL Editor** de Supabase:\n\n"
            f"```sql\n{sql_script}\n```"
        )

def _confirmar_registro_individual(row, current_usr, mapa_cajeros=None):
    """Ejecuta la confirmación directa en 1 solo clic de cualquier transacción."""
    data_conf = {
        "confirmado": True,
        "confirmado_por": current_usr,
        "confirmado_supervisor": True,
        "supervisor_nombre": current_usr,
        "fecha_confirmacion_supervisor": datetime.now().isoformat()
    }
    try:
        try:
            supabase.table(row["tabla"]).update(data_conf).eq("id", row["id"]).execute()
        except Exception:
            supabase.table(row["tabla"]).update({"confirmado": True, "confirmado_supervisor": True}).eq("id", row["id"]).execute()

        if row["tabla"] == "cda_pagos_bancarios":
            try:
                supabase.table("cda_pagos_diarios").update(data_conf).eq("agencia", row["agencia"]).eq("fecha", row["fecha"]).eq("monto", row["monto"]).execute()
            except Exception:
                try:
                    supabase.table("cda_pagos_diarios").update({"confirmado": True, "confirmado_supervisor": True}).eq("agencia", row["agencia"]).eq("fecha", row["fecha"]).eq("monto", row["monto"]).execute()
                except Exception:
                    pass

        es_efectivo = (row.get("categoria") == "Efectivo" or "EFECTIVO" in str(row.get("metodo", "")).upper())
        if es_efectivo:
            c_nom_pago = row.get("cajero_nombre") or resolver_nombre_cajero(row.get("cajero_id"), pago_dict=row, mapa=mapa_cajeros)
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
                    "comentario": f"Recibido de cajero {c_nom_pago} (Confirmado por {current_usr})"
                }).execute()
            except Exception:
                pass
        return True, None
    except Exception as e:
        return False, str(e)

def _revertir_registro_individual(row):
    """Revierte una transacción confirmada a estado pendiente."""
    data_rev = {
        "confirmado": False,
        "confirmado_por": None,
        "confirmado_supervisor": False,
        "supervisor_nombre": None,
        "fecha_confirmacion_supervisor": None
    }
    try:
        try:
            supabase.table(row["tabla"]).update(data_rev).eq("id", row["id"]).execute()
        except Exception:
            supabase.table(row["tabla"]).update({"confirmado": False, "confirmado_supervisor": False}).eq("id", row["id"]).execute()

        if row["tabla"] == "cda_pagos_bancarios":
            try:
                supabase.table("cda_pagos_diarios").update(data_rev).eq("agencia", row["agencia"]).eq("fecha", row["fecha"]).eq("monto", row["monto"]).execute()
            except Exception:
                try:
                    supabase.table("cda_pagos_diarios").update({"confirmado": False, "confirmado_supervisor": False}).eq("agencia", row["agencia"]).eq("fecha", row["fecha"]).eq("monto", row["monto"]).execute()
                except Exception:
                    pass

        try:
            supabase.table("cda_caja_efectivo_supervisor").delete().eq("pago_id", row["id"]).execute()
        except Exception:
            pass

        return True, None
    except Exception as e:
        return False, str(e)

def _confirmar_lote(df_a_confirmar, mapa_cajeros=None):
    """Confirma masivamente todas las transacciones pendientes pasadas en el dataframe."""
    if df_a_confirmar.empty:
        st.warning("⚠️ No hay transacciones pendientes para confirmar en la vista actual.")
        return

    current_usr = obtener_nombre_usuario_actual()
    total_procesados = 0
    errores = []

    progress_bar = st.progress(0, text="⚡ Confirmando transacciones en lote...")
    total_items = len(df_a_confirmar)

    for idx, (_, row) in enumerate(df_a_confirmar.iterrows()):
        ok, err = _confirmar_registro_individual(row, current_usr, mapa_cajeros)
        if ok:
            total_procesados += 1
        else:
            errores.append(f"Registro #{row.get('id')}: {err}")
        progress_bar.progress((idx + 1) / total_items, text=f"⚡ Procesando {idx + 1}/{total_items}...")

    progress_bar.empty()

    if total_procesados > 0:
        st.success(f"✅ ¡Se confirmaron exitosamente {total_procesados} transacciones por {current_usr}!")
    if errores:
        st.error(f"⚠️ Ocurrieron {len(errores)} errores durante el proceso.")
    
    time.sleep(0.6)
    st.rerun()

def _renderizar_resumen_metricas(df_target, df_pendientes_lote=None):
    """Barra ejecutiva unificada y minimalista de métricas con botón de acción masiva."""
    if df_target.empty:
        df_pend = pd.DataFrame()
        df_conf = pd.DataFrame()
    else:
        df_pend = df_target[df_target["confirmado"] == False]
        df_conf = df_target[df_target["confirmado"] == True]

    # Cálculos agrupados por moneda para Pendientes
    bs_pend = df_pend[df_pend["moneda"].isin(["BS", "BOLIVARES", "VES"])]["monto"].sum() if not df_pend.empty else 0.0
    usd_pend = df_pend[df_pend["moneda"].isin(["USD", "DOLARES", "$"])]["monto"].sum() if not df_pend.empty else 0.0
    cop_pend = df_pend[df_pend["moneda"].isin(["COP", "PESOS"])]["monto"].sum() if not df_pend.empty else 0.0

    # Cálculos agrupados por moneda para Confirmados
    bs_conf = df_conf[df_conf["moneda"].isin(["BS", "BOLIVARES", "VES"])]["monto"].sum() if not df_conf.empty else 0.0
    usd_conf = df_conf[df_conf["moneda"].isin(["USD", "DOLARES", "$"])]["monto"].sum() if not df_conf.empty else 0.0
    cop_conf = df_conf[df_conf["moneda"].isin(["COP", "PESOS"])]["monto"].sum() if not df_conf.empty else 0.0

    col_m1, col_m2, col_m3 = st.columns([4, 4, 3])

    with col_m1:
        st.markdown(f"""
            <div style="background: rgba(234, 179, 8, 0.08); border: 1px solid rgba(234, 179, 8, 0.3); border-radius: 10px; padding: 12px 16px; min-height: 96px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-size: 11px; font-weight: 800; color: #eab308; text-transform: uppercase; letter-spacing: 0.05em;">⏳ PENDIENTES POR CONFIRMAR</span>
                    <span style="background: rgba(234, 179, 8, 0.2); color: #fef08a; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: 800;">{len(df_pend)} reg.</span>
                </div>
                <div style="font-size: 13px; font-weight: 700; color: #f8fafc; margin-top: 6px; display: flex; flex-wrap: wrap; gap: 10px;">
                    <span style="color: #fde047;">🇻🇪 Bs {bs_pend:,.2f}</span>
                    <span style="color: #4ade80;">💵 ${usd_pend:,.2f}</span>
                    <span style="color: #60a5fa;">🇨🇴 COP {cop_pend:,.2f}</span>
                </div>
            </div>
        """, unsafe_allow_html=True)

    with col_m2:
        st.markdown(f"""
            <div style="background: rgba(34, 197, 94, 0.08); border: 1px solid rgba(34, 197, 94, 0.3); border-radius: 10px; padding: 12px 16px; min-height: 96px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-size: 11px; font-weight: 800; color: #22c55e; text-transform: uppercase; letter-spacing: 0.05em;">✅ TOTAL CONFIRMADOS</span>
                    <span style="background: rgba(34, 197, 94, 0.2); color: #bbf7d0; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: 800;">{len(df_conf)} reg.</span>
                </div>
                <div style="font-size: 13px; font-weight: 700; color: #f8fafc; margin-top: 6px; display: flex; flex-wrap: wrap; gap: 10px;">
                    <span style="color: #86efac;">🇻🇪 Bs {bs_conf:,.2f}</span>
                    <span style="color: #4ade80;">💵 ${usd_conf:,.2f}</span>
                    <span style="color: #93c5fd;">🇨🇴 COP {cop_conf:,.2f}</span>
                </div>
            </div>
        """, unsafe_allow_html=True)

    with col_m3:
        num_pend_lote = len(df_pend) if df_pendientes_lote is None else len(df_pendientes_lote)
        st.markdown("""
            <div style="font-size: 11px; font-weight: 800; color: #94a3b8; text-transform: uppercase; margin-bottom: 4px; letter-spacing: 0.05em;">
                ⚡ ACCIÓN RÁPIDA MASIVA
            </div>
        """, unsafe_allow_html=True)
        if num_pend_lote > 0:
            with st.popover(f"⚡ Confirmar Todo ({num_pend_lote})", use_container_width=True):
                st.markdown(f"#### ⚡ Confirmación Masiva en 1 Clic")
                st.markdown(f"¿Deseas confirmar simultáneamente las **{num_pend_lote}** transacciones pendientes de la vista actual?")
                st.caption("Esta acción marcará como confirmados todos los registros filtrados en pantalla.")
                if st.button("🚀 Sí, Confirmar Todo Ahora", key="btn_confirmar_lote_action", type="primary", use_container_width=True):
                    mapa_c = obtener_mapa_cajeros()
                    target_lote = df_pend if df_pendientes_lote is None else df_pendientes_lote
                    _confirmar_lote(target_lote, mapa_cajeros=mapa_c)
        else:
            st.button("✅ Todo Confirmado", disabled=True, use_container_width=True, help="No hay transacciones pendientes bajo este filtro")

def _renderizar_lista_transacciones(df_list, key_prefix="act"):
    """Renderiza tarjetas limpias de transacciones con confirmación y reversión directa en 1 clic."""
    if df_list.empty:
        st.info("ℹ️ No hay transacciones que coincidan con los filtros seleccionados.")
        return

    mapa_cajeros = obtener_mapa_cajeros()
    current_usr = obtener_nombre_usuario_actual()

    for idx_pos, (_, row) in enumerate(df_list.iterrows(), start=1):
        is_c = bool(row.get("confirmado", False))
        conf_por = str(row.get("confirmado_por") or row.get("supervisor_nombre") or "").strip()
        
        cat_str = str(row.get("categoria", "")).upper()
        if "GASTO" in cat_str:
            color_monto = "#f43f5e"
            icon_cat = "💸"
        elif "EFECTIVO" in cat_str:
            color_monto = "#22c55e"
            icon_cat = "💵"
        else:
            color_monto = "#38bdf8"
            icon_cat = "💳"

        if is_c:
            badge_estado = "<span style='background: rgba(34, 197, 94, 0.15); color: #22c55e; border: 1px solid rgba(34, 197, 94, 0.3); padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 800;'>✅ CONFIRMADO</span>"
        else:
            badge_estado = "<span style='background: rgba(234, 179, 8, 0.15); color: #eab308; border: 1px solid rgba(234, 179, 8, 0.3); padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 800;'>⏳ PENDIENTE</span>"

        num_badge = f"<span style='background: rgba(56, 189, 248, 0.12); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.25); padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 800; margin-right: 6px;'>#{idx_pos}</span>"

        conf_info_text = f"<br><small style='color: #22c55e; font-weight: 600;'>👤 Confirmado por: <b>{conf_por}</b></small>" if (is_c and conf_por) else ""

        with st.container(border=True):
            col_info, col_monto, col_action = st.columns([5, 3, 2])

            with col_info:
                st.markdown(
                    f"{num_badge} 🏢 **{row['agencia']}** | 👤 Cajero: **{row['cajero_nombre']}** | 📅 {row['fecha']}<br>"
                    f"<small style='color: #94a3b8;'>{icon_cat} <b>{row['categoria']}</b> | Método: <b>{row['metodo']}</b></small><br>"
                    f"<small>Concepto: <b>{row['concepto']}</b> | Ref: <b>{row['referencia']}</b> | Pagador: <b>{row['pagador']}</b></small>"
                    f"{conf_info_text}",
                    unsafe_allow_html=True
                )

            with col_monto:
                st.markdown(
                    f"<div style='text-align: right; padding-right: 8px;'>"
                    f"<span style='font-size: 17px; font-weight: 800; color: {color_monto};'>{row['moneda']} {row['monto']:,.2f}</span><br>"
                    f"<div style='margin-top: 4px;'>{badge_estado}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )

            with col_action:
                btn_key = f"btn_conf_{key_prefix}_{row['tabla']}_{row['id']}"
                if not is_c:
                    if st.button("✅ Confirmar", key=btn_key, type="primary", use_container_width=True):
                        ok, err = _confirmar_registro_individual(row, current_usr, mapa_cajeros)
                        if ok:
                            st.success(f"✅ Confirmado por {current_usr}")
                            time.sleep(0.4)
                            st.rerun()
                        else:
                            st.error(f"❌ Error: {err}")
                else:
                    if st.button("↩️ Revertir", key=btn_key, use_container_width=True):
                        ok, err = _revertir_registro_individual(row)
                        if ok:
                            st.info("↩️ Registro devuelto a Pendiente")
                            time.sleep(0.4)
                            st.rerun()
                        else:
                            st.error(f"❌ Error: {err}")

def _renderizar_caja_acumulada_supervisor(u_id, existe_supervisor=True, agencias_permitidas=None):
    """Pestaña 2: Arqueo y Control de Efectivo, Balances por Agencia, Liquidación e Histórico estrictamente restringido al paraguas."""
    _sincronizar_efectivo_supervisor_con_pagos(u_id=u_id, existe_supervisor=existe_supervisor, agencias_permitidas=agencias_permitidas)

    totales_pend_sup = {"BS": 0.0, "USD": 0.0, "COP": 0.0}
    totales_rec_sup = {"BS": 0.0, "USD": 0.0, "COP": 0.0}
    totales_conf_admin = {"BS": 0.0, "USD": 0.0, "COP": 0.0}

    movs_lista = []
    pagos_ids_en_movs = set()
    mapa_cajeros_movs = obtener_mapa_cajeros(u_id)
    mapa_pd = {}

    try:
        q_pd = supabase.table("cda_pagos_diarios").select("*")
        if u_id:
            try:
                q_pd = q_pd.eq("user_id", u_id)
            except Exception:
                pass
        res_pd_all = q_pd.execute()
        if res_pd_all.data:
            for p in res_pd_all.data:
                ag_p = str(p.get("agencia") or "").upper().strip()
                if agencias_permitidas and ag_p not in agencias_permitidas:
                    continue
                if p.get("id") is not None:
                    mapa_pd[str(p["id"])] = p
    except Exception:
        pass

    try:
        q_m = supabase.table("cda_caja_efectivo_supervisor").select("*")
        if u_id:
            try:
                q_m = q_m.eq("user_id", u_id)
            except Exception:
                pass
        res_movs = q_m.execute()
        if res_movs.data:
            for rm in res_movs.data:
                rm_copy = dict(rm)
                ag_m = str(rm_copy.get("agencia") or "").upper().strip()
                
                # Filtrar movimientos pertenecientes al paraguas
                if agencias_permitidas and ag_m not in agencias_permitidas and ag_m != "TODAS":
                    continue

                pid_str = str(rm_copy.get("pago_id") or "")
                p_asoc = mapa_pd.get(pid_str, {}) if pid_str else {}
                
                sup_nom_curr = str(rm_copy.get("supervisor_nombre") or "").strip()
                if sup_nom_curr in ["", "None", "Cajero", "SYSTEM"]:
                    cid = str(rm_copy.get("user_id") or p_asoc.get("cajero_id") or p_asoc.get("user_id") or "").strip()
                    nombre_res = resolver_nombre_cajero(cid, pago_dict=p_asoc, mapa=mapa_cajeros_movs)
                    if nombre_res and nombre_res != "Cajero":
                        rm_copy["supervisor_nombre"] = nombre_res

                movs_lista.append(rm_copy)
                if rm_copy.get("pago_id") is not None:
                    pagos_ids_en_movs.add(str(rm_copy["pago_id"]))
                
                mon_m = normalizar_moneda(rm_copy.get("moneda"))
                monto_m = float(rm_copy.get("monto") or 0.0)
                tipo_m = str(rm_copy.get("tipo_movimiento") or "").upper()

                if tipo_m == "ENTREGA_ADMIN":
                    totales_rec_sup[mon_m] -= monto_m
                    totales_conf_admin[mon_m] += monto_m
                elif tipo_m == "ENTRADA_CAJERO" and rm_copy.get("pago_id") is None:
                    totales_rec_sup[mon_m] += monto_m
    except Exception:
        pass

    if mapa_pd:
        for pid, pago in mapa_pd.items():
            ag_p = str(pago.get("agencia") or "").upper().strip()
            if agencias_permitidas and ag_p not in agencias_permitidas:
                continue

            cat_val = str(pago.get("categoria") or "").upper()
            tipo = str(pago.get("tipo_pago") or pago.get("metodo") or "").upper()
            es_efectivo = "EFECTIVO" in cat_val or "EFECTIVO" in tipo or ("REF:" not in tipo and "PUNTO" not in tipo and "TRANSFERENCIA" not in tipo and "ZELLE" not in tipo and "PAGO MÓVIL" not in tipo)

            if es_efectivo:
                is_conf = bool(pago.get("confirmado", False)) or bool(pago.get("confirmado_supervisor", False))
                monto_val = float(pago.get("monto") or 0.0)
                moneda_val = normalizar_moneda(pago.get("moneda"))
                
                cid = str(pago.get("cajero_id") or pago.get("user_id") or "").strip()
                c_nom = resolver_nombre_cajero(cid, pago_dict=pago, mapa=mapa_cajeros_movs)
                sup_nom = str(pago.get("supervisor_nombre") or c_nom).strip()
                if sup_nom in ["", "None", "Cajero", "SYSTEM"]:
                    sup_nom = c_nom

                u_id_val = str(pago.get("user_id") or "SYSTEM").strip()
                f_val = str(pago.get("fecha") or "")

                if pid and pid not in pagos_ids_en_movs:
                    movs_lista.append({
                        "id": f"pd_{pid}",
                        "pago_id": pid,
                        "user_id": u_id_val,
                        "agencia": ag_p,
                        "supervisor_nombre": sup_nom,
                        "tipo_movimiento": "ENTRADA_CAJERO",
                        "monto": monto_val,
                        "moneda": moneda_val,
                        "comentario": f"Pago Cajero #{pid}",
                        "fecha": f_val
                    })

                if is_conf:
                    totales_rec_sup[moneda_val] += monto_val
                else:
                    totales_pend_sup[moneda_val] += monto_val

    for m in ["BS", "USD", "COP"]:
        totales_rec_sup[m] = max(0.0, totales_rec_sup[m])

    # 1. TARJETAS DE BALANCE DE EFECTIVO
    st.markdown("<div style='font-size: 14px; font-weight: 800; color: #38bdf8; margin-bottom: 8px;'>📦 Balance y Fondo de Efectivo en Caja</div>", unsafe_allow_html=True)
    c_b1, c_b2, c_b3, c_b4 = st.columns([3, 3, 3, 3])
    with c_b1:
        st.markdown(f"""
            <div style="background: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 8px; padding: 10px 14px;">
                <div style="font-size: 10px; font-weight: 700; color: #94a3b8;">🇻🇪 EFECTIVO EN CAJA (BS)</div>
                <div style="font-size: 16px; font-weight: 800; color: #38bdf8; margin-top: 4px;">Bs {totales_rec_sup['BS']:,.2f}</div>
            </div>
        """, unsafe_allow_html=True)
    with c_b2:
        st.markdown(f"""
            <div style="background: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 8px; padding: 10px 14px;">
                <div style="font-size: 10px; font-weight: 700; color: #94a3b8;">💵 EFECTIVO EN CAJA (USD)</div>
                <div style="font-size: 16px; font-weight: 800; color: #38bdf8; margin-top: 4px;">${totales_rec_sup['USD']:,.2f}</div>
            </div>
        """, unsafe_allow_html=True)
    with c_b3:
        st.markdown(f"""
            <div style="background: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 8px; padding: 10px 14px;">
                <div style="font-size: 10px; font-weight: 700; color: #94a3b8;">🇨🇴 EFECTIVO EN CAJA (COP)</div>
                <div style="font-size: 16px; font-weight: 800; color: #38bdf8; margin-top: 4px;">COP {totales_rec_sup['COP']:,.2f}</div>
            </div>
        """, unsafe_allow_html=True)
    with c_b4:
        with st.popover("💸 Entregar a Administración", use_container_width=True):
            st.markdown("##### 💸 Liquidación de Efectivo a Administración")
            moneda_liq = st.selectbox("Moneda a Liquidar:", ["COP", "USD", "BS"], key="liq_moneda_sup_tab")
            monto_liq = st.number_input(f"Monto a Entregar ({moneda_liq}):", min_value=0.0, value=float(totales_rec_sup.get(moneda_liq, 0.0)), key="liq_monto_sup_tab")
            ag_entrega = agencias_permitidas[0] if (agencias_permitidas and len(agencias_permitidas) == 1) else "TODAS"
            nota_liq = st.text_input("Nota / Comentario:", value=f"Entrega de caja {ag_entrega} a Administración", key="liq_nota_sup_tab")
            
            if st.button("🚀 Confirmar Entrega a Admin", key="btn_confirm_liq_admin_tab", type="primary", use_container_width=True):
                if monto_liq <= 0:
                    st.error("⚠️ El monto a entregar debe ser mayor a 0.")
                else:
                    curr_usr = obtener_nombre_usuario_actual()
                    u_id_val = str(u_id or "SYSTEM")
                    mon_norm = normalizar_moneda(moneda_liq)
                    try:
                        supabase.table("cda_caja_efectivo_supervisor").insert({
                            "user_id": u_id_val,
                            "agencia": ag_entrega,
                            "supervisor_nombre": curr_usr,
                            "tipo_movimiento": "ENTREGA_ADMIN",
                            "monto": float(monto_liq),
                            "moneda": mon_norm,
                            "comentario": nota_liq
                        }).execute()
                        st.success(f"✅ Entrega de {mon_norm} {monto_liq:,.2f} registrada correctamente por {curr_usr}.")
                        time.sleep(0.5)
                        st.rerun()
                    except Exception as ex_l:
                        err_str = str(ex_l).lower()
                        if "42501" in err_str or "row-level security" in err_str:
                            st.error("🔒 **Políticas RLS Requeridas:** La tabla `cda_caja_efectivo_supervisor` requiere habilitar sus políticas seguras.")
                            st.caption("Ejecuta estas políticas en el **SQL Editor** de Supabase para autorizar las operaciones de forma segura:")
                            st.code("""ALTER TABLE cda_caja_efectivo_supervisor ENABLE ROW LEVEL SECURITY;
CREATE POLICY "cda_caja_sup_all_policy" ON cda_caja_efectivo_supervisor
    FOR ALL USING (user_id IS NOT NULL AND length(user_id) > 0)
    WITH CHECK ((user_id IS NOT NULL AND length(user_id) > 0) AND monto >= 0);""", language="sql")
                        else:
                            st.error(f"❌ Error al registrar liquidación: {ex_l}")

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # 2. RESUMEN DE EFECTIVO POR AGENCIA (SOLO DEL PARAGUAS)
    st.markdown("<div style='font-size: 14px; font-weight: 800; color: #f8fafc; margin-bottom: 6px;'>🏛️ Resumen de Efectivo por Agencia</div>", unsafe_allow_html=True)
    if movs_lista:
        df_movs = pd.DataFrame(movs_lista)
        df_movs["moneda_norm"] = df_movs["moneda"].apply(normalizar_moneda)
        df_movs["agencia_norm"] = df_movs["agencia"].astype(str).str.upper().str.strip()
        
        df_pd_all = pd.DataFrame()
        try:
            q_pd2 = supabase.table("cda_pagos_diarios").select("*")
            if u_id:
                try:
                    q_pd2 = q_pd2.eq("user_id", u_id)
                except Exception:
                    pass
            res_pd_all = q_pd2.execute()
            if res_pd_all.data:
                df_pd_all = pd.DataFrame(res_pd_all.data)
        except Exception:
            pass

        resumen_agencias = []
        target_ags = agencias_permitidas if agencias_permitidas else sorted(set(df_movs["agencia_norm"].unique()))

        for ag in sorted(target_ags):
            if not ag or ag in ["NONE", "TODAS"]:
                continue

            sub_pd = df_pd_all[df_pd_all["agencia"].astype(str).str.upper().str.strip() == ag] if (not df_pd_all.empty and "agencia" in df_pd_all.columns) else pd.DataFrame()
            
            if not sub_pd.empty:
                sub_pd["moneda_norm"] = sub_pd["moneda"].apply(normalizar_moneda)
                sub_pd = sub_pd[sub_pd.apply(lambda r: "EFECTIVO" in str(r.get("categoria","")).upper() or "EFECTIVO" in str(r.get("tipo_pago","")).upper() or ("REF:" not in str(r.get("tipo_pago","")).upper() and "PUNTO" not in str(r.get("tipo_pago","")).upper() and "TRANSFERENCIA" not in str(r.get("tipo_pago","")).upper() and "ZELLE" not in str(r.get("tipo_pago","")).upper() and "PAGO MÓVIL" not in str(r.get("tipo_pago","")).upper()), axis=1)]

            p_bs = sub_pd[(sub_pd["moneda_norm"] == "BS") & (sub_pd["confirmado"] == False) & (sub_pd.get("confirmado_supervisor", False) == False)]["monto"].sum() if not sub_pd.empty else 0.0
            c_bs = sub_pd[(sub_pd["moneda_norm"] == "BS") & ((sub_pd["confirmado"] == True) | (sub_pd.get("confirmado_supervisor", False) == True))]["monto"].sum() if not sub_pd.empty else 0.0

            p_usd = sub_pd[(sub_pd["moneda_norm"] == "USD") & (sub_pd["confirmado"] == False) & (sub_pd.get("confirmado_supervisor", False) == False)]["monto"].sum() if not sub_pd.empty else 0.0
            c_usd = sub_pd[(sub_pd["moneda_norm"] == "USD") & ((sub_pd["confirmado"] == True) | (sub_pd.get("confirmado_supervisor", False) == True))]["monto"].sum() if not sub_pd.empty else 0.0

            p_cop = sub_pd[(sub_pd["moneda_norm"] == "COP") & (sub_pd["confirmado"] == False) & (sub_pd.get("confirmado_supervisor", False) == False)]["monto"].sum() if not sub_pd.empty else 0.0
            c_cop = sub_pd[(sub_pd["moneda_norm"] == "COP") & ((sub_pd["confirmado"] == True) | (sub_pd.get("confirmado_supervisor", False) == True))]["monto"].sum() if not sub_pd.empty else 0.0

            resumen_agencias.append({
                "Agencia": ag,
                "Pendiente (Bs / $ / COP)": f"Bs {float(p_bs):,.2f} | ${float(p_usd):,.2f} | COP {float(p_cop):,.2f}",
                "Confirmado en Caja (Bs / $ / COP)": f"Bs {float(c_bs):,.2f} | ${float(c_usd):,.2f} | COP {float(c_cop):,.2f}"
            })

        if resumen_agencias:
            st.dataframe(pd.DataFrame(resumen_agencias), use_container_width=True, hide_index=True)

        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

        # 3. HISTÓRICO DE MOVIMIENTOS DE CAJA (SOLO DEL PARAGUAS)
        st.markdown("<div style='font-size: 14px; font-weight: 800; color: #f8fafc; margin-bottom: 6px;'>📜 Histórico de Movimientos de Caja</div>", unsafe_allow_html=True)
        cols_req = ["fecha", "agencia", "supervisor_nombre", "tipo_movimiento", "monto", "moneda_norm", "comentario"]
        for col in cols_req:
            if col not in df_movs.columns:
                df_movs[col] = ""
        df_disp_movs = df_movs[cols_req].copy()
        df_disp_movs.columns = ["Fecha / Hora", "Agencia", "Responsable", "Tipo Movimiento", "Monto", "Moneda", "Comentario"]
        
        # Filtro estricto por agencias del paraguas en la visualización
        if agencias_permitidas:
            df_disp_movs = df_disp_movs[df_disp_movs["Agencia"].astype(str).str.upper().str.strip().isin(agencias_permitidas) | (df_disp_movs["Agencia"].astype(str).str.upper().str.strip() == "TODAS")]

        df_disp_movs["Monto"] = df_disp_movs["Monto"].apply(lambda m: f"{float(m or 0.0):,.2f}")
        df_disp_movs = df_disp_movs.sort_values(by="Fecha / Hora", ascending=False)
        st.dataframe(df_disp_movs.head(50), use_container_width=True, hide_index=True)
    else:
        st.info("ℹ️ No hay movimientos registrados en la Caja de Efectivo aún.")

def modulo_pizarra(agencia_data=None):
    return modulo_pizarra_confirmaciones(agencia_data)

def modulo_pizarra_confirmaciones(agencia_data=None):
    st.html("""
        <style>
        .stMetric { background: rgba(255, 255, 255, 0.03); padding: 8px 12px !important; border-radius: 8px; border: 1px solid rgba(255,255,255,0.08); }
        .stMetric label { font-size: 0.75rem !important; opacity: 0.8; }
        .stMetric div[data-testid="stMetricValue"] { font-size: 1.2rem !important; font-weight: 700 !important; }
        </style>
    """)

    cajero_info = st.session_state.get("cajero_actual", {})
    ag_info = agencia_data or st.session_state.get("agencia_actual", {})
    u_id = str(ag_info.get("user_id") or cajero_info.get("id") or "").strip()

    if not u_id and "user" in st.session_state and hasattr(st.session_state["user"], "id"):
        u_id = str(st.session_state["user"].id).strip()

    rol_usuario = str(cajero_info.get("rol", "")).lower()
    es_supervisor = (rol_usuario == "supervisor")
    existe_sup = verificar_existe_supervisor(u_id)

    # Obtener el paraguas de agencias autorizadas para este usuario/terminal
    agencias_paraguas = obtener_agencias_paraguas_usuario(u_id, agencia_data=ag_info)

    # Cabecera principal compacta
    titulo_sub = f" ({', '.join(agencias_paraguas)})" if len(agencias_paraguas) == 1 else ""
    st.markdown(f"<h3 style='font-size: 20px; font-weight: 800; margin-bottom: 2px;'>📌 Pizarra de Confirmaciones y Arqueo{titulo_sub}</h3>", unsafe_allow_html=True)
    st.caption("Verificación directa en 1 clic de **Transferencias**, **Punto de Venta**, **Gastos** y **Caja de Efectivo**.")

    _check_confirmado_cols_cms()

    # Período de ciclo actual
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

    # Configuración de lista de agencias según el paraguas
    if len(agencias_paraguas) > 1:
        lista_agencias = ["Todas"] + agencias_paraguas
    elif len(agencias_paraguas) == 1:
        lista_agencias = agencias_paraguas
    else:
        lista_agencias = ["Todas"]

    # Cargar cajeros
    mapa_cajeros = obtener_mapa_cajeros(u_id)
    lista_cajeros = ["Todos"]
    for unombre in sorted(set(mapa_cajeros.values())):
        if unombre and unombre not in lista_cajeros:
            lista_cajeros.append(unombre)

    # Fetch datos de Supabase
    df_bancarios = pd.DataFrame()
    df_gastos = pd.DataFrame()
    df_pagos_diarios = pd.DataFrame()

    try:
        q_pb = supabase.table("cda_pagos_bancarios").select("*")
        if u_id:
            try:
                q_pb = q_pb.eq("user_id", u_id)
            except Exception:
                pass
        res_pb = q_pb.execute()
        df_bancarios = pd.DataFrame(res_pb.data or [])
    except Exception:
        pass

    try:
        q_g = supabase.table("cda_gastos_diarios").select("*")
        if u_id:
            try:
                q_g = q_g.eq("user_id", u_id)
            except Exception:
                pass
        res_g = q_g.execute()
        df_gastos = pd.DataFrame(res_g.data or [])
    except Exception:
        pass

    try:
        q_pd = supabase.table("cda_pagos_diarios").select("*")
        if u_id:
            try:
                q_pd = q_pd.eq("user_id", u_id)
            except Exception:
                pass
        res_pd = q_pd.execute()
        df_pagos_diarios = pd.DataFrame(res_pd.data or [])
    except Exception:
        pass

    # Normalizar transacciones
    registros = []

    # 1. Pagos Bancarios
    if not df_bancarios.empty:
        df_bancarios.columns = [c.lower().strip() for c in df_bancarios.columns]
        for _, r in df_bancarios.iterrows():
            ag_r = str(r.get("agencia") or "").upper().strip()
            # Filtrar por paraguas
            if agencias_paraguas and ag_r not in agencias_paraguas:
                continue

            r_dict = r.to_dict()
            cid = str(r.get("cajero_id") or r.get("user_id") or "").strip()
            c_nombre = resolver_nombre_cajero(cid, pago_dict=r_dict, mapa=mapa_cajeros)
            metodo_raw = str(r.get("metodo_pago") or "Bancario").strip().upper()
            metodo = "TRANSFERENCIA" if "TRANSFERENCIA" in metodo_raw else metodo_raw
            
            cat_db = str(r.get("categoria") or "").strip()
            if cat_db:
                cat = cat_db
            elif "PUNTO" in metodo:
                cat = "Punto de Venta"
            else:
                cat = "Bancos (Transferencia/POS/Zelle)"

            is_conf = bool(r.get("confirmado", False)) or bool(r.get("confirmado_supervisor", False))
            conf_por = str(r.get("confirmado_por") or r.get("supervisor_nombre") or "").strip()

            registros.append({
                "id": r.get("id"),
                "tabla": "cda_pagos_bancarios",
                "fecha": str(r.get("fecha") or ""),
                "agencia": ag_r,
                "cajero_id": cid,
                "cajero_nombre": c_nombre,
                "categoria": cat,
                "metodo": metodo,
                "concepto": str(r.get("concepto") or "Pago Bancario"),
                "referencia": str(r.get("referencia") or "N/A"),
                "pagador": str(r.get("datos_pagador") or "N/A"),
                "monto": float(r.get("monto") or 0.0),
                "moneda": normalizar_moneda(r.get("moneda") or "USD"),
                "confirmado": is_conf,
                "confirmado_por": conf_por
            })

    # 2. Gastos
    if not df_gastos.empty:
        df_gastos.columns = [c.lower().strip() for c in df_gastos.columns]
        for _, r in df_gastos.iterrows():
            ag_nom = str(r.get("agencia") or r.get("nombre_agency") or "").upper().strip()
            # Filtrar por paraguas
            if agencias_paraguas and ag_nom not in agencias_paraguas:
                continue

            r_dict = r.to_dict()
            cid = str(r.get("cajero_id") or r.get("user_id") or "").strip()
            c_nombre = resolver_nombre_cajero(cid, pago_dict=r_dict, mapa=mapa_cajeros)
            is_conf = bool(r.get("confirmado", False)) or bool(r.get("confirmado_supervisor", False))
            conf_por = str(r.get("confirmado_por") or r.get("supervisor_nombre") or "").strip()

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
                "monto": float(r.get("monto") or 0.0),
                "moneda": normalizar_moneda(r.get("moneda") or "USD"),
                "confirmado": is_conf,
                "confirmado_por": conf_por
            })

    # 3. Pagos de cda_pagos_diarios (Efectivo)
    if not df_pagos_diarios.empty:
        df_pagos_diarios.columns = [c.lower().strip() for c in df_pagos_diarios.columns]
        for _, r in df_pagos_diarios.iterrows():
            ag_nom = str(r.get("agencia") or r.get("nombre_agency") or "").upper().strip()
            # Filtrar por paraguas
            if agencias_paraguas and ag_nom not in agencias_paraguas:
                continue

            r_dict = r.to_dict()
            cid = str(r.get("cajero_id") or r.get("user_id") or "").strip()
            c_nombre = resolver_nombre_cajero(cid, pago_dict=r_dict, mapa=mapa_cajeros)
            is_conf = bool(r.get("confirmado", False)) or bool(r.get("confirmado_supervisor", False))
            conf_por = str(r.get("confirmado_por") or r.get("supervisor_nombre") or "").strip()

            tipo = str(r.get("tipo_pago") or "").strip()
            registros.append({
                "id": r.get("id"),
                "tabla": "cda_pagos_diarios",
                "fecha": str(r.get("fecha") or ""),
                "agencia": ag_nom,
                "cajero_id": cid,
                "cajero_nombre": c_nombre,
                "categoria": "Efectivo",
                "metodo": tipo or "EFECTIVO",
                "concepto": tipo if tipo else "Pago Efectivo",
                "referencia": str(r.get("referencia") or "N/A"),
                "pagador": str(r.get("datos_pagador") or "N/A"),
                "monto": float(r.get("monto") or 0.0),
                "moneda": normalizar_moneda(r.get("moneda") or "USD"),
                "confirmado": is_conf,
                "confirmado_por": conf_por
            })

    df_raw = pd.DataFrame(registros)

    if df_raw.empty:
        st.info("ℹ️ No hay transacciones registradas bajo tu paraguas de agencias.")
        return

    df_raw["fecha_str"] = df_raw["fecha"].astype(str).str.slice(0, 10)
    df_activo = df_raw[(df_raw["confirmado"] == False) | (df_raw["fecha_str"] >= ciclo_desde_str)].copy()

    # -------------------------------------------------------------
    # 1. CABECERA Y FILTROS COMPACTOS (1 Sola Fila)
    # -------------------------------------------------------------
    f_hasta_default = max(hoy, ciclo_hasta_dt)
    
    col_f1, col_f2, col_f3, col_f4, col_f5, col_f6 = st.columns([2, 2, 2, 2, 2, 2])
    with col_f1:
        f_desde = st.date_input("📅 Desde:", value=ciclo_desde_dt, key="pizarra_f_desde_compact")
    with col_f2:
        f_hasta = st.date_input("📅 Hasta:", value=f_hasta_default, key="pizarra_f_hasta_compact")
    with col_f3:
        sel_agencia = st.selectbox("🏢 Agencia:", lista_agencias, key="pizarra_agencia_sel_compact")
    with col_f4:
        sel_cajero = st.selectbox("👤 Cajero:", lista_cajeros, key="pizarra_cajero_sel_compact")
    with col_f5:
        sel_tipo = st.selectbox("💳 Tipo:", ["Todas", "Bancos (Transferencias/POS/Zelle)", "Gastos", "Efectivo"], key="pizarra_tipo_sel_compact")
    with col_f6:
        sel_estado = st.selectbox("🚦 Estado:", ["⏳ Pendientes", "✅ Confirmados", "Todos"], key="pizarra_estado_sel_compact")

    f_desde_str, f_hasta_str = str(f_desde), str(f_hasta)

    df_act_work = df_activo.copy()

    if not df_act_work.empty:
        df_act_work = df_act_work[(df_act_work["fecha_str"] >= f_desde_str) & (df_act_work["fecha_str"] <= f_hasta_str)]

    if sel_agencia != "Todas" and not df_act_work.empty:
        df_act_work = df_act_work[df_act_work["agencia"] == sel_agencia]

    if sel_cajero != "Todos" and not df_act_work.empty:
        df_act_work = df_act_work[df_act_work["cajero_nombre"] == sel_cajero]

    if sel_tipo != "Todas" and not df_act_work.empty:
        if sel_tipo == "Gastos":
            df_act_work = df_act_work[df_act_work["categoria"] == "Gastos"]
        elif sel_tipo == "Efectivo":
            df_act_work = df_act_work[df_act_work["categoria"] == "Efectivo"]
        else: # Bancos
            df_act_work = df_act_work[df_act_work["categoria"].isin(["Bancos (Transferencia/POS/Zelle)", "Punto de Venta", "Transferencia / Zelle / Pago Móvil"])]

    if sel_estado == "⏳ Pendientes" and not df_act_work.empty:
        df_act_work = df_act_work[df_act_work["confirmado"] == False]
    elif sel_estado == "✅ Confirmados" and not df_act_work.empty:
        df_act_work = df_act_work[df_act_work["confirmado"] == True]

    if "fecha" in df_act_work.columns and not df_act_work.empty:
        df_act_work = df_act_work.sort_values(by="fecha", ascending=False)

    st.markdown("---")

    # -------------------------------------------------------------
    # 2. ORGANIZACIÓN EN 2 PESTAÑAS CLARAS
    # -------------------------------------------------------------
    tab_conf, tab_arqueo = st.tabs(["⚡ Confirmaciones Rápidas", "📦 Arqueo y Control de Efectivo"])

    with tab_conf:
        # Barra de Métricas Unificada y Minimalista
        df_pendientes_visibles = df_act_work[df_act_work["confirmado"] == False] if not df_act_work.empty else pd.DataFrame()
        _renderizar_resumen_metricas(df_act_work, df_pendientes_visibles)

        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

        # Lista de Transacciones Limpia
        st.markdown("<div style='font-size: 15px; font-weight: 800; color: #f8fafc; margin-bottom: 8px;'>📋 Transacciones Filtradas</div>", unsafe_allow_html=True)
        _renderizar_lista_transacciones(df_act_work, key_prefix="act")

    with tab_arqueo:
        _renderizar_caja_acumulada_supervisor(u_id, existe_supervisor=existe_sup, agencias_permitidas=agencias_paraguas)
