#!/bin/bash

# Script de despliegue automatizado para DigitalOcean Droplet
# Uso: bash deploy.sh <SUPABASE_URL> <SUPABASE_KEY>

set -e

SUPABASE_URL=$1
SUPABASE_KEY=$2
PORT=8510

if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_KEY" ]; then
    echo "❌ Error: Debes proporcionar SUPABASE_URL y SUPABASE_KEY."
    echo "Uso: bash deploy.sh \"https://tu-proyecto.supabase.co\" \"tu-key\""
    exit 1
fi

echo "🚀 Actualizando paquetes e instalando dependencias..."
apt update || true
apt install -y nginx certbot python3-certbot-nginx git psmisc || true

systemctl enable --now docker || true
systemctl enable --now nginx || true

echo "📦 Construyendo la imagen de Docker para cda..."
docker build -t taquilla-app .

echo "🛑 Liberando solo el puerto $PORT..."
fuser -k $PORT/tcp || true
docker stop taquilla-container 2>/dev/null || true
docker rm taquilla-container 2>/dev/null || true

echo "▶️ Iniciando contenedor en puerto dedicado $PORT..."
docker run -d \
  --name taquilla-container \
  -p 127.0.0.1:$PORT:8501 \
  -e SUPABASE_URL="$SUPABASE_URL" \
  -e SUPABASE_KEY="$SUPABASE_KEY" \
  --restart always \
  taquilla-app

echo "⚙️ Configurando Nginx ÚNICAMENTE para cda.multibancaexpress.com..."
rm -f /etc/nginx/sites-enabled/cda
rm -f /etc/nginx/sites-available/cda

cat << EOF > /etc/nginx/sites-available/cda
server {
    listen 80;
    listen [::]:80;
    server_name cda.multibancaexpress.com;

    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 86400;

        # Evitar almacenamiento en caché del navegador y forzar siempre la versión actual
        add_header Cache-Control "no-cache, no-store, must-revalidate, max-age=0" always;
        add_header Pragma "no-cache" always;
        add_header Expires "0" always;
    }
}
EOF

ln -sf /etc/nginx/sites-available/cda /etc/nginx/sites-enabled/cda
nginx -t
systemctl reload nginx

echo "🔒 Aplicando Certificado SSL para cda.multibancaexpress.com..."
certbot --nginx -d cda.multibancaexpress.com --non-interactive --agree-tos --register-unsafely-without-email || echo "⚠️ Certbot finalizado."

nginx -t
systemctl reload nginx

echo "✅ Despliegue completado con éxito."
