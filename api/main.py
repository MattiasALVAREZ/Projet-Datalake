from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pymysql
import pymongo
import boto3
from dotenv import load_dotenv
import os
from pydantic import BaseModel
import requests
from typing import List
from bson import ObjectId

load_dotenv(dotenv_path="/opt/api/.env")

MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))

MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongodb-dlk:27017/")
MONGO_DATABASE = os.getenv("MONGO_DATABASE", "datalakes_curated")

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")
BUCKET_NAME = os.getenv("BUCKET_NAME")

mysql_connection = pymysql.connect(
    host=MYSQL_HOST,
    user=MYSQL_USER,
    password=MYSQL_PASSWORD,
    database=MYSQL_DATABASE,
    port=MYSQL_PORT,
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
)
mongo_client = pymongo.MongoClient(MONGO_URI)
mongo_db = mongo_client[MONGO_DATABASE]
s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION,
)

AIRFLOW_API_URL = os.getenv("AIRFLOW_API_URL")
AIRFLOW_USER = os.getenv("AIRFLOW_USER")
AIRFLOW_PASSWORD = os.getenv("AIRFLOW_PASSWORD")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ArtistRequest(BaseModel):
    artists: List[str]

class Song(BaseModel):
    title: str
    artist: str

class SongRequest(BaseModel):
    songs: List[Song]

def convert_objectid(data):
    """Convertit les ObjectId en chaînes de caractères dans les documents MongoDB."""
    if isinstance(data, list):
        return [convert_objectid(item) for item in data]
    elif isinstance(data, dict):
        return {key: convert_objectid(value) for key, value in data.items()}
    elif isinstance(data, ObjectId):
        return str(data)
    else:
        return data

@app.get("/")
async def root():
    return {"message": "Bienvenue sur l'API Gateway du projet DLK"}

@app.get("/raw")
async def get_raw_data():
    response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix="raw/")
    files = [obj["Key"] for obj in response.get("Contents", [])]
    return {"raw_files": files}

@app.get("/raw/artist/{artist_name}")
async def get_artist_data(artist_name: str):
    """Récupère les données brutes de l'artiste depuis S3"""
    key = f"raw/{artist_name.replace(' ', '_').lower()}.json"
    try:
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=key)
        artist_data = response["Body"].read().decode("utf-8")
        return {"artist_data": artist_data}
    except Exception as e:
        return {"error": f"Artiste non trouvé ou erreur S3: {str(e)}"}

@app.get("/raw/song/{artist_name}/{song_title}")
async def get_song_data(artist_name: str, song_title: str):
    """Récupère les données brutes d'une chanson depuis S3"""
    key = f"raw/{artist_name.replace(' ', '_').lower()}_{song_title.replace(' ', '_').lower()}.json"
    try:
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=key)
        song_data = response["Body"].read().decode("utf-8")
        return {"song_data": song_data}
    except Exception as e:
        return {"error": f"Chanson non trouvée ou erreur S3: {str(e)}"}

@app.get("/staging")
async def get_staging_data():
    """Récupère les données depuis le MySQL"""
    with mysql_connection.cursor() as cursor:
        cursor.execute("SELECT * FROM artists")
        artists = cursor.fetchall()
        cursor.execute("SELECT * FROM songs")
        songs = cursor.fetchall()
    return {"artists": artists, "songs": songs}

@app.get("/staging/artists")
async def get_staging_artists():
    """Liste les artistes stockés en MySQL."""
    with mysql_connection.cursor() as cursor:
        cursor.execute("SELECT id, name, bio FROM artists")
        artists = cursor.fetchall()
    return {"artists": artists}

@app.get("/staging/songs")
async def get_staging_songs():
    """Liste les chansons stockées en MySQL."""
    with mysql_connection.cursor() as cursor:
        cursor.execute("SELECT id, artist_id, title, url, image_url, lyrics FROM songs")
        songs = cursor.fetchall()
    return {"songs": songs}

