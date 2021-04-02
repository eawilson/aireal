#!/usr/bin/env bash

sudo apt-get -y install curl ca-certificates gnupg
sudo curl https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
sudo add-apt-repository 'deb http://apt.postgresql.org/pub/repos/apt/ bionic-pgdg main'
sudo apt-get -y update
sudo apt-get -y install postgresql-12 postgresql-client-12 postgresql-server-dev-12
sudo pip3 install psycopg2

sudo systemctl stop postgresql@12-main

VARLIB='/var/lib/postgresql/12/main'
ETC='/etc/postgresql/12/main'
sudo -u postgres mv $VARLIB /var/lib/postgresql/12/_main

sudo -u postgres /usr/lib/postgresql/12/bin/initdb -D $VARLIB --wal-segsize=1
sudo -u postgres sed -i "s|max_wal_size = 1GB|max_wal_size = 64MB|" $ETC/postgresql.conf
sudo -u postgres sed -i "s|min_wal_size = 80MB|min_wal_size = 5MB|" $ETC/postgresql.conf

sudo systemctl enable postgresql@12-main
sudo systemctl start postgresql@12-main

sudo -u postgres psql -c 'create database prod;'
sudo -u postgres psql -c "create user flask;"
sudo -u postgres psql -c 'grant all privileges on database prod to flask;'


