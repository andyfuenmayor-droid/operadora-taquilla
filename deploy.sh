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

echo "⚙️ Configurando Nginx para cda.multibancaexpress.com..."
SITE_NAME="cda"
DOMAIN="cda.multibancaexpress.com"
CERT_DIR="/etc/letsencrypt/live/$DOMAIN"

SSL_OPTS=""
[ -f /etc/letsencrypt/options-ssl-nginx.conf ] && SSL_OPTS="    include /etc/letsencrypt/options-ssl-nginx.conf;"
SSL_DH=""
[ -f /etc/letsencrypt/ssl-dhparams.pem ] && SSL_DH="    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;"

if [ -f "$CERT_DIR/fullchain.pem" ] && [ -f "$CERT_DIR/privkey.pem" ]; then
    echo "🔒 Certificados SSL detectados en $CERT_DIR. Configurando HTTPS directo..."
    cat << EOF > /etc/nginx/sites-available/$SITE_NAME
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name $DOMAIN;

    ssl_certificate $CERT_DIR/fullchain.pem;
    ssl_certificate_key $CERT_DIR/privkey.pem;
$SSL_OPTS
$SSL_DH

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

        add_header Cache-Control "no-cache, no-store, must-revalidate, max-age=0" always;
        add_header Pragma "no-cache" always;
        add_header Expires "0" always;
    }
}
EOF
else
    echo "⚠️ Certificado aún no existe. Configurando HTTP temporal para validación Certbot..."
    cat << EOF > /etc/nginx/sites-available/$SITE_NAME
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;

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
        add_header Cache-Control "no-cache, no-store, must-revalidate, max-age=0" always;
        add_header Pragma "no-cache" always;
        add_header Expires "0" always;
    }
}
EOF
    ln -sf /etc/nginx/sites-available/$SITE_NAME /etc/nginx/sites-enabled/$SITE_NAME
    nginx -t
    systemctl reload nginx

    echo "🔒 Solicitando Certificado SSL Let's Encrypt para $DOMAIN..."
    certbot --nginx -d $DOMAIN --non-interactive --agree-tos --register-unsafely-without-email --keep-until-expiring || true

    if [ -f "$CERT_DIR/fullchain.pem" ]; then
        cat << EOF > /etc/nginx/sites-available/$SITE_NAME
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name $DOMAIN;

    ssl_certificate $CERT_DIR/fullchain.pem;
    ssl_certificate_key $CERT_DIR/privkey.pem;
$SSL_OPTS
$SSL_DH

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

        add_header Cache-Control "no-cache, no-store, must-revalidate, max-age=0" always;
        add_header Pragma "no-cache" always;
        add_header Expires "0" always;
    }
}
EOF
    fi
fi

ln -sf /etc/nginx/sites-available/$SITE_NAME /etc/nginx/sites-enabled/$SITE_NAME
nginx -t
systemctl reload nginx

echo "✅ Despliegue completado con éxito."
