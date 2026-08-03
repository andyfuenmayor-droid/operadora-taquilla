import os
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime

# Local native Streamlit component declaration
parent_dir = os.path.dirname(os.path.abspath(__file__))
build_dir = os.path.join(parent_dir, "component_firma")
_componente_firma_native = components.declare_component("componente_firma_native", path=build_dir)

def renderizar_canvas_firma(key="firma_default", titulo="✍️ Firma Digital", height=185):
    """
    Renders native Streamlit HTML5 Canvas component.
    Returns the base64 PNG string of captured signature directly to Streamlit Python on stroke release.
    """
    return _componente_firma_native(key=key)

def renderizar_formulario_pago_cajero_unificado(ag_nombre, u_id, cajero_id, fecha_filtro_str):
    """Fallback alias"""
    pass

def renderizar_popover_supervisor_unificado(pago_id, ag_nombre, cajero_nombre, monto_str, moneda_str):
    """Fallback alias"""
    pass

def renderizar_comprobante_firma(firma_b64=None, supervisor_nombre="Supervisor", fecha_str=None, monto_str=None, moneda_str=None, firma_cajero_b64=None, cajero_nombre="Cajero"):
    """
    Renders a visual card displaying captured digital signatures (Cajero and/or Supervisor).
    """
    if not fecha_str:
        fecha_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    monto_html = f"<div style='font-size: 15px; font-weight: 800; color: #22c55e; margin-bottom: 6px;'>💵 Monto Registrado: {moneda_str or ''} {monto_str}</div>" if monto_str else ""

    boxes_html = ""
    if firma_cajero_b64:
        boxes_html += f"""
        <div style="flex: 1; min-width: 150px; background: #0b1325; border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 8px; padding: 6px 10px; text-align: center;">
            <div style="font-size: 10px; color: #38bdf8; font-weight: 700; text-transform: uppercase;">✍️ Firma Cajero: {cajero_nombre or 'Cajero'}</div>
            <img src="{firma_cajero_b64}" style="max-height: 50px; max-width: 160px; display: block; margin: 4px auto;" alt="Firma Cajero"/>
            <div style="font-size: 8.5px; color: #64748b; font-weight: 600;">ENVIADO Y FIRMADO POR CAJERO</div>
        </div>
        """

    if firma_b64:
        boxes_html += f"""
        <div style="flex: 1; min-width: 150px; background: #0b1325; border: 1px solid rgba(34, 197, 94, 0.3); border-radius: 8px; padding: 6px 10px; text-align: center;">
            <div style="font-size: 10px; color: #22c55e; font-weight: 700; text-transform: uppercase;">🔏 Firma Supervisor: {supervisor_nombre or 'Supervisor'}</div>
            <img src="{firma_b64}" style="max-height: 50px; max-width: 160px; display: block; margin: 4px auto;" alt="Firma Supervisor"/>
            <div style="font-size: 8.5px; color: #22c55e; font-weight: 700;">RECIBIDO Y VALIDADO POR SUPERVISOR</div>
        </div>
        """

    if not boxes_html and firma_b64:
        boxes_html = f"""
        <div style="flex: 1; min-width: 150px; background: #0b1325; border: 1px solid rgba(34, 197, 94, 0.3); border-radius: 8px; padding: 6px 10px; text-align: center;">
            <img src="{firma_b64}" style="max-height: 50px; max-width: 160px; display: block; margin: 4px auto;" alt="Firma Digital"/>
        </div>
        """

    st.markdown(
        f"""
        <div style="background: rgba(15, 23, 42, 0.75); border: 1px dashed rgba(56, 189, 248, 0.4); border-radius: 12px; padding: 12px 16px; margin-top: 8px;">
            <div style="font-size: 11px; font-weight: 700; color: #38bdf8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px;">
                📜 COMPROBANTE DE ENTREGA Y VALIDACIÓN DE EFECTIVO
            </div>
            {monto_html}
            <div style="font-size: 11px; color: #94a3b8; margin-bottom: 8px;">📅 Fecha Operativa: <b>{fecha_str}</b></div>
            <div style="display: flex; gap: 12px; flex-wrap: wrap; align-items: center; justify-content: space-between;">
                {boxes_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
