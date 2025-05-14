FROM apache/airflow:2.7.1

USER root

# Installation des dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Création des dossiers nécessaires
RUN mkdir -p /opt/airflow/scripts /opt/airflow/logs /opt/airflow/plugins /opt/airflow/dags
COPY ./scripts /opt/airflow/scripts
COPY ./dags /opt/airflow/dags
COPY ./requirements.txt /requirements.txt

# Copier le script spécifique au webserver
COPY ./scripts/init_webserver.sh /opt/airflow/scripts/init_webserver.sh
COPY ./scripts/init_scheduler.sh /opt/airflow/scripts/init_scheduler.sh
RUN chmod +x /opt/airflow/scripts/init_webserver.sh
RUN chmod +x /opt/airflow/scripts/init_scheduler.sh

# Assurer les bons droits pour l'utilisateur airflow
RUN chown -R airflow: /opt/airflow

# Installation des dépendances Python
USER airflow
RUN pip install --no-cache-dir -r /requirements.txt
