import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime

def renderizar_canvas_firma(key="firma_sup", titulo="✍️ Firma Digital de Validación", height=270):
    """
    Renders an HTML5 Canvas signature pad supporting touch and mouse.
    Returns the base64 PNG string of the captured signature or None.
    """
    # 1. Check if signature was submitted via URL params
    if "firma_captured" in st.query_params:
        f_key = st.query_params.get("firma_key")
        if f_key == key or not f_key:
            captured_b64 = st.query_params["firma_captured"]
            st.session_state[f"firma_val_{key}"] = captured_b64
            # Clean query params safely
            try:
                del st.query_params["firma_captured"]
                if "firma_key" in st.query_params:
                    del st.query_params["firma_key"]
            except Exception:
                pass
            st.rerun()

    current_firma = st.session_state.get(f"firma_val_{key}")

    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no"/>
    <style>
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        padding: 0;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        background: transparent;
        color: #f8fafc;
      }}
      .signature-box {{
        background: rgba(15, 23, 42, 0.95);
        border: 1px solid rgba(56, 189, 248, 0.3);
        border-radius: 12px;
        padding: 12px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.4);
      }}
      .header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
      }}
      .title {{
        font-size: 13px;
        font-weight: 700;
        color: #38bdf8;
      }}
      .badge {{
        font-size: 10px;
        background: rgba(56, 189, 248, 0.15);
        color: #38bdf8;
        padding: 2px 6px;
        border-radius: 4px;
        font-weight: 600;
      }}
      canvas {{
        background: #0b1325;
        border: 1.5px dashed rgba(255, 255, 255, 0.2);
        border-radius: 8px;
        touch-action: none;
        cursor: crosshair;
        width: 100%;
        height: 140px;
        display: block;
      }}
      .controls {{
        display: flex;
        gap: 8px;
        margin-top: 10px;
      }}
      button {{
        flex: 1;
        padding: 9px 12px;
        border-radius: 6px;
        border: none;
        font-weight: 700;
        font-size: 12px;
        cursor: pointer;
        transition: all 0.2s ease;
      }}
      .btn-clear {{
        background: rgba(244, 63, 94, 0.15);
        color: #f43f5e;
        border: 1px solid rgba(244, 63, 94, 0.3);
      }}
      .btn-clear:hover {{
        background: rgba(244, 63, 94, 0.3);
      }}
      .btn-save {{
        background: #00c853;
        color: #071217;
      }}
      .btn-save:hover {{
        background: #69f0ae;
      }}
      .hint {{
        font-size: 11px;
        color: #64748b;
        margin-top: 5px;
        text-align: center;
      }}
    </style>
    </head>
    <body>
    <div class="signature-box">
      <div class="header">
        <span class="title">{titulo}</span>
        <span class="badge">📱 TÁCTIL / MOUSE</span>
      </div>
      <canvas id="sigCanvas"></canvas>
      <div class="hint">✏️ Dibuje su firma con su dedo, stylus o ratón dentro del recuadro</div>
      <div class="controls">
        <button type="button" class="btn-clear" id="btnClear">🧹 Limpiar</button>
        <button type="button" class="btn-save" id="btnSave">✅ Registrar Firma</button>
      </div>
    </div>

    <script>
      const canvas = document.getElementById('sigCanvas');
      const ctx = canvas.getContext('2d');
      let drawing = false;
      let hasStrokes = false;

      function resizeCanvas() {{
        const rect = canvas.getBoundingClientRect();
        canvas.width = rect.width;
        canvas.height = 140;
        ctx.strokeStyle = '#38bdf8';
        ctx.lineWidth = 2.8;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
      }}
      window.addEventListener('resize', resizeCanvas);
      setTimeout(resizeCanvas, 40);

      function getPos(e) {{
        const rect = canvas.getBoundingClientRect();
        let clientX = e.clientX;
        let clientY = e.clientY;
        if (e.touches && e.touches.length > 0) {{
          clientX = e.touches[0].clientX;
          clientY = e.touches[0].clientY;
        }}
        return {{
          x: clientX - rect.left,
          y: clientY - rect.top
        }};
      }}

      function startDraw(e) {{
        e.preventDefault();
        drawing = true;
        hasStrokes = true;
        const p = getPos(e);
        ctx.beginPath();
        ctx.moveTo(p.x, p.y);
      }}

      function draw(e) {{
        if (!drawing) return;
        e.preventDefault();
        const p = getPos(e);
        ctx.lineTo(p.x, p.y);
        ctx.stroke();
      }}

      function endDraw(e) {{
        if (drawing) {{
          drawing = false;
          ctx.closePath();
        }}
      }}

      canvas.addEventListener('mousedown', startDraw);
      canvas.addEventListener('mousemove', draw);
      canvas.addEventListener('mouseup', endDraw);
      canvas.addEventListener('mouseleave', endDraw);

      canvas.addEventListener('touchstart', startDraw, {{passive: false}});
      canvas.addEventListener('touchmove', draw, {{passive: false}});
      canvas.addEventListener('touchend', endDraw, {{passive: false}});

      document.getElementById('btnClear').addEventListener('click', function() {{
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        hasStrokes = false;
      }});

      document.getElementById('btnSave').addEventListener('click', function() {{
        if (!hasStrokes) {{
          alert('⚠️ Por favor realice su firma antes de confirmar.');
          return;
        }}
        const dataUrl = canvas.toDataURL('image/png');
        try {{
          const urlParams = new URLSearchParams(window.parent.location.search);
          urlParams.set('firma_captured', dataUrl);
          urlParams.set('firma_key', '{key}');
          window.parent.location.search = urlParams.toString();
        }} catch(err) {{
          console.error(err);
        }}
      }});
    </script>
    </body>
    </html>
    """

    components.html(html_template, height=height)

    col_s1, col_s2 = st.columns([3, 1])
    if current_firma:
        with col_s1:
            st.success("✅ Firma registrada correctamente.")
        with col_s2:
            if st.button("🔄 Borrar Firma", key=f"btn_reset_sig_{key}", use_container_width=True):
                st.session_state[f"firma_val_{key}"] = None
                st.rerun()

    return current_firma


def renderizar_comprobante_firma(firma_b64, supervisor_nombre="Supervisor", fecha_str=None, monto_str=None, moneda_str=None):
    """
    Renders a visual card with the embedded Base64 digital signature.
    """
    if not fecha_str:
        fecha_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    monto_html = f"<div style='font-size: 15px; font-weight: 800; color: #22c55e; margin-bottom: 6px;'>💵 Monto: {moneda_str or ''} {monto_str}</div>" if monto_str else ""

    st.markdown(
        f"""
        <div style="background: rgba(15, 23, 42, 0.7); border: 1px dashed rgba(56, 189, 248, 0.4); border-radius: 12px; padding: 12px 16px; margin-top: 8px;">
            <div style="font-size: 11px; font-weight: 700; color: #38bdf8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px;">
                🔏 VALIDACIÓN CON FIRMA DIGITAL
            </div>
            {monto_html}
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap;">
                <div style="flex: 1; min-width: 140px;">
                    <div style="font-size: 12px; color: #94a3b8;">Validado por: <b style="color: #ffffff;">{supervisor_nombre}</b></div>
                    <div style="font-size: 11px; color: #64748b;">📅 Fecha/Hora: <b>{fecha_str}</b></div>
                </div>
                <div style="background: #0b1325; border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; padding: 4px 8px; text-align: center;">
                    <img src="{firma_b64}" style="max-height: 55px; max-width: 180px; display: block; margin: 0 auto;" alt="Firma Digital"/>
                    <div style="font-size: 9px; color: #22c55e; font-weight: 700; margin-top: 2px;">✔ FIRMADO DIGITALMENTE</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
