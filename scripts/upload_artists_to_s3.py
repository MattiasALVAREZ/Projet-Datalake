import requests
import boto3
import json
import os
import sys
import logging
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from unidecode import unidecode

# Charger les variables d'environnement
load_dotenv(dotenv_path="/opt/airflow/.env")

GENIUS_ACCESS_TOKEN = os.getenv("GENIUS_ACCESS_TOKEN")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")
BUCKET_NAME = os.getenv("BUCKET_NAME")

# Configuration du logger pour Airflow et le terminal
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Initialisation du client S3
s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION,
)

BASE_URL = "https://api.genius.com"

def request_genius(endpoint, params=None):
    headers = {"Authorization": f"Bearer {GENIUS_ACCESS_TOKEN}"}
    response = requests.get(f"{BASE_URL}{endpoint}", headers=headers, params=params, timeout=10)
    if response.status_code == 200:
        return response.json()
    else:
        logger.error(f"Erreur API ({response.status_code}) : {response.text}")
        return None

def get_artist_id(artist_name):
    normalized_name = unidecode(artist_name.lower())
    logger.info(f"Recherche de l'ID pour l'artiste : {artist_name}")
    data = request_genius("/search", {"q": normalized_name})
    if not data:
        logger.warning(f"Aucune donnée retournée pour l'artiste : {artist_name}")
        return None

    for hit in data["response"]["hits"]:
        name = unidecode(hit["result"]["primary_artist"]["name"].lower())
        if name == normalized_name:
            artist_id = hit["result"]["primary_artist"]["id"]
            logger.info(f"ID trouvé pour {artist_name} : {artist_id}")
            return artist_id

    logger.warning(f"Aucun match exact pour {artist_name}.")
    return None

def get_artist_details(artist_id):
    data = request_genius(f"/artists/{artist_id}")
    if not data:
        return None

    artist = data["response"]["artist"]
    bio_text = ""
    if "description" in artist and "dom" in artist["description"]:
        for item in artist["description"]["dom"].get("children", []):
            if isinstance(item, dict) and "children" in item:
                bio_text += "".join([c if isinstance(c, str) else "" for c in item["children"]])

    return {
        "name": artist["name"],
        "image_url": artist["image_url"],
        "bio": bio_text.strip(),
    }

def get_popular_songs_by_artist(artist_id):
    data = request_genius(f"/artists/{artist_id}/songs", {"sort": "popularity", "per_page": 50})
    if not data:
        return []

    primary_songs = [song for song in data["response"]["songs"] if song["primary_artist"]["id"] == artist_id]
    logger.info(f"{len(primary_songs[:20])} chansons trouvées pour l'artiste ID : {artist_id}")
    return primary_songs[:20]

def get_song_lyrics(song_url):
    try:
        response = requests.get(song_url, timeout=10)
        if response.status_code != 200:
            return "Paroles indisponibles"

        soup = BeautifulSoup(response.text, "html.parser")
        lyrics_divs = soup.find_all("div", {"data-lyrics-container": "true"})
        lyrics = "\n".join(div.get_text(separator="\n") for div in lyrics_divs)

        return lyrics.strip() if lyrics else "Paroles indisponibles"
    except Exception as e:
        logger.error(f"Erreur lors du scraping des paroles : {e}")
        return "Paroles indisponibles"

def get_song_details(song_id):
    """Récupère les détails d'une chanson en utilisant uniquement release_date_display."""
    data = request_genius(f"/songs/{song_id}")
    if not data:
        return None

    song = data["response"]["song"]
    release_date = song.get("release_date_for_display", "unknown")

    details = {
        "title": song["title"],
        "url": song["url"],
        "image_url": song["song_art_image_url"],
        "language": song.get("language", "unknown"),
        "release_date": release_date,
        "pageviews": song["stats"].get("pageviews", 0),
        "lyrics": get_song_lyrics(song["url"]),
        "french_lyrics": "",
    }

    # Récupération des paroles traduites si disponibles
    if details["language"] != "fr":
        french_translation = next(
            (t for t in song.get("translation_songs", []) if isinstance(t, dict) and str(t.get("language", "")).startswith("fr")),
            None
        )
        if french_translation and "url" in french_translation:
            translation_url = french_translation["url"]
            logger.info(f"Récupération des paroles traduites depuis : {translation_url}")
            details["french_lyrics"] = get_song_lyrics(translation_url)

    return details

def upload_to_s3(key, content):
    try:
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=key,
            Body=json.dumps(content, ensure_ascii=False, indent=4).encode("utf-8"),
            ContentType="application/json",
        )
        logger.info(f"Téléversement réussi : {key}")
    except Exception as e:
        logger.error(f"Erreur lors du téléversement sur S3 : {str(e)}")

def process_artists(artists):
    for artist_name in artists:
        artist_id = get_artist_id(artist_name)
        if not artist_id:
            logger.warning(f"Artiste non trouvé : {artist_name}")
            continue

        artist_details = get_artist_details(artist_id)
        songs = get_popular_songs_by_artist(artist_id)

        song_details = []
        for song in songs:
            details = get_song_details(song["id"])
            if details:
                song_details.append(details)

        artist_data = {
            "artist": artist_details,
            "songs": song_details,
        }
        s3_key = f"raw/{unidecode(artist_name).replace(' ', '_').lower()}.json"
        upload_to_s3(s3_key, artist_data)

if __name__ == "__main__":
    artists = sys.argv[1:]
    process_artists(artists)
