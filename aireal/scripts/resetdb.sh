cd ~/Data/aireal_instance
sudo -u postgres psql -c "drop database prod;"
sudo -u postgres psql -c "create database prod;"
sudo -u postgres psql -c "grant all privileges on database prod to "`id -u --name`";"
rm -f ~/Software/aireal/aireal/alembic/versions/*py
aireal_alembic revision --autogenerate -m "Base system."
aireal_alembic upgrade head
