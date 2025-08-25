from __future__ import annotations

from typing import Optional
from fastapi import Form

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from jinja2 import Environment, FileSystemLoader, select_autoescape
import secrets
from . import settings
from .spotify import SpotifyAPI

app = FastAPI(title="Liked Songs → Playlist")
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY, same_site="lax", https_only=False)

# Templates
jinja_env = Environment(
    loader=FileSystemLoader("templates"),
    autoescape=select_autoescape(["html", "xml"]),
)

def render(tpl: str, **ctx):
    template = jinja_env.get_template(tpl)
    return HTMLResponse(content=template.render(**ctx))

@app.get("/")
def home(request: Request):
    logged_in = bool(request.session.get("access_token"))
    return render("index.html", logged_in=logged_in)

@app.get("/login")
def login(request: Request):
    state = secrets.token_urlsafe(16)
    request.session["oauth_state"] = state
    auth_url = SpotifyAPI.build_auth_url(settings.SPOTIFY_CLIENT_ID, settings.SPOTIFY_REDIRECT_URI, state)
    return RedirectResponse(auth_url)

@app.get("/callback")
def callback(request: Request, code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    if error:
        raise HTTPException(400, f"Spotify error: {error}")
    if not code or not state:
        raise HTTPException(400, "Missing code/state")
    if state != request.session.get("oauth_state"):
        raise HTTPException(400, "Invalid state (CSRF)")

    token = SpotifyAPI.exchange_code_for_token(code)

    request.session.update({
        "access_token": token["access_token"],
        "refresh_token": token.get("refresh_token"),
        "expires_at": token.get("expires_at"),
    })
    return RedirectResponse("/")

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")

@app.post("/create-playlist")
def create_playlist(request: Request, name: str = Form(settings.PLAYLIST_NAME)):
    print(name)
    access = request.session.get("access_token")
    if not access:
        return RedirectResponse("/login")

    api = SpotifyAPI(
        access_token=access,
        refresh_token=request.session.get("refresh_token"),
        expires_at=request.session.get("expires_at"),
    )
    # After ensure_fresh_token, persist in session if refreshed
    api.ensure_fresh_token()
    request.session["access_token"] = api.access_token
    request.session["refresh_token"] = api.refresh_token
    request.session["expires_at"] = api.expires_at

    me = api.get_current_user()
    user_id = me.get("id")

    uris = api.list_liked_tracks(limit=50)
    if not uris:
        return render("done.html", playlist_url=None, count=0)

    playlist_id = api.create_playlist(user_id=user_id, name=name, public=True)
    api.add_tracks_to_playlist(playlist_id, uris)

    playlist_url = f"https://open.spotify.com/playlist/{playlist_id}"
    return render("done.html", playlist_url=playlist_url, count=len(uris))
