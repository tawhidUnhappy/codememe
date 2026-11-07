"""YouTube upload: OAuth for an installed app (browser login once, loopback redirect, PKCE) and the
resumable videos.insert upload. Stdlib only. The client secret and token live in global/youtube/
(gitignored); nothing here ever prints them."""

from __future__ import annotations

import base64
import hashlib
import http.server
import json
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

from .paths import ROOT, read_json, write_json

DIR = ROOT / "global" / "youtube"
SECRET = DIR / "client_secret.json"
TOKEN = DIR / "token.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"]
API = "https://www.googleapis.com/youtube/v3"
UPLOAD = "https://www.googleapis.com/upload/youtube/v3/videos"


class QuotaExceeded(SystemExit):
    pass


def _client() -> dict:
    if not SECRET.exists():
        raise SystemExit(f"Put the Google OAuth client file at {SECRET} (see README: YouTube).")
    return read_json(SECRET)["installed"]


def _post(url: str, data: dict) -> dict:
    req = urllib.request.Request(url, urllib.parse.urlencode(data).encode(), {"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Google said {e.code}: {e.read().decode()[:300]}") from None


def login() -> None:
    c = _client()
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    got: dict = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            got.update(urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query))
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"codememe is signed in. You can close this tab.")

        def log_message(self, *a):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    redirect = f"http://127.0.0.1:{server.server_port}"
    state = secrets.token_urlsafe(16)
    url = c["auth_uri"] + "?" + urllib.parse.urlencode({
        "client_id": c["client_id"], "redirect_uri": redirect, "response_type": "code", "scope": " ".join(SCOPES),
        "code_challenge": challenge, "code_challenge_method": "S256", "access_type": "offline", "prompt": "consent", "state": state})
    print("Open this link and sign in with the Google account that owns the channel:\n\n" + url + "\n")
    webbrowser.open(url)
    threading.Thread(target=server.handle_request, daemon=True).start()
    for _ in range(600):
        if got:
            break
        time.sleep(1)
    server.server_close()
    if got.get("state") != [state] or "code" not in got:
        raise SystemExit(f"Sign-in did not finish ({got.get('error', 'no answer')}).")
    tok = _post(c["token_uri"], {"code": got["code"][0], "client_id": c["client_id"], "client_secret": c["client_secret"],
                                  "redirect_uri": redirect, "grant_type": "authorization_code", "code_verifier": verifier})
    tok["expires_at"] = time.time() + tok["expires_in"] - 60
    DIR.mkdir(parents=True, exist_ok=True)
    write_json(TOKEN, tok)
    TOKEN.chmod(0o600)
    print("Signed in. Token saved to global/youtube/token.json")


def access_token() -> str:
    if not TOKEN.exists():
        raise SystemExit("Not signed in: run ./run.sh youtube-login first.")
    tok, c = read_json(TOKEN), _client()
    if tok["expires_at"] < time.time():
        fresh = _post(c["token_uri"], {"refresh_token": tok["refresh_token"], "client_id": c["client_id"],
                                       "client_secret": c["client_secret"], "grant_type": "refresh_token"})
        tok.update(fresh, expires_at=time.time() + fresh["expires_in"] - 60)
        write_json(TOKEN, tok)
    return tok["access_token"]


def _call(method: str, url: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(url, json.dumps(body).encode() if body is not None else None, method=method,
                                 headers={"Authorization": f"Bearer {access_token()}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        _raise(e)


def _raise(e: urllib.error.HTTPError):
    text = e.read().decode()
    if "quotaExceeded" in text or "uploadLimitExceeded" in text:
        raise QuotaExceeded("YouTube's daily quota/upload limit is used up - run the same command tomorrow; finished videos are skipped.")
    raise SystemExit(f"YouTube said {e.code}: {text[:400]}") from None


def playlist_id(title: str) -> str:
    """The channel's playlist called `title` - made (private-by-default is not needed, public) if absent."""
    page = _call("GET", f"{API}/playlists?part=snippet&mine=true&maxResults=50")
    for item in page.get("items", []):
        if item["snippet"]["title"] == title:
            return item["id"]
    made = _call("POST", f"{API}/playlists?part=snippet,status",
                 {"snippet": {"title": title}, "status": {"privacyStatus": "public"}})
    return made["id"]


def add_to_playlist(playlist: str, video_id: str) -> None:
    _call("POST", f"{API}/playlistItems?part=snippet",
          {"snippet": {"playlistId": playlist, "resourceId": {"kind": "youtube#video", "videoId": video_id}}})


def upload_video(path: Path, meta: dict, privacy: str, publish_at: str | None = None) -> str:
    """Resumable upload; returns the video id. `publish_at` (RFC 3339, UTC) schedules it (it is then private until then)."""
    status = {"privacyStatus": "private" if publish_at else privacy, "selfDeclaredMadeForKids": False}
    if publish_at:
        status["publishAt"] = publish_at
    body = {"snippet": {"title": meta["title"][:100], "description": meta["description"], "tags": meta.get("tags", []),
                        "categoryId": "27"}, "status": status}
    size = path.stat().st_size
    start = urllib.request.Request(
        f"{UPLOAD}?uploadType=resumable&part=snippet,status", json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Bearer {access_token()}", "Content-Type": "application/json; charset=UTF-8",
                 "X-Upload-Content-Length": str(size), "X-Upload-Content-Type": "video/mp4"})
    try:
        with urllib.request.urlopen(start, timeout=60) as r:
            session = r.headers["Location"]
    except urllib.error.HTTPError as e:
        _raise(e)
    with path.open("rb") as f:
        put = urllib.request.Request(session, f.read(), method="PUT", headers={"Content-Type": "video/mp4", "Content-Length": str(size)})
    try:
        with urllib.request.urlopen(put, timeout=900) as r:
            return json.load(r)["id"]
    except urllib.error.HTTPError as e:
        _raise(e)
