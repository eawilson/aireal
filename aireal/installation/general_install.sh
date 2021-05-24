#!/usr/bin/env bash

sudo apt-get -y update
sudo apt-get -y dist-upgrade
sudo apt-get install python3-pip

APP=""
EMAIL=""

mkdir -p /var/log/journal
sudo systemd-tmpfiles --create --prefix /var/log/journal


sudo pip3 install boto3
sudo pip3 install waitress
sudo pip3 install flask


sudo useradd flask --shell /usr/bin/false
sudo usermod flask -L

sudo mkdir /home/flask/$APP_prod
sudo chown flask /home/flask/$APP_prod
cat >$APP.conf <<EOF 
DB_URL = "postgresql://flask@localhost/$APP_prod"
EOF
sudo chown flask $APP.cfg
sudo mv $APP.conf /home/flask/$APP_prod


ssh-keygen -t rsa -b 4096 -C "$EMAIL"
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_rsa
cat ~/.ssh/id_rsa.pub

git clone git@github.com:eawilson/aireal.git
cd aireal
sudo python3 setup.py develop
cd ..


cat >$APP.service <<EOF 
[Unit]
Description=aireal
After=network.target

[Service]
User=flask
WorkingDirectory=/home/flask/$APP_prod
ExecStart=/usr/local/bin/waitress_serve --port 8080 '$APP:create_app(\"/home/flask/aireal_prod\")'
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo mv $APP.service /etc/systemd/system/$APP.service

sudo systemctl daemon-reload
sudo systemctl start $APP
