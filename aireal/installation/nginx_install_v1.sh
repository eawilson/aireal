#!/usr/bin/env bash

DOMAIN=""

sudo apt-get -y update
sudo apt-get -y dist-upgrade

sudo apt-get -y install python3-pip
sudo pip3 install setuptools

sudo apt-get -y install nginx

openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout cert.key -out cert.crt
sudo mv cert.key /etc/nginx/cert.key
sudo mv cert.crt /etc/nginx/cert.crt

openssl dhparam -out dhparam.pem 4096
sudo mv dhparam.pem /etc/nginx/dhparam.pem
cat >nginx.conf <<EOF 
events { }

http {
    server {
        listen 80;
        server_name $DOMAIN;

        return 301 https://www.$DOMAIN/\$request_uri;
        }

    server {
        listen 80;
        server_name www.$DOMAIN lab.$DOMAIN;

        return 301 https://\$host\$request_uri;
        }
        

    server {
        listen 443;
        server_name $DOMAIN;

        ssl                  on;
        ssl_certificate      /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
        ssl_certificate_key  /etc/letsencrypt/live/$DOMAIN/privkey.pem;

        return 301 https://lab.$DOMAIN/\$request_uri;
        }
        
    server {
        listen 443;
        server_name www.$DOMAIN;

        ssl                  on;
        ssl_certificate      /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
        ssl_certificate_key  /etc/letsencrypt/live/$DOMAIN/privkey.pem;

        return 301 https://lab.$DOMAIN/\$request_uri;
        }
        
    server {
        listen 443;
        server_name lab.$DOMAIN;

        ssl                  on;
        ssl_certificate      /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
        ssl_certificate_key  /etc/letsencrypt/live/$DOMAIN/privkey.pem;

        ssl_prefer_server_ciphers on;
        ssl_session_timeout 1d;
        ssl_session_cache shared:SSL:50m;
        ssl_session_tickets off;

        ssl_dhparam /etc/nginx/dhparam.pem;

        # https://wiki.mozilla.org/Security/Server_Side_TLS
        # Intermediate compatibility (recommended)
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers 'TLS_AES_128_GCM_SHA256:TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256:ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384';

        location / {
            proxy_pass http://localhost:8080;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto https;
            }
        }
    }
EOF

sudo mv nginx.conf /etc/nginx/nginx.conf


# CERTBOT
# Requires the following aws permissions.
#route53:ListHostedZones
#route53:GetChange
#route53:ChangeResourceRecordSets

sudo apt-get -y install software-properties-common
sudo add-apt-repository universe
sudo add-apt-repository ppa:certbot/certbot
sudo apt-get update
sudo apt-get -y install python3-certbot python3-certbot-nginx python3-certbot-dns-route53
sudo certbot certonly --dns-route53 -d $DOMAIN -d www.$DOMAIN -d lab.$DOMAIN -i nginx
(crontab -l 2>/dev/null; echo "0 12 * * * /usr/bin/certbot renew --quiet") | crontab -

sudo systemctl restart nginx


