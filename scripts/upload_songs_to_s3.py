import requests
import boto3
import json
import os
import logging
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from unidecode import unidecode
import sys
from concurrent.futures import ThreadPoolExecutor
from requests.adapters import HTTPAdapter, Retry

# Utiliser le logger Airflow pour éviter les conflits de logs
logger = logging.getLogger("airflow.task")

# Charger les variables d'environnement
load_dotenv(dotenv_path="/opt/airflow/.env")

GENIUS_ACCESS_TOKEN = os.getenv("GENIUS_ACCESS_TOKEN")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")
BUCKET_NAME = os.getenv("BUCKET_NAME")

BASE_URL = "https://api.genius.com"

# Configuration des sessions HTTP avec gestion des retries
retries = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"]
)

# Session pour l'API Genius
api_session = requests.Session()
api_session.headers.update({"Authorization": f"Bearer {GENIUS_ACCESS_TOKEN}"})
api_session.mount("https://", HTTPAdapter(max_retries=retries))

# Session pour le scraping des paroles
lyrics_session = requests.Session()
lyrics_session.mount("https://", HTTPAdapter(max_retries=retries))

# Client S3 réutilisé pour éviter les reconnections fréquentes
s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION,
)

def request_genius(endpoint, params=None):
    """Effectue une requête à l'API Genius avec gestion des erreurs et des retries."""
    try:
        logger.info(f"[API] Requête vers : {endpoint} avec paramètres : {params}")
        response = api_session.get(f"{BASE_URL}{endpoint}", params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Erreur lors de la requête API : {e}")
        return None

def get_song_details_by_title_and_artist(song_title, artist_name):
    """Recherche une chanson par son titre et son artiste et récupère ses détails."""
    data = request_genius("/search", {"q": f"{song_title} {artist_name}"})
    if not data:
        return None

    for hit in data["response"]["hits"]:
        song = hit["result"]
        if (
            unidecode(song["title"].lower()) == unidecode(song_title.lower()) and
            unidecode(song["primary_artist"]["name"].lower()) == unidecode(artist_name.lower())
        ):
            song_id = song["id"]
            return request_genius(f"/songs/{song_id}")["response"]["song"]
    
    logger.warning(f"Chanson introuvable : {song_title} par {artist_name}")
    return None

def get_artist_details(artist_id):
    """Récupère les informations de l'artiste avec gestion des erreurs."""
    data = request_genius(f"/artists/{artist_id}")
    if not data:
        return {"name": "Inconnu", "image_url": "", "bio": "Biographie non disponible"}

    artist = data["response"]["artist"]
    bio_text = ""
    if "description" in artist and "dom" in artist["description"]:
        for item in artist["description"]["dom"].get("children", []):
            if isinstance(item, dict) and "children" in item:
                bio_text += "".join([c if isinstance(c, str) else "" for c in item["children"]])

    return {
        "name": artist["name"],
        "image_url": artist.get("image_url", ""),
        "bio": bio_text.strip() or "Biographie non disponible",
    }

def get_song_lyrics(song_url):
    """Scrape les paroles d'une chanson depuis Genius avec gestion des erreurs."""
    try:
        logger.info(f"Scraping des paroles depuis : {song_url}")
        response = lyrics_session.get(song_url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        lyrics_divs = soup.find_all("div", {"data-lyrics-container": "true"})
        lyrics = "\n".join(div.get_text(separator="\n") for div in lyrics_divs)
        return lyrics.strip() if lyrics else "Paroles indisponibles"
    except Exception as e:
        logger.error(f"Erreur lors du scraping des paroles : {e}")
        return "Paroles indisponibles"

def upload_song_to_s3(song_title, artist_name):
    """Récupère les détails d'une chanson spécifique et les téléverse sur S3."""
    song_data = get_song_details_by_title_and_artist(song_title, artist_name)
    if not song_data:
        logger.warning(f"Chanson introuvable : {song_title} par {artist_name}")
        return

    artist_info = get_artist_details(song_data["primary_artist"]["id"])
    lyrics = get_song_lyrics(song_data["url"])
    french_lyrics = ""

    if song_data.get("language") != "fr":
        fr_translation = next((t for t in song_data.get("translation_songs", []) if t["language"] == "fr"), None)
        if fr_translation:
            french_lyrics = get_song_lyrics(fr_translation["url"])

    song_info = {
        "title": song_data["title"],
        "artist": artist_info,
        "url": song_data["url"],
        "image_url": song_data.get("song_art_image_url", ""),
        "language": song_data.get("language", "unknown"),
        "release_date": song_data.get("release_date_for_display", "unknown"),
        "pageviews": song_data["stats"].get("pageviews", 0),
        "lyrics": lyrics,
        "french_lyrics": french_lyrics
    }

    s3_key = f"raw/{unidecode(artist_name).replace(' ', '_').lower()}_{unidecode(song_title).replace(' ', '_').lower()}.json"

    try:
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=json.dumps(song_info, ensure_ascii=False, indent=4).encode("utf-8"),
            ContentType="application/json"
        )
        logger.info(f"Téléversé sur S3 : {s3_key}")
    except Exception as e:
        logger.error(f"Erreur lors du téléversement sur S3 : {e}")

def process_songs_in_parallel(songs):
    """Traite les chansons en parallèle avec ThreadPoolExecutor."""
    max_workers = min(8, len(songs))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for title, artist in songs:
            executor.submit(upload_song_to_s3, title, artist)

if __name__ == "__main__":
    if len(sys.argv) < 3 or len(sys.argv) % 2 == 0:
        sys.exit(1)
    
    songs = list(zip(sys.argv[1::2], sys.argv[2::2]))
    process_songs_in_parallel(songs)
