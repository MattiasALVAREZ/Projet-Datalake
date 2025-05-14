#!/bin/bash

echo "Attente que la base de données Airflow soit prête..."

# Attendre que la DB soit accessible
until airflow db check; do
    echo "Base non prête. Nouvelle vérification dans 5s..."
    sleep 5
done

echo "Base de données prête. Lancement du Scheduler..."

# Lancer le scheduler
exec airflow scheduler
