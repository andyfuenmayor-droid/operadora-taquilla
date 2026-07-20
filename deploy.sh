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
apt install -y nginx certbot python3-certbot-nginx git psmisc || true

# Verificar si Docker ya está instalado
if ! command -v docker &> /dev/null; then
    echo "📦 Instalando Docker..."
    apt install -y docker.io || apt install -y docker-ce docker-ce-cli containerd.io || true
fi

systemctl enable --now docker || true
systemctl enable --now nginx || true

echo "📦 Construyendo la imagen de Docker..."
docker build -t taquilla-app .

echo "🛑 Liberando el puerto 8501 y deteniendo contenedores previos..."
fuser -k 8501/tcp || true
docker stop taquilla-container 2>/dev/null || true
docker rm taquilla-container 2>/dev/null || true

# Detener cualquier otro contenedor que esté ocupando el puerto 8501
for cid in $(docker ps -q 2>/dev/null); do
    if docker port "$cid" 2>/dev/null | grep -q "8501"; then
        echo "Deteniendo contenedor $cid en puerto 8501..."
        docker stop "$cid" || true
        docker rm "$cid" || true
    fi
done

echo "▶️ Iniciando nuevo contenedor..."
docker run -d \
  --name taquilla-container \
  -p 127.0.0.1:8501:8501 \
  -e SUPABASE_URL="$SUPABASE_URL" \
  -e SUPABASE_KEY="$SUPABASE_KEY" \
  --restart always \
  taquilla-app

echo "⚙️ Limpiando configuraciones Nginx duplicadas para cda..."
rm -f /etc/nginx/sites-enabled/default
rm -f /etc/nginx/sites-enabled/default.conf
rm -f /etc/nginx/sites-enabled/cda*
rm -f /etc/nginx/sites-available/cda*

echo "⚙️ Configurando Nginx para cda.multibancaexpress.com..."
cat << 'EOF' > /etc/nginx/sites-available/cda
server {
    listen 80;
    listen [::]:80;
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

ln -sf /etc/nginx/sites-available/cda /etc/nginx/sites-enabled/cda
nginx -t
systemctl reload nginx

echo "🔒 Aplicando Certificado SSL con Certbot..."
certbot --nginx -d cda.multibancaexpress.com --non-interactive --agree-tos --register-unsafely-without-email --redirect || echo "⚠️ Certbot finalizado."

nginx -t
systemctl reload nginx

echo "✅ Despliegue completado con éxito. Accede a https://cda.multibancaexpress.com"
