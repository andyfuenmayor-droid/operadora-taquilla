#!/bin/bash

# Script de despliegue automatizado para DigitalOcean Droplet
# Uso: bash deploy.sh <SUPABASE_URL> <SUPABASE_KEY>

set -e

SUPABASE_URL=$1
SUPABASE_KEY=$2

if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_KEY" ]; then
    echo "❌ Error: Debes proporcionar SUPABASE_URL y SUPABASE_KEY."
    echo "Uso: bash deploy.sh \"https://tu-proyecto.supabase.co\" \"tu-key\""
    exit 1
fi

echo "🚀 Actualizando paquetes e instalando dependencias..."
apt update || true
apt install -y nginx certbot python3-certbot-nginx git || true

# Verificar si Docker ya está instalado
if ! command -v docker &> /dev/null; then
    echo "📦 Instalando Docker..."
    apt install -y docker.io || apt install -y docker-ce docker-ce-cli containerd.io || true
fi

systemctl enable --now docker || true
systemctl enable --now nginx || true

echo "📦 Construyendo la imagen de Docker..."
docker build -t taquilla-app .

echo "🛑 Deteniendo contenedor anterior si existe..."
docker stop taquilla-container || true
docker rm taquilla-container || true

echo "▶️ Iniciando nuevo contenedor..."
docker run -d \
  --name taquilla-container \
  -p 8501:8501 \
  -e SUPABASE_URL="$SUPABASE_URL" \
  -e SUPABASE_KEY="$SUPABASE_KEY" \
  --restart always \
  taquilla-app

echo "⚙️ Configurando Nginx para cda.multibancaexpress.com..."
cat << 'EOF' > /etc/nginx/sites-available/cda
server {
    listen 80;
    server_name cda.multibancaexpress.com;

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }
}
EOF

ln -sf /etc/nginx/sites-available/cda /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx

echo "🔒 Configurando certificado SSL (HTTPS)..."
certbot --nginx -d cda.multibancaexpress.com --non-interactive --agree-tos --register-unsafely-without-email || echo "⚠️ Certbot omitido o el dominio aún no apunta a esta IP."

echo "✅ Despliegue completado con éxito. Accede a https://cda.multibancaexpress.com"