@app.get("/curated")
async def get_curated_data():
    songs = list(mongo_db.songs.find({}))
    artists = list(mongo_db.artists.find({}))

    return {
        "curated_data": {
            "songs": convert_objectid(songs),
            "artists": convert_objectid(artists)
        }
    }

@app.get("/curated/artists")
async def get_curated_artists():
    """Récupère les artistes stockés dans MongoDB."""
    artists = list(mongo_db.artists.find({}, {"_id": 0}))
    return {"artists": artists}

@app.get("/curated/songs")
async def get_curated_songs():
    """Récupère les chansons stockées dans MongoDB."""
    songs = list(mongo_db.songs.find({}, {"_id": 0}))
    return {"songs": convert_objectid(songs)}

@app.get("/health")
async def get_health_status():
    service_status = {
        "mysql": {"status": "unhealthy", "details": None},
        "mongodb": {"status": "unhealthy", "details": None},
        "s3": {"status": "unhealthy", "details": None},
    }

    try:
        with mysql_connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        service_status["mysql"]["status"] = "healthy"
    except Exception as e:
        service_status["mysql"]["details"] = str(e)

    try:
        mongo_db.command("ping")
        service_status["mongodb"]["status"] = "healthy"
    except Exception as e:
        service_status["mongodb"]["details"] = str(e)

    try:
        s3_client.head_bucket(Bucket=BUCKET_NAME)
        service_status["s3"]["status"] = "healthy"
    except Exception as e:
        service_status["s3"]["details"] = str(e)

    overall_status = "healthy" if all(service["status"] == "healthy" for service in service_status.values()) else "unhealthy"
    return {"status": overall_status, "services": service_status}

@app.get("/stats")
async def get_stats():
    response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix="raw/")
    s3_files = response.get("Contents", []) if "Contents" in response else []
    s3_file_count = len(s3_files)

    # Calcul de la taille totale des fichiers S3
    total_s3_size = sum(file["Size"] for file in s3_files)

    # Récupération des stats MySQL
    try:
        connection = pymysql.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE,
            port=MYSQL_PORT,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )

        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM artists")
            mysql_artists_count = cursor.fetchone()["count"]

            cursor.execute("SELECT COUNT(*) as count FROM songs")
            mysql_songs_count = cursor.fetchone()["count"]

        connection.close()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération des stats MySQL: {e}")

    # Récupération des stats MongoDB
    mongo_songs_count = mongo_db.songs.count_documents({})
    mongo_artists_count = mongo_db.artists.count_documents({})

    # Récupération des stats de stockage MongoDB
    stats = mongo_db.command("collstats", "songs")
    mongo_storage_size = stats.get("storageSize", 0)
    mongo_total_size = stats.get("totalSize", 0)

    return {
        "s3": {
            "file_count": s3_file_count,
            "total_size_bytes": total_s3_size,
        },
        "mysql": {
            "artists_count": mysql_artists_count,
            "songs_count": mysql_songs_count
        },
        "mongodb": {
            "artists_count": mongo_artists_count,
            "songs_count": mongo_songs_count,
            "storage_size_bytes": mongo_storage_size,
            "total_size_bytes": mongo_total_size,
        }
    }

