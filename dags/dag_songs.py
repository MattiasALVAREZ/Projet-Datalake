from airflow import DAG  # type: ignore
from airflow.operators.python import PythonOperator  # type: ignore
from datetime import datetime, timedelta
import subprocess

# Chemin des scripts dans le conteneur
SCRIPT_PATH = "/opt/airflow/scripts"

def run_upload_songs_to_s3(**kwargs):
    """Appelle le script upload_songs_to_s3.py avec toutes les chansons en un seul appel."""
    songs = kwargs.get('dag_run').conf.get('songs', [])

    if not songs:
        raise ValueError("Aucune chanson fournie pour l'ingestion")

    song_args = [item for song in songs for item in [song["title"], song["artist"]]]
    subprocess.run(["python", f"{SCRIPT_PATH}/upload_songs_to_s3.py"] + song_args, check=True)

def run_songs_raw_to_staging(**kwargs):
    """Appelle le script songs_raw_to_staging.py avec les chansons spécifiées."""
    songs = kwargs.get('dag_run').conf.get('songs', [])

    if not songs:
        raise ValueError("Aucune chanson fournie pour l'étape de staging")

    song_args = [item for song in songs for item in [song["title"], song["artist"]]]
    subprocess.run(["python", f"{SCRIPT_PATH}/songs_raw_to_staging.py"] + song_args, check=True)

def run_songs_staging_to_curated(**kwargs):
    """Appelle le script songs_staging_to_curated.py avec les chansons spécifiées."""
    songs = kwargs.get('dag_run').conf.get('songs', [])

    if not songs:
        raise ValueError("Aucune chanson fournie pour la migration vers MongoDB")

    song_args = [item for song in songs for item in [song["title"], song["artist"]]]
    subprocess.run(["python", f"{SCRIPT_PATH}/songs_staging_to_curated.py"] + song_args, check=True)

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
    'dag_songs',
    default_args=default_args,
    description="DAG pour orchestrer les scripts S3, MySQL et MongoDB pour l'insertion des chansons",
    schedule_interval=None,
    catchup=False,
)

# Définition des tâches
task_song_s3 = PythonOperator(
    task_id='upload_songs_to_s3',
    python_callable=run_upload_songs_to_s3,
    provide_context=True,
    dag=dag,
)

task_song_mysql = PythonOperator(
    task_id='songs_raw_to_staging',
    python_callable=run_songs_raw_to_staging,
    provide_context=True,
    dag=dag,
)

task_song_mongo = PythonOperator(
    task_id='songs_staging_to_curated',
    python_callable=run_songs_staging_to_curated,
    provide_context=True,
    dag=dag,
)

# Ordre d'exécution des tâches
task_song_s3 >> task_song_mysql >> task_song_mongo
