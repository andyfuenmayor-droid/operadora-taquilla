import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime

def renderizar_formulario_pago_cajero_unificado(ag_nombre, u_id, cajero_id, fecha_filtro_str, height=360):
    """
    Renders a unified, single-step HTML5 form containing Fecha, Moneda, Monto, 
    Touch/Mouse Signature Canvas, and 'GUARDAR PAGO Y FIRMAR' button.
    Submits payment and signature in ONE single click.
    """
    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no"/>
    <style>
      * {{ box-sizing: border-box; margin: 0; padding: 0; }}
      body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        background: transparent;
        color: #f8fafc;
      }}
      .form-card {{
        background: rgba(13, 27, 34, 0.85);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 16px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.5);
      }}
      .form-header {{
        font-size: 14px;
        font-weight: 800;
        color: #ffffff;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        gap: 6px;
      }}
      .grid-inputs {{
        display: grid;
        grid-template-columns: 2fr 1.5fr 3fr 2fr;
        gap: 10px;
        margin-bottom: 12px;
      }}
      @media (max-width: 650px) {{
        .grid-inputs {{
          grid-template-columns: 1fr 1fr;
        }}
      }}
      .field {{
        display: flex;
        flex-direction: column;
        gap: 4px;
      }}
      label {{
        font-size: 10px;
        font-weight: 700;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
      }}
      input, select {{
        background: #071217;
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 8px;
        padding: 8px 10px;
        color: #ffffff;
        font-size: 13px;
        font-weight: 600;
        outline: none;
        width: 100%;
      }}
      input:focus, select:focus {{
        border-color: #00c853;
      }}
      .canvas-header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 12px;
        font-weight: 700;
        color: #38bdf8;
        margin: 8px 0 6px 0;
      }}
      .badge {{
        font-size: 9px;
        background: rgba(56, 189, 248, 0.15);
        color: #38bdf8;
        padding: 2px 6px;
        border-radius: 4px;
        font-weight: 700;
      }}
      canvas {{
        background: #071217;
        border: 1.5px dashed rgba(56, 189, 248, 0.35);
        border-radius: 8px;
        touch-action: none;
        cursor: crosshair;
        width: 100%;
        height: 120px;
        display: block;
      }}
      .hint {{
        font-size: 10.5px;
        color: #94a3b8;
        margin-top: 4px;
        text-align: center;
      }}
      .actions {{
        display: flex;
        gap: 10px;
        margin-top: 12px;
      }}
      button {{
        padding: 11px;
        border-radius: 8px;
        border: none;
        font-weight: 800;
        font-size: 13px;
        cursor: pointer;
        transition: all 0.2s ease;
      }}
      .btn-clear {{
        width: 120px;
        background: rgba(244, 63, 94, 0.15);
        color: #f43f5e;
        border: 1px solid rgba(244, 63, 94, 0.3);
      }}
      .btn-clear:hover {{
        background: rgba(244, 63, 94, 0.3);
      }}
      .btn-submit {{
        flex: 1;
        background: #00c853;
        color: #071217;
      }}
      .btn-submit:hover {{
        background: #69f0ae;
        box-shadow: 0 4px 12px rgba(0, 200, 83, 0.3);
      }}
    </style>
    </head>
    <body>
    <div class="form-card">
      <div class="form-header">📝 Registrar Nuevo Pago (Entrega de Efectivo)</div>
      
      <div class="grid-inputs">
        <div class="field">
          <label>FECHA</label>
          <input type="date" id="inputFecha" value="{fecha_filtro_str}"/>
        </div>
        <div class="field">
          <label>MONEDA</label>
          <select id="selectMoneda">
            <option value="COP" selected>COP</option>
            <option value="USD">USD</option>
            <option value="BS">BS</option>
          </select>
        </div>
        <div class="field">
          <label>MONTO</label>
          <input type="number" id="inputMonto" step="0.01" min="0.01" placeholder="0.00"/>
        </div>
        <div class="field">
          <label>TIPO PAGO</label>
          <input type="text" value="Efectivo" readonly style="opacity: 0.7; cursor: not-allowed;"/>
        </div>
      </div>

      <div class="canvas-header">
        <span>✍️ Firma Digital del Cajero (Entrega de Efectivo)</span>
        <span class="badge">📱 TÁCTIL / MOUSE</span>
      </div>
      <canvas id="sigCanvas"></canvas>
      <div class="hint">✏️ Dibuje su firma dentro del recuadro usando su dedo, stylus o ratón</div>

      <div class="actions">
        <button type="button" class="btn-clear" id="btnClear">🧹 Limpiar</button>
        <button type="button" class="btn-submit" id="btnSubmit">💾 GUARDAR PAGO Y FIRMAR</button>
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
        canvas.height = 120;
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

      document.getElementById('btnSubmit').addEventListener('click', function() {{
        const montoVal = parseFloat(document.getElementById('inputMonto').value) || 0;
        const monedaVal = document.getElementById('selectMoneda').value;
        const fechaVal = document.getElementById('inputFecha').value;

        if (montoVal <= 0) {{
          alert('⚠️ Por favor ingrese un monto válido mayor a cero.');
          return;
        }}

        if (!hasStrokes) {{
          alert('⚠️ Por favor realice su firma digital en el recuadro antes de guardar el pago.');
          return;
        }}

        const firmaData = canvas.toDataURL('image/png');

        try {{
          const urlParams = new URLSearchParams(window.parent.location.search);
          urlParams.set('pago_submit_monto', montoVal);
          urlParams.set('pago_submit_moneda', monedaVal);
          urlParams.set('pago_submit_fecha', fechaVal);
          urlParams.set('pago_submit_firma', firmaData);
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


def renderizar_popover_supervisor_unificado(pago_id, ag_nombre, cajero_nombre, monto_str, moneda_str, height=270):
    """
    Renders a single-step HTML5 confirmation box for Supervisor with signature canvas 
    and single 'Confirmar y Registrar Recepcion' submit button.
    """
    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no"/>
    <style>
      * {{ box-sizing: border-box; margin: 0; padding: 0; }}
      body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        background: transparent;
        color: #f8fafc;
      }}
      .sup-card {{
        background: #0f172a;
        border: 1px solid rgba(56, 189, 248, 0.3);
        border-radius: 12px;
        padding: 12px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.5);
      }}
      .info-header {{
        font-size: 13px;
        font-weight: 800;
        color: #22c55e;
        margin-bottom: 2px;
      }}
      .subtext {{
        font-size: 11px;
        color: #94a3b8;
        margin-bottom: 8px;
      }}
      .field {{
        margin-bottom: 8px;
      }}
      label {{
        font-size: 10px;
        font-weight: 700;
        color: #94a3b8;
        text-transform: uppercase;
      }}
      input {{
        background: #071217;
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 6px;
        padding: 6px 8px;
        color: #ffffff;
        font-size: 12px;
        width: 100%;
      }}
      canvas {{
        background: #071217;
        border: 1.5px dashed rgba(34, 197, 94, 0.35);
        border-radius: 6px;
        touch-action: none;
        cursor: crosshair;
        width: 100%;
        height: 110px;
        display: block;
        margin-top: 4px;
      }}
      .actions {{
        display: flex;
        gap: 8px;
        margin-top: 8px;
      }}
      button {{
        padding: 8px 10px;
        border-radius: 6px;
        border: none;
        font-weight: 800;
        font-size: 12px;
        cursor: pointer;
      }}
      .btn-clear {{
        background: rgba(244, 63, 94, 0.15);
        color: #f43f5e;
        border: 1px solid rgba(244, 63, 94, 0.3);
      }}
      .btn-submit {{
        flex: 1;
        background: #00c853;
        color: #071217;
      }}
    </style>
    </head>
    <body>
    <div class="sup-card">
      <div class="info-header">🔏 Recepción de Efectivo: {moneda_str} {monto_str}</div>
      <div class="subtext">Cajero: <b>{cajero_nombre}</b> | Agencia: <b>{ag_nombre}</b></div>
      
      <div class="field">
        <label>Nota / Comentario del Supervisor:</label>
        <input type="text" id="supComentario" value="Recibido de cajero {cajero_nombre}"/>
      </div>

      <div style="font-size: 11px; font-weight: 700; color: #22c55e; margin-top: 4px;">✍️ Firma Digital del Supervisor</div>
      <canvas id="sigCanvas"></canvas>

      <div class="actions">
        <button type="button" class="btn-clear" id="btnClear">🧹 Limpiar</button>
        <button type="button" class="btn-submit" id="btnSubmit">✅ Confirmar y Registrar Recepción</button>
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
        canvas.height = 110;
        ctx.strokeStyle = '#22c55e';
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

      document.getElementById('btnSubmit').addEventListener('click', function() {{
        if (!hasStrokes) {{
          alert('⚠️ Por favor realice su firma digital antes de confirmar.');
          return;
        }}
        const comVal = document.getElementById('supComentario').value;
        const firmaData = canvas.toDataURL('image/png');

        try {{
          const urlParams = new URLSearchParams(window.parent.location.search);
          urlParams.set('sup_confirm_id', '{pago_id}');
          urlParams.set('sup_confirm_comentario', comVal);
          urlParams.set('sup_confirm_firma', firmaData);
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


def renderizar_canvas_firma(key="firma_sup", titulo="✍️ Firma Digital de Validación", height=270):
    """Fallback canvas renderer"""
    return None


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
