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
    'dag_songs_fast',
    default_args=default_args,
    description="DAG optimisé pour l'ingestion rapide des chansons spécifiées avec Airflow",
    schedule_interval=None,
    catchup=False,
)

def run_upload_songs_to_s3_fast(**kwargs):
    """Appelle le script optimisé upload_songs_to_s3_fast.py avec les chansons spécifiées."""
    songs = kwargs.get('dag_run').conf.get('songs', [])
    
    if not songs:
        raise ValueError("Aucune chanson fournie pour l'ingestion rapide")

    # Préparer les arguments pour le script : titre et artiste en paires
    song_args = [item for song in songs for item in [song["title"], song["artist"]]]
    
    print(f"Lancement de l'upload vers S3 pour les chansons : {songs}")
    subprocess.run(["python", "/opt/airflow/scripts/upload_songs_to_s3_fast.py"] + song_args, check=True)

def run_songs_raw_to_staging_fast(**kwargs):
    """Appelle le script optimisé songs_raw_to_staging_fast.py avec les chansons spécifiées."""
    songs = kwargs.get('dag_run').conf.get('songs', [])
    
    if not songs:
        raise ValueError("Aucune chanson fournie pour le transfert vers MySQL")

    # Préparer les arguments pour le script : titre et artiste en paires
    song_args = [item for song in songs for item in [song["title"], song["artist"]]]
    
    print(f"Lancement du transfert vers MySQL pour les chansons : {songs}")
    subprocess.run(["python", "/opt/airflow/scripts/songs_raw_to_staging_fast.py"] + song_args, check=True)

def run_songs_staging_to_curated_fast(**kwargs):
    """Appelle le script optimisé songs_staging_to_curated_fast.py avec les chansons spécifiées."""
    songs = kwargs.get('dag_run').conf.get('songs', [])
    
    if not songs:
        raise ValueError("Aucune chanson fournie pour la migration vers MongoDB")

    # Préparer les arguments pour le script : titre et artiste en paires
    song_args = [item for song in songs for item in [song["title"], song["artist"]]]
    
    print(f"Lancement de la migration vers MongoDB pour les chansons : {songs}")
    subprocess.run(["python", "/opt/airflow/scripts/songs_staging_to_curated_fast.py"] + song_args, check=True)

# Définition des tâches optimisées
task_upload_s3 = PythonOperator(
    task_id='upload_songs_to_s3_fast',
    python_callable=run_upload_songs_to_s3_fast,
    provide_context=True,
    dag=dag,
)

task_to_mysql = PythonOperator(
    task_id='songs_raw_to_staging_fast',
    python_callable=run_songs_raw_to_staging_fast,
    provide_context=True,
    dag=dag,
)

task_to_mongo = PythonOperator(
    task_id='songs_staging_to_curated_fast',
    python_callable=run_songs_staging_to_curated_fast,
    provide_context=True,
    dag=dag,
)

# Ordre d'exécution des tâches optimisées
task_upload_s3 >> task_to_mysql >> task_to_mongo
