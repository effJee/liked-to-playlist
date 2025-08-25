from __future__ import annotations

import time
import base64
import requests
from typing import Dict, List, Tuple, Optional
from . import settings

AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API_BASE = "https://api.spotify.com/v1"

SCOPES = [
    "user-library-read",
    "playlist-modify-private",
    "playlist-modify-public",
]

class SpotifyAPI:
    def __init__(self, access_token: str, refresh_token: Optional[str] = None, expires_at: Optional[float] = None):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_at = expires_at or 0

    def _auth_header(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}"}

    @staticmethod
    def build_auth_url(client_id: str, redirect_uri: str, state: str) -> str:
        scope_str = "%20".join(SCOPES)
        return (
            f"{AUTH_URL}?client_id={client_id}"
            f"&response_type=code"
            f"&redirect_uri={redirect_uri}"
            f"&scope={scope_str}"
            f"&state={state}"
            f"&show_dialog=false"
        )

    @staticmethod
    def exchange_code_for_token(code: str) -> Dict:
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.SPOTIFY_REDIRECT_URI,
        }
        auth_header = base64.b64encode(
            f"{settings.SPOTIFY_CLIENT_ID}:{settings.SPOTIFY_CLIENT_SECRET}".encode()
        ).decode()
        headers = {"Authorization": f"Basic {auth_header}", "Content-Type": "application/x-www-form-urlencoded"}
        resp = requests.post(TOKEN_URL, data=data, headers=headers)
        resp.raise_for_status()
        token = resp.json()
        token["expires_at"] = time.time() + token.get("expires_in", 3600) - 30
        return token

    def ensure_fresh_token(self) -> None:
        if time.time() < (self.expires_at or 0) - 5:
            return
        if not self.refresh_token:
            return
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
        }
        auth_header = base64.b64encode(
            f"{settings.SPOTIFY_CLIENT_ID}:{settings.SPOTIFY_CLIENT_SECRET}".encode()
        ).decode()
        headers = {"Authorization": f"Basic {auth_header}", "Content-Type": "application/x-www-form-urlencoded"}
        resp = requests.post(TOKEN_URL, data=data, headers=headers)
        resp.raise_for_status()
        t = resp.json()
        # access_token & expires_in always present; refresh_token may be omitted
        self.access_token = t["access_token"]
        self.expires_at = time.time() + t.get("expires_in", 3600) - 30
        if t.get("refresh_token"):
            self.refresh_token = t["refresh_token"]

    # ===== API Calls =====
    def get_current_user(self) -> Dict:
        self.ensure_fresh_token()
        r = requests.get(f"{API_BASE}/me", headers=self._auth_header())
        r.raise_for_status()
        return r.json()

    def list_liked_tracks(self, limit: int = 50, max_count: Optional[int] = None) -> List[str]:
        """Return a list of track URIs for all saved tracks. Optionally cap to max_count.
        """
        self.ensure_fresh_token()
        uris: List[str] = []
        next_url = f"{API_BASE}/me/tracks?limit={limit}"
        while next_url:
            r = requests.get(next_url, headers=self._auth_header())
            r.raise_for_status()
            data = r.json()
            for item in data.get("items", []):
                track = item.get("track") or {}
                uri = track.get("uri")
                if uri:
                    uris.append(uri)
                    if max_count and len(uris) >= max_count:
                        return uris
            next_url = data.get("next")
        return uris

    def create_playlist(self, user_id: str, name: str, public: bool = False, description: Optional[str] = None) -> str:
        self.ensure_fresh_token()
        payload = {
            "name": name,
            "public": public,
            "description": description or "Auto-generated from Liked Songs",
        }
        r = requests.post(f"{API_BASE}/users/{user_id}/playlists", json=payload, headers=self._auth_header())
        r.raise_for_status()
        return r.json()["id"]

    def add_tracks_to_playlist(self, playlist_id: str, uris: List[str]) -> None:
        self.ensure_fresh_token()
        # Spotify allows up to 100 URIs per request
        for i in range(0, len(uris), 100):
            batch = uris[i:i+100]
            r = requests.post(
                f"{API_BASE}/playlists/{playlist_id}/tracks",
                json={"uris": batch},
                headers=self._auth_header(),
            )
            r.raise_for_status()