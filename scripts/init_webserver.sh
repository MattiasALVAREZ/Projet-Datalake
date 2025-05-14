#!/bin/bash

echo "Attente que la base de données Airflow soit prête..."

# Attendre que la DB soit accessible
until airflow db check; do
    echo "Base non prête. Nouvelle vérification dans 5s..."
    sleep 5
done

# Modifier le fichier airflow.cfg uniquement pour le webserver
echo "Modification de airflow.cfg pour optimiser les performances..."

sed -i 's/auth_backends = airflow.api.auth.backend.session/auth_backends = airflow.api.auth.backend.basic_auth/' /opt/airflow/airflow.cfg

# Optimisation des workers et des timeouts
sed -i 's/^workers = .*/workers = 2/' /opt/airflow/airflow.cfg
sed -i 's/^web_server_worker_timeout = .*/web_server_worker_timeout = 300/' /opt/airflow/airflow.cfg
sed -i 's/^worker_refresh_interval = .*/worker_refresh_interval = 3600/' /opt/airflow/airflow.cfg
sed -i 's/^web_server_master_timeout = .*/web_server_master_timeout = 300/' /opt/airflow/airflow.cfg

echo "Lancement de l'Airflow Webserver..."
exec airflow webserver
