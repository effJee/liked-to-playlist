import os
from dotenv import load_dotenv

# load_dotenv()  # loads .env in local dev; in cloud, use environment panel

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
SECRET_KEY = os.getenv("SECRET_KEY")
PLAYLIST_NAME = os.getenv("PLAYLIST_NAME")