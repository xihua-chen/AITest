import os
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel

load_dotenv()

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_hex(32))
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24
COOKIE_NAME = "auth_token"

# Simplified email validation regex (handles the most common valid formats)
EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI()

# --------------- In-memory stores ---------------
users: dict[str, dict] = {}          # user_id -> {id, login, name, avatar_url}
todos: dict[str, list[dict]] = {}    # user_id -> [{id, text, done}]
oauth_states: dict[str, float] = {}  # state -> timestamp
email_users: dict[str, dict] = {}    # email -> {id, email, name, password_hash}

# --------------- Pydantic models ---------------

class TodoCreate(BaseModel):
    text: str


class TodoUpdate(BaseModel):
    done: bool


class EmailLoginRequest(BaseModel):
    email: str
    password: str

# --------------- Helpers ---------------

def create_jwt(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> str | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


def get_current_user(request: Request) -> dict:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user_id = decode_jwt(token)
    if not user_id or user_id not in users:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return users[user_id]


# --------------- OAuth2 endpoints ---------------

@app.get("/auth/github")
async def auth_github():
    state = secrets.token_urlsafe(32)
    oauth_states[state] = datetime.now(timezone.utc).timestamp()
    # Clean up states older than 10 minutes
    cutoff = datetime.now(timezone.utc).timestamp() - 600
    for s in [k for k, v in oauth_states.items() if v < cutoff]:
        oauth_states.pop(s, None)
    url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_CLIENT_ID}"
        f"&redirect_uri={BASE_URL}/auth/github/callback"
        f"&state={state}"
        f"&scope=read:user"
    )
    return RedirectResponse(url)


@app.get("/auth/github/callback")
async def auth_github_callback(code: str = "", state: str = ""):
    # Validate state
    if not state or state not in oauth_states:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    oauth_states.pop(state, None)

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    async with httpx.AsyncClient() as client:
        # Exchange code for access token
        token_resp = await client.post(
            "https://github.com/login/oauth/access_token",
            json={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": f"{BASE_URL}/auth/github/callback",
            },
            headers={"Accept": "application/json"},
        )
        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="Failed to obtain access token")

        # Fetch user info
        user_resp = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        user_data = user_resp.json()

    github_id = str(user_data["id"])
    users[github_id] = {
        "id": github_id,
        "login": user_data.get("login", ""),
        "name": user_data.get("name") or user_data.get("login", ""),
        "avatar_url": user_data.get("avatar_url", ""),
    }
    todos.setdefault(github_id, [])

    token = create_jwt(github_id)
    response = RedirectResponse("/")
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        max_age=JWT_EXPIRY_HOURS * 3600,
    )
    return response


@app.post("/auth/logout")
async def logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(COOKIE_NAME)
    return response


@app.post("/auth/email")
async def auth_email(body: EmailLoginRequest):
    """Authenticate (or register) a user with email + password."""
    email = body.email.strip().lower()

    if not EMAIL_REGEX.match(email):
        raise HTTPException(status_code=400, detail="Invalid email address format.")

    if len(body.password) < 6:
        raise HTTPException(
            status_code=400, detail="Password must be at least 6 characters."
        )

    password_hash = pwd_context.hash(body.password)

    if email in email_users:
        # Existing user – verify password
        if not pwd_context.verify(body.password, email_users[email]["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid email or password.")
        user_id = email_users[email]["id"]
    else:
        # New user – register
        user_id = "email-" + uuid.uuid4().hex[:8]
        email_users[email] = {
            "id": user_id,
            "email": email,
            "name": email.split("@")[0],
            "password_hash": password_hash,
        }
        users[user_id] = {
            "id": user_id,
            "login": email,
            "name": email.split("@")[0],
            "avatar_url": "",
        }
        todos.setdefault(user_id, [])

    token = create_jwt(user_id)
    response = JSONResponse({"ok": True, "user": users[user_id]})
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        max_age=JWT_EXPIRY_HOURS * 3600,
    )
    return response


# --------------- User info ---------------

@app.get("/api/me")
async def me(user: dict = Depends(get_current_user)):
    return user


# --------------- Todo API ---------------

@app.get("/api/todos")
async def list_todos(user: dict = Depends(get_current_user)):
    return todos.get(user["id"], [])


@app.post("/api/todos")
async def add_todo(body: TodoCreate, user: dict = Depends(get_current_user)):
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="Todo text is required")
    item = {"id": uuid.uuid4().hex[:8], "text": body.text.strip(), "done": False}
    todos.setdefault(user["id"], []).append(item)
    return item


@app.delete("/api/todos/{todo_id}")
async def delete_todo(todo_id: str, user: dict = Depends(get_current_user)):
    user_todos = todos.get(user["id"], [])
    for i, t in enumerate(user_todos):
        if t["id"] == todo_id:
            user_todos.pop(i)
            return {"ok": True}
    raise HTTPException(status_code=404, detail="Todo not found")


@app.patch("/api/todos/{todo_id}")
async def update_todo(todo_id: str, body: TodoUpdate, user: dict = Depends(get_current_user)):
    user_todos = todos.get(user["id"], [])
    for t in user_todos:
        if t["id"] == todo_id:
            t["done"] = body.done
            return t
    raise HTTPException(status_code=404, detail="Todo not found")


# --------------- Serve frontend ---------------

@app.get("/", response_class=HTMLResponse)
async def index():
    with open("index.html", encoding="utf-8") as f:
        return f.read()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