@app.delete("/delete_all")
async def delete_all():
    """Supprime toutes les données des bases MySQL, MongoDB et S3."""
    try:
        await delete_mysql()
        await delete_mongo()
        await delete_s3()
        return {"message": "Toutes les données ont été supprimées avec succès de MySQL, MongoDB et S3."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la suppression des données: {str(e)}")

@app.delete("/delete_mysql")
async def delete_mysql():
    """Supprime toutes les données de MySQL."""
    try:
        with mysql_connection.cursor() as cursor:
            cursor.execute("DELETE FROM songs")
            cursor.execute("DELETE FROM artists")
            mysql_connection.commit()
        return {"message": "Toutes les données ont été supprimées de MySQL."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la suppression des données MySQL: {str(e)}")

@app.delete("/delete_mongo")
async def delete_mongo():
    """Supprime toutes les données de MongoDB."""
    try:
        mongo_db.songs.drop()
        mongo_db.artists.drop()
        mongo_db.command("compact", "songs")
        mongo_db.command("compact", "artists")
        return {"message": "Toutes les données ont été supprimées de MongoDB et les collections ont été droppées."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la suppression des données MongoDB: {str(e)}")

@app.delete("/delete_s3")
async def delete_s3():
    """Supprime tous les fichiers du bucket S3."""
    try:
        response = s3_client.list_objects_v2(Bucket=BUCKET_NAME)
        if "Contents" in response:
            objects_to_delete = [{"Key": obj["Key"]} for obj in response["Contents"]]
            s3_client.delete_objects(Bucket=BUCKET_NAME, Delete={"Objects": objects_to_delete})
        return {"message": "Tous les fichiers ont été supprimés du bucket S3."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la suppression des fichiers S3: {str(e)}")

@app.post("/ingest")
async def ingest_data(request: ArtistRequest):
    """Déclenche le pipeline d'ingestion basé sur les artistes."""
    if not request.artists:
        raise HTTPException(status_code=400, detail="Liste d'artistes vide")

    # Unpause le DAG avant de lancer
    airflow_api_url = f"{os.getenv('AIRFLOW_BASE_URL')}/dags/dag_artists"
    auth = (AIRFLOW_USER, AIRFLOW_PASSWORD)
    headers = {"Content-Type": "application/json"}

    response = requests.get(airflow_api_url, auth=auth, headers=headers)
    if response.status_code == 200:
        dag_info = response.json()
        if dag_info.get("is_paused"):
            unpause_response = requests.patch(airflow_api_url, auth=auth, headers=headers, json={"is_paused": False})
            if unpause_response.status_code == 200:
                print("DAG 'dag_artists' unpausé automatiquement.")
            else:
                raise HTTPException(status_code=500, detail="Impossible d'unpause le DAG.")
    else:
        raise HTTPException(status_code=500, detail="Impossible de vérifier l'état du DAG.")

    # Déclencher le DAG après unpause
    dag_run_url = f"{os.getenv('AIRFLOW_BASE_URL')}/dags/dag_artists/dagRuns"
    payload = {"conf": {"artists": request.artists}}
    response = requests.post(dag_run_url, auth=auth, headers=headers, json=payload)

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Erreur lors du déclenchement du DAG 'dag_artists': {response.text}")

    return {"message": f"Pipeline artistes déclenché avec succès pour {len(request.artists)} artistes."}

@app.post("/ingest_songs")
async def ingest_songs(request: SongRequest):
    """Déclenche le pipeline d'ingestion basé sur les chansons."""
    if not request.songs:
        raise HTTPException(status_code=400, detail="Liste de chansons vide")
    
    # Unpause le DAG avant de lancer
    airflow_api_url = f"{os.getenv('AIRFLOW_BASE_URL')}/dags/dag_songs"
    auth = (os.getenv("AIRFLOW_USER"), os.getenv("AIRFLOW_PASSWORD"))
    headers = {"Content-Type": "application/json"}
    
    response = requests.get(airflow_api_url, auth=auth, headers=headers)
    if response.status_code == 200:
        dag_info = response.json()
        if dag_info.get("is_paused"):
            unpause_response = requests.patch(airflow_api_url, auth=auth, headers=headers, json={"is_paused": False})
            if unpause_response.status_code == 200:
                print("DAG 'dag_songs' unpausé automatiquement.")
            else:
                raise HTTPException(status_code=500, detail="Impossible d'unpause le DAG.")
    else:
        raise HTTPException(status_code=500, detail="Impossible de vérifier l'état du DAG.")
    
    # Déclencher le DAG après unpause
    dag_run_url = f"{os.getenv('AIRFLOW_BASE_URL')}/dags/dag_songs/dagRuns"
    payload = {"conf": {"songs": [song.dict() for song in request.songs]}}
    response = requests.post(dag_run_url, auth=auth, headers=headers, json=payload)
    
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Erreur lors du déclenchement du DAG 'dag_songs': {response.text}")
    
    return {"message": f"Pipeline chansons déclenché avec succès pour {len(request.songs)} chansons."}

@app.post("/ingest_fast")
async def ingest_fast(request: ArtistRequest):
    """Déclenche le pipeline d'ingestion rapide basé sur les artistes."""
    if not request.artists:
        raise HTTPException(status_code=400, detail="Liste d'artistes vide")

    # Unpause le DAG avant de lancer
    airflow_api_url = f"{os.getenv('AIRFLOW_BASE_URL')}/dags/dag_artists_fast"
    auth = (os.getenv("AIRFLOW_USER"), os.getenv("AIRFLOW_PASSWORD"))
    headers = {"Content-Type": "application/json"}
    
    response = requests.get(airflow_api_url, auth=auth, headers=headers)
    if response.status_code == 200:
        dag_info = response.json()
        if dag_info.get("is_paused"):
            unpause_response = requests.patch(airflow_api_url, auth=auth, headers=headers, json={"is_paused": False})
            if unpause_response.status_code == 200:
                print("DAG 'dag_artists_fast' unpausé automatiquement.")
            else:
                raise HTTPException(status_code=500, detail="Impossible d'unpause le DAG 'dag_artists_fast'.")
    else:
        raise HTTPException(status_code=500, detail="Impossible de vérifier l'état du DAG 'dag_artists_fast'.")

    # Déclencher le DAG après unpause
    dag_run_url = f"{os.getenv('AIRFLOW_BASE_URL')}/dags/dag_artists_fast/dagRuns"
    payload = {"conf": {"artists": request.artists}}
    response = requests.post(dag_run_url, auth=auth, headers=headers, json=payload)

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Erreur lors du déclenchement du DAG 'dag_artists_fast': {response.text}")

    return {"message": f"Pipeline rapide déclenché avec succès pour {len(request.artists)} artistes."}

@app.post("/ingest_songs_fast")
async def ingest_songs(request: SongRequest):
    """Déclenche le pipeline d'ingestion rapide basé sur les chansons."""
    if not request.songs:
        raise HTTPException(status_code=400, detail="Liste de chansons vide")
    
    # Unpause le DAG avant de lancer
    airflow_api_url = f"{os.getenv('AIRFLOW_BASE_URL')}/dags/dag_songs_fast"
    auth = (os.getenv("AIRFLOW_USER"), os.getenv("AIRFLOW_PASSWORD"))
    headers = {"Content-Type": "application/json"}
    
    response = requests.get(airflow_api_url, auth=auth, headers=headers)
    if response.status_code == 200:
        dag_info = response.json()
        if dag_info.get("is_paused"):
            unpause_response = requests.patch(airflow_api_url, auth=auth, headers=headers, json={"is_paused": False})
            if unpause_response.status_code == 200:
                print("DAG 'dag_songs_fast' unpausé automatiquement.")
            else:
                raise HTTPException(status_code=500, detail="Impossible d'unpause le DAG.")
    else:
        raise HTTPException(status_code=500, detail="Impossible de vérifier l'état du DAG.")
    
    # Déclencher le DAG après unpause
    dag_run_url = f"{os.getenv('AIRFLOW_BASE_URL')}/dags/dag_songs_fast/dagRuns"
    payload = {"conf": {"songs": [song.dict() for song in request.songs]}}
    response = requests.post(dag_run_url, auth=auth, headers=headers, json=payload)
    
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Erreur lors du déclenchement du DAG 'dag_songs_fast': {response.text}")
    
    return {"message": f"Pipeline rapide chansons déclenché avec succès pour {len(request.songs)} chansons."}