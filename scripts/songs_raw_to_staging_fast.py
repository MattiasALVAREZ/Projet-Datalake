import boto3
import pymysql
import os
import json
import re
from dotenv import load_dotenv
from datetime import datetime
from dateutil import parser
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
from unidecode import unidecode

# Chargement des variables d'environnement
load_dotenv(dotenv_path="/opt/airflow/.env")

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")
BUCKET_NAME = os.getenv("BUCKET_NAME")

MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE")
MYSQL_PORT = int(os.getenv("MYSQL_PORT"))

# Initialisation du client S3
s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION,
)

def create_mysql_connection():
    """Crée une nouvelle connexion MySQL pour chaque thread."""
    return pymysql.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        port=MYSQL_PORT,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )

def format_release_date(release_date: str) -> str:
    """Formate la date de sortie dans un format compatible MySQL (YYYY-MM-DD)."""
    if not release_date or release_date.lower() == "unknown":
        return None

    try:
        parsed_date = parser.parse(release_date, default=datetime(1900, 1, 1))
        return parsed_date.strftime("%Y-%m-%d")
    except Exception as e:
        print(f"Erreur de formatage de la date complète : {release_date} - Erreur : {e}")
    
    try:
        if re.match(r"^[A-Za-z]+\s\d{4}$", release_date):
            parsed_date = parser.parse(f"1 {release_date}")
            return parsed_date.strftime("%Y-%m-%d")
        elif re.match(r"^\d{4}$", release_date):
            return f"{release_date}-01-01"
    except Exception as e:
        print(f"Erreur de formatage pour date partielle : {release_date} - Erreur : {e}")
    
    return None

def clean_lyrics(raw_lyrics: str) -> str:
    """Nettoie les paroles en supprimant les balises et les espaces inutiles."""
    if not raw_lyrics or raw_lyrics == "Paroles indisponibles":
        return "Paroles indisponibles"
    raw_lyrics = re.sub(r"^Paroles\s*:", "", raw_lyrics)
    raw_lyrics = re.sub(r"\[.*?\]", "", raw_lyrics)
    return "\n".join(line.strip() for line in raw_lyrics.split("\n") if line.strip())

def list_files_for_requested_songs(songs: list) -> list:
    """Liste uniquement les fichiers JSON correspondants aux chansons demandées."""
    response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix="raw/")
    all_files = [obj["Key"] for obj in response.get("Contents", []) if obj["Key"].endswith(".json")]
    
    target_files = []
    for song in songs:
        safe_title = unidecode(song["title"]).replace(" ", "_").lower()
        safe_artist = unidecode(song["artist"]).replace(" ", "_").lower()
        expected_key = f"raw/{safe_artist}_{safe_title}.json"
        if expected_key in all_files:
            target_files.append(expected_key)
    
    return target_files

def process_song_file(file_key: str):
    """Lit et insère un fichier JSON de chanson dans MySQL."""
    try:
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=file_key)
        data = json.loads(response["Body"].read().decode("utf-8"))
    except Exception as e:
        print(f"Erreur lors de la récupération du fichier S3 {file_key} : {e}")
        return

    artist_name = data["artist"]["name"]
    artist_bio = data["artist"].get("bio", "Biographie non disponible")
    artist_image_url = data["artist"].get("image_url", "")

    connection = create_mysql_connection()

    try:
        with connection.cursor() as cursor:
            # Insertion ou mise à jour de l'artiste
            cursor.execute(
                """
                INSERT INTO artists (name, bio, image_url) 
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE bio=VALUES(bio), image_url=VALUES(image_url)
                """,
                (artist_name, artist_bio, artist_image_url),
            )
            connection.commit()

            cursor.execute("SELECT id FROM artists WHERE name = %s", (artist_name,))
            artist_id = cursor.fetchone()["id"]

            # Préparation des données de la chanson
            title = data.get("title", "Titre inconnu")
            url = data.get("url", "")
            image_url = data.get("image_url", "")
            language = data.get("language", "unknown")
            release_date_raw = data.get("release_date", None)
            release_date = format_release_date(release_date_raw)
            pageviews = data.get("pageviews", 0)

            lyrics = clean_lyrics(data.get("lyrics", ""))
            french_lyrics = clean_lyrics(data.get("french_lyrics", ""))

            cursor.execute(
                """
                INSERT INTO songs (artist_id, title, url, image_url, language, release_date, pageviews, lyrics, french_lyrics)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                    url=VALUES(url), 
                    image_url=VALUES(image_url), 
                    pageviews=VALUES(pageviews), 
                    lyrics=VALUES(lyrics),
                    french_lyrics=VALUES(french_lyrics)
                """,
                (artist_id, title, url, image_url, language, release_date, pageviews, lyrics, french_lyrics),
            )
            connection.commit()

        print(f"Chanson insérée : {title} ({artist_name})")

    except Exception as e:
        connection.rollback()
        print(f"Erreur MySQL pour {artist_name} : {e}")
    finally:
        connection.close()

def process_all_songs(songs: list):
    """Parcourt les fichiers JSON spécifiés sur S3 en multithreading."""
    files = list_files_for_requested_songs(songs)
    print(f"Fichiers trouvés : {len(files)}")

    with ThreadPoolExecutor(max_workers=min(8, len(files))) as executor:
        futures = {executor.submit(process_song_file, file_key): file_key for file_key in files}
        
        for future in as_completed(futures):
            file_key = futures[future]
            try:
                future.result()
            except Exception as e:
                print(f"Erreur lors du traitement de {file_key} : {e}")

if __name__ == "__main__":
    if len(sys.argv) < 3 or len(sys.argv) % 2 == 0:
        print("Usage : python songs_raw_to_staging_fast.py <title1> <artist1> [<title2> <artist2> ...]")
        sys.exit(1)
    
    songs = [{"title": sys.argv[i], "artist": sys.argv[i + 1]} for i in range(1, len(sys.argv), 2)]
    process_all_songs(songs)
