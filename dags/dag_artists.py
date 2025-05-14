from airflow import DAG # type: ignore
from airflow.operators.python import PythonOperator # type: ignore
from datetime import datetime, timedelta
import subprocess

# Chemin des scripts dans le conteneur
SCRIPT_PATH = "/opt/airflow/scripts"

def run_upload_artists_to_s3(**kwargs):
    """Appelle le script upload_artists_to_s3.py en passant les artistes depuis la config."""
    artists = kwargs.get('dag_run').conf.get('artists', [])
    if not artists:
        raise ValueError("Aucun artiste fourni pour l'ingestion")
    subprocess.run(["python", f"{SCRIPT_PATH}/upload_artists_to_s3.py"] + artists, check=True)

def run_artists_raw_to_staging(**kwargs):
    artists = kwargs.get('dag_run').conf.get('artists', [])
    subprocess.run(["python", f"{SCRIPT_PATH}/artists_raw_to_staging.py"] + artists, check=True)

def run_artists_staging_to_curated(**kwargs):
    artists = kwargs.get('dag_run').conf.get('artists', [])
    subprocess.run(["python", f"{SCRIPT_PATH}/artists_staging_to_curated.py"] + artists, check=True)

# Configuration du DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2025, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'dag_artists',
    default_args=default_args,
    description="DAG pour orchestrer les scripts S3, MySQL et MongoDB pour l'insertion des artistes",
    schedule_interval=None,
    catchup=False,
)

# Définition des tâches
task1 = PythonOperator(
    task_id='upload_artists_to_s3',
    python_callable=run_upload_artists_to_s3,
    provide_context=True,
    dag=dag,
)

task2 = PythonOperator(
    task_id='artists_raw_to_staging',
    python_callable=run_artists_raw_to_staging,
    dag=dag,
)

task3 = PythonOperator(
    task_id='artists_staging_to_curated',
    python_callable=run_artists_staging_to_curated,
    dag=dag,
)

# Ordre d'exécution des tâches
task1 >> task2 >> task3
