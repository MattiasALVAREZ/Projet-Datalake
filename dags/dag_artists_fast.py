from airflow import DAG  # type: ignore
from airflow.operators.python import PythonOperator  # type: ignore
from datetime import datetime, timedelta
import subprocess

# Configuration des arguments par défaut pour le DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2025, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# Définition du DAG optimisé
dag = DAG(
    'dag_artists_fast',
    default_args=default_args,
    description="DAG optimisé pour l'ingestion rapide des artistes avec Airflow",
    schedule_interval=None,
    catchup=False,
)

def run_upload_artists_to_s3_fast(**kwargs):
    """Appelle le script optimisé upload_artists_to_s3_fast.py avec les artistes spécifiés."""
    artists = kwargs.get('dag_run').conf.get('artists', [])
    if not artists:
        raise ValueError("Aucun artiste fourni pour l'ingestion rapide")
    subprocess.run(["python", "/opt/airflow/scripts/upload_artists_to_s3_fast.py"] + artists, check=True)

def run_artists_raw_to_staging_fast(**kwargs):
    """Appelle le script optimisé artists_raw_to_staging_fast.py avec les artistes spécifiés."""
    artists = kwargs.get('dag_run').conf.get('artists', [])
    if not artists:
        raise ValueError("Aucun artiste fourni pour l'étape de staging rapide")
    subprocess.run(["python", "/opt/airflow/scripts/artists_raw_to_staging_fast.py"] + artists, check=True)

def run_artists_staging_to_curated_fast(**kwargs):
    """Appelle le script optimisé artists_staging_to_curated_fast.py avec les artistes spécifiés."""
    artists = kwargs.get('dag_run').conf.get('artists', [])
    if not artists:
        raise ValueError("Aucun artiste fourni pour la migration rapide vers MongoDB")
    subprocess.run(["python", "/opt/airflow/scripts/artists_staging_to_curated_fast.py"] + artists, check=True)

# Définition des tâches optimisées
task1 = PythonOperator(
    task_id='upload_artists_to_s3_fast',
    python_callable=run_upload_artists_to_s3_fast,
    provide_context=True,
    dag=dag,
)

task2 = PythonOperator(
    task_id='artists_raw_to_staging_fast',
    python_callable=run_artists_raw_to_staging_fast,
    provide_context=True,
    dag=dag,
)

task3 = PythonOperator(
    task_id='artists_staging_to_curated_fast',
    python_callable=run_artists_staging_to_curated_fast,
    provide_context=True,
    dag=dag,
)

# Ordre d'exécution des tâches optimisées
task1 >> task2 >> task3
