#!/usr/bin/env bash

APP=""
DOMAIN = ""

sudo apt-get -y update
sudo apt-get -y dist-upgrade
sudo apt-get -y install unzip
sudo apt-get -y install python3-pip
sudo pip3 install setuptools


curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
rm awscliv2.zip
sudo rm -rf aws


# NGINX
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

        return 301 http://www.$DOMAIN/\$request_uri;
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

        return 301 https://www.$DOMAIN/\$request_uri;
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
sudo apt-get -y install python3-certbot python3-certbot-nginx python3-certbot-dns-route53
sudo certbot certonly --dns-route53 -d $DOMAIN -d www.$DOMAIN -d lab.$DOMAIN -i nginx
(crontab -l 2>/dev/null; echo "0 12 * * * /usr/bin/certbot renew -i nginx --quiet") | crontab -

sudo systemctl restart nginx


# POSTGRESQL
sudo apt-get -y install wget ca-certificates gnupg
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
sudo apt-get update
sudo apt-get -y install postgresql-13 postgresql-client-13 postgresql-server-dev-13
sudo pip3 install psycopg2

sudo systemctl stop postgresql@13-main

VARLIB='/var/lib/postgresql/13/main'
ETC='/etc/postgresql/13/main'
sudo -u postgres mv $VARLIB /var/lib/postgresql/13/_main

sudo -u postgres /usr/lib/postgresql/13/bin/initdb -D $VARLIB --wal-segsize=1
sudo -u postgres sed -i "s|max_wal_size = 1GB|max_wal_size = 64MB|" $ETC/postgresql.conf
sudo -u postgres sed -i "s|min_wal_size = 80MB|min_wal_size = 5MB|" $ETC/postgresql.conf

sudo systemctl enable postgresql@13-main
sudo systemctl start postgresql@13-main

sudo -u postgres psql -c 'create database prod;'
sudo -u postgres psql -c "create user flask;"
sudo -u postgres psql -c 'grant all privileges on database prod to flask;'



mkdir -p /var/log/journal
sudo systemd-tmpfiles --create --prefix /var/log/journal

sudo useradd flask -m --shell /usr/bin/false
sudo usermod flask -L
sudo -u flask mkdir "/home/flask/$APP"_prod

ssh-keygen -t rsa -b 4096
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_rsa
cat ~/.ssh/id_rsa.pub

git clone https://github.com/eawilson/aireal.git
cd aireal
sudo python3 setup.py develop
cd ..


cat >$APP.service <<EOF 
[Unit]
Description=aireal
After=network.target

[Service]
User=flask
WorkingDirectory=/home/flask/aireal_prod
ExecStart=/usr/local/bin/waitress_serve --port 8080 'aireal:create_app(\"/home/flask/aireal_prod\")'
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo mv $APP.service /etc/systemd/system/$APP.service

sudo systemctl daemon-reload
sudo systemctl start $APP
