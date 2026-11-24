"""Preorder Hub API. Python 3.10+, Pydantic 2.

Existing tables: users, games, store_offers, collections.
For the weekly Telegram job, apply weekly_summary.sql once before enabling it.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import inspect
import logging
import os
import re
import secrets
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated
from types import SimpleNamespace
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import httpx
import public_launch as launch
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import (
    AliasChoices, BaseModel, ConfigDict, Field, StrictBool, StringConstraints,
    field_validator, model_validator,
)

logger = logging.getLogger(__name__)
# Telegram uses its bot token in the URL. Do not log HTTP request URLs.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

SECRET_KEY = os.getenv("SECRET_KEY", "")
DATABASE_URL = os.getenv("TURSO_DATABASE_URL", "")
DATABASE_TOKEN = os.getenv("TURSO_AUTH_TOKEN")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))
ALLOW_LEGACY_PLAINTEXT = os.getenv("ALLOW_LEGACY_PLAINTEXT_PASSWORDS", "false").lower() == "true"
TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
# Support the old environment variable during migration.
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET") or os.getenv("TWITCH_CLIENT_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_USER_ID = os.getenv("TELEGRAM_USER_ID")
CRON_SECRET = os.getenv("CRON_SECRET", "")
APP_TIMEZONE = ZoneInfo(os.getenv("APP_TIMEZONE", "Europe/Warsaw"))

password_hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def validate_config() -> None:
    if len(SECRET_KEY.encode("utf-8")) < 32:
        raise RuntimeError("SECRET_KEY must contain at least 32 bytes of secure random material")
    if not DATABASE_URL:
        raise RuntimeError("Missing TURSO_DATABASE_URL")
    turso_https_url(DATABASE_URL)
    if not DATABASE_TOKEN:
        raise RuntimeError("Missing TURSO_AUTH_TOKEN")
    if ACCESS_TOKEN_EXPIRE_MINUTES <= 0:
        raise RuntimeError("ACCESS_TOKEN_EXPIRE_MINUTES must be positive")
    if CRON_SECRET:
        if len(CRON_SECRET.encode("utf-8")) < 32 or secrets.compare_digest(CRON_SECRET.encode(), SECRET_KEY.encode()):
            raise RuntimeError("CRON_SECRET must be a separate strong secret (at least 32 bytes)")
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID or not (TELEGRAM_USER_ID or "").isdigit() or int(TELEGRAM_USER_ID) <= 0:
            raise RuntimeError("Cron requires TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID and positive TELEGRAM_USER_ID")


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_config()
    launch.init_state(app)
    if ALLOW_LEGACY_PLAINTEXT:
        logger.warning("Legacy plaintext password verification is enabled; disable after migration")
    app.state.twitch_token = None
    app.state.twitch_expires_at = 0.0
    app.state.twitch_lock = asyncio.Lock()
    # Limit expensive password computations per worker.
    app.state.password_slots = asyncio.Semaphore(4)
    app.state.dummy_hash = await run_in_threadpool(password_hasher.hash, secrets.token_hex(32))
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0), follow_redirects=False) as http:
        app.state.http = http
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0), follow_redirects=False) as db_http:
            app.state.db_http = db_http
            yield


app = FastAPI(title="Preorder Hub API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://preordergames.dwiad1110.workers.dev",
        "http://localhost:5500",
        "https://preorderhub.pl",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    # Never return raw input (e.g. passwords) or Pydantic's internal context.
    return JSONResponse(status_code=422, content={"detail": [
        {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
        for error in exc.errors()
    ]})


# ==========================================
# INPUT MODELS
# ==========================================
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
Platform = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
PositiveID = Annotated[int, Field(gt=0, le=2**63 - 1, strict=True)]
Price = Annotated[Decimal, Field(ge=0, le=Decimal("99999999.99"), max_digits=10, decimal_places=2, allow_inf_nan=False)]


def parse_game_date(value: str | None) -> date | None:
    """Only a known day qualifies for a weekly notification."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return date.fromisoformat(value)
        if re.fullmatch(r"\d{1,2}\.\d{1,2}\.\d{4}", value):
            return datetime.strptime(value, "%d.%m.%Y").date()
    except ValueError:
        pass
    return None


def validate_release_date(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    value = value.strip()
    if parse_game_date(value) is not None:
        return value
    if re.fullmatch(r"\d{4}-\d{2}", value):
        year, month = map(int, value.split("-"))
        if 1 <= year <= 9999 and 1 <= month <= 12:
            return value
    if re.fullmatch(r"\d{4}(?:-Q[1-4])?", value, re.IGNORECASE) and int(value[:4]) > 0:
        return value.upper()
    if value.upper() in {"TBA", "TBD"}:
        return value.upper()
    raise ValueError("Data: YYYY-MM-DD, DD.MM.YYYY, YYYY-MM, YYYY, YYYY-Q1..Q4, TBA lub TBD")


class InputModel(BaseModel):
    model_config = ConfigDict(extra="ignore")  # Keep compatibility with older frontend payloads.


class RegisterInput(InputModel):
    username: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    password: Annotated[str, StringConstraints(min_length=8, max_length=1024)]
    accept_terms: StrictBool = False
    policy_version: str | None = Field(default=None, max_length=40)


class OfferInput(InputModel):
    store_name: Text
    price: Price
    order_number: str | None = Field(default=None, max_length=300)
    url: str | None = Field(default=None, max_length=2048)

    @field_validator("url")
    @classmethod
    def check_url(cls, value):
        if not value:
            return value
        value = value.strip()
        if not value:
            return None
        if any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in value) or "\\" in value:
            raise ValueError("Nieprawidłowy adres URL")
        try:
            parsed = urlsplit(value)
            if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname or parsed.username is not None or parsed.password is not None:
                raise ValueError
            _ = parsed.port
        except ValueError:
            raise ValueError("Adres oferty musi być poprawnym URL HTTP/HTTPS") from None
        return value


class AddPreorderInput(InputModel):
    title: Text
    platform: Platform
    release_date: str | None = Field(default=None, max_length=40)
    in_budget: StrictBool = True
    offers: list[OfferInput] = Field(default_factory=list, max_length=50)

    _release_date = field_validator("release_date")(validate_release_date)


class GameReference(InputModel):
    game_id: PositiveID | None = Field(default=None, validation_alias=AliasChoices("game_id", "id"))
    title: Text | None = None
    platform: Platform | None = None

    @model_validator(mode="after")
    def check_reference(self):
        if self.game_id is None and (self.title is None or self.platform is None):
            raise ValueError("Podaj game_id lub title i platform")
        return self


class EditPreorderInput(InputModel):
    game_id: PositiveID | None = Field(default=None, validation_alias=AliasChoices("game_id", "id"))
    original_title: Text | None = None
    original_platform: Platform | None = None
    title: Text | None = None
    platform: Platform | None = None
    release_date: str | None = Field(default=None, max_length=40)
    offers: list[OfferInput] = Field(default_factory=list, max_length=50)
    in_budget: StrictBool | None = None

    _release_date = field_validator("release_date")(validate_release_date)

    @model_validator(mode="after")
    def check_edit(self):
        if self.game_id is None and (self.original_title is None or self.original_platform is None):
            raise ValueError("Podaj game_id lub original_title i original_platform")
        for field in ("title", "platform", "in_budget"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"Pole {field} nie może być null")
        return self


class BudgetInput(GameReference):
    in_budget: StrictBool


class CollectionReference(InputModel):
    id: PositiveID


# ==========================================
# DATABASE / ATOMIC TRANSACTIONS
# ==========================================
# Turso's documented Hrana HTTP v2 protocol. Unlike the archived Python
# libsql-client, this uses HTTPS even for a libsql:// database URL.
# Each client is a single logical stream; its baton is never shared across requests.
# Protocol: https://github.com/tursodatabase/libsql/blob/main/docs/HTTP_V2_SPEC.md
class TursoDatabaseError(RuntimeError):
    def __init__(self, code):
        safe_code = str(code or "UNKNOWN")
        self.code = safe_code if re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", safe_code) else "UNKNOWN"
        super().__init__(f"Turso database error ({self.code})")


def turso_https_url(value: str, *, allow_prefix: bool = False) -> str:
    try:
        parts = urlsplit(value.strip())
        if (parts.scheme.lower() not in ({"https"} if allow_prefix else {"https", "libsql", "wss"})
                or not parts.hostname or parts.username is not None or parts.password is not None
                or parts.query or parts.fragment or any(ch.isspace() for ch in value.strip())
                or (not allow_prefix and parts.path not in {"", "/"})):
            raise ValueError
        _ = parts.port
    except ValueError:
        raise RuntimeError("TURSO_DATABASE_URL must be a database URL without credentials, e.g. https://database.turso.io") from None
    return urlunsplit(("https", parts.netloc, parts.path.rstrip("/"), "", ""))


def encode_db_value(value):
    if value is None:
        return {"type": "null"}
    if isinstance(value, int):
        return {"type": "integer", "value": str(int(value))}
    if isinstance(value, float):
        return {"type": "float", "value": value}
    if isinstance(value, str):
        return {"type": "text", "value": value}
    if isinstance(value, bytes):
        return {"type": "blob", "base64": base64.b64encode(value).decode("ascii")}
    raise TypeError("Unsupported SQL parameter")


def decode_db_value(value):
    kind = value["type"]
    if kind == "null":
        return None
    if kind == "integer":
        return int(value["value"])
    if kind == "float":
        return float(value["value"]) if value["value"] is not None else float("nan")
    if kind == "text":
        return value["value"]
    if kind == "blob":
        encoded = value["base64"]
        return base64.b64decode(encoded + "=" * (-len(encoded) % 4), validate=True)
    raise TursoDatabaseError("UNSUPPORTED_VALUE")


class TursoHTTPClient:
    def __init__(self, http, url, token):
        self.http = http
        self.base_url = turso_https_url(url)
        self.origin = urlsplit(self.base_url)
        self.token = token
        self.baton = None
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    def _update_base_url(self, value):
        target = turso_https_url(value, allow_prefix=True)
        parts = urlsplit(target)
        # Do not send the database token to an arbitrary host or over plaintext.
        same_origin = (parts.hostname, parts.port or 443) == (self.origin.hostname, self.origin.port or 443)
        turso_route = (self.origin.hostname.endswith(".turso.io") and parts.hostname.endswith(".turso.io")
                       and (parts.port or 443) == 443)
        if not (same_origin or turso_route):
            raise TursoDatabaseError("UNTRUSTED_BASE_URL")
        self.base_url = target

    async def _request(self, command):
        if self.closed:
            raise TursoDatabaseError("STREAM_CLOSED")
        try:
            response = await self.http.post(
                self.base_url + "/v2/pipeline",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"baton": self.baton, "requests": [command]},
            )
            response.raise_for_status()
            payload = response.json()
            baton = payload["baton"]
            if baton is not None and (not isinstance(baton, str) or not baton):
                raise TursoDatabaseError("INVALID_BATON")
            self.baton = baton
            if baton is None:
                # A closed stream must never silently restart inside a transaction.
                self.closed = True
            if payload.get("base_url") is not None:
                self._update_base_url(payload["base_url"])
            results = payload["results"]
            if len(results) != 1:
                raise TursoDatabaseError("INVALID_RESULT_COUNT")
            item = results[0]
            if item["type"] not in {"ok", "error"}:
                raise TursoDatabaseError("INVALID_RESULT_TYPE")
            if item["type"] == "ok" and item["response"]["type"] != command["type"]:
                raise TursoDatabaseError("INVALID_RESPONSE_TYPE")
        except httpx.HTTPStatusError as exc:
            self.closed = True
            raise TursoDatabaseError(f"HTTP_{exc.response.status_code}") from None
        except BaseException:
            # Transport or malformed response: the server may already have applied
            # the command. Never retry blindly, or open a replacement stream.
            self.closed = True
            raise
        if item["type"] == "error":
            # A SQL error is not a transport failure: keep the baton for rollback.
            raise TursoDatabaseError(item.get("error", {}).get("code"))
        return item["response"]

    async def execute(self, sql, args=()):
        response = await self._request({"type": "execute", "stmt": {
            "sql": sql, "args": [encode_db_value(value) for value in args], "want_rows": True,
        }})
        result = response["result"]
        return SimpleNamespace(
            rows=[tuple(decode_db_value(value) for value in row) for row in result["rows"]],
            rows_affected=int(result["affected_row_count"]),
            last_insert_rowid=int(result["last_insert_rowid"]) if result["last_insert_rowid"] is not None else None,
        )

    async def transaction(self):
        await self.execute("BEGIN IMMEDIATE")
        if self.closed:
            raise TursoDatabaseError("TRANSACTION_STREAM_CLOSED")
        return self

    async def commit(self):
        await self.execute("COMMIT")

    async def rollback(self):
        await self.execute("ROLLBACK")

    async def close(self):
        if self.closed:
            return
        try:
            if self.baton is not None:
                await self._request({"type": "close"})
        except Exception as exc:
            log_db_error(exc, "Turso stream cleanup failed")
        finally:
            self.closed = True


def get_db_client():
    return TursoHTTPClient(app.state.db_http, DATABASE_URL, DATABASE_TOKEN)


def log_db_error(exc: BaseException, message: str) -> None:
    logger.error("%s (%s, code=%s)", message, type(exc).__name__, getattr(exc, "code", "unknown"))


@asynccontextmanager
async def database():
    try:
        async with get_db_client() as client:
            yield client
    except HTTPException:
        raise
    except Exception as exc:
        log_db_error(exc, "Database operation failed")
        raise HTTPException(500, "Nie udało się wykonać operacji w bazie.") from None


async def maybe_await(result):
    return await result if inspect.isawaitable(result) else result


@asynccontextmanager
async def transaction():
    """Use a real interactive transaction, not separate autocommitted queries."""
    async with database() as client:
        tx = await maybe_await(client.transaction())
        try:
            yield tx
            await maybe_await(tx.commit())
        except BaseException:
            try:
                await maybe_await(tx.rollback())
            except Exception as exc:
                log_db_error(exc, "Rollback failed")
            raise
        finally:
            close = getattr(tx, "close", None)
            if close is not None:
                try:
                    await maybe_await(close())
                except Exception as exc:
                    log_db_error(exc, "Transaction cleanup failed")


def normalize(value: str) -> str:
    return value.strip().casefold()


async def find_game(db, user_id: int, game_id=None, title=None, platform=None):
    sql = "SELECT id, title, platform, release_date, in_budget, cover_url FROM games WHERE user_id = ?"
    if game_id is not None:
        result = await db.execute(sql + " AND id = ?", [user_id, game_id])
        rows = result.rows
    else:
        # Legacy frontend: no guessing if old duplicate records are present.
        result = await db.execute(sql, [user_id])
        rows = [row for row in result.rows if isinstance(row[1], str) and isinstance(row[2], str)
                and normalize(row[1]) == normalize(title) and normalize(row[2]) == normalize(platform)]
    if not rows:
        raise HTTPException(404, "Gra nie została znaleziona.")
    if len(rows) != 1:
        raise HTTPException(409, "Znaleziono kilka gier. Podaj game_id.")
    return tuple(rows[0])


async def ensure_unique_game(db, user_id, title, platform, exclude_id=None):
    result = await db.execute("SELECT id, title, platform FROM games WHERE user_id = ?", [user_id])
    if any(row[0] != exclude_id and isinstance(row[1], str) and isinstance(row[2], str)
           and normalize(row[1]) == normalize(title) and normalize(row[2]) == normalize(platform)
           for row in result.rows):
        raise HTTPException(409, "Taka gra na tej platformie już istnieje.")


async def insert_offers(db, game_id, offers):
    if not offers:
        return
    # One statement, inside the same transaction as the game write.
    placeholders = ", ".join(["(?, ?, ?, ?, ?)"] * len(offers))
    args = []
    for offer in offers:
        # Preserve existing numeric column/API. Exact minor units need a schema migration.
        args.extend([game_id, offer.store_name, float(offer.price), offer.order_number, offer.url])
    await db.execute(
        "INSERT INTO store_offers (game_id, store_name, price, order_number, url) VALUES " + placeholders,
        args,
    )


# ==========================================
# AUTHENTICATION AND PASSWORD MIGRATION
# ==========================================
def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)},
                      SECRET_KEY, algorithm=ALGORITHM)


def unauthorized(detail="Nieprawidłowa nazwa użytkownika lub hasło."):
    return HTTPException(401, detail, headers={"WWW-Authenticate": "Bearer"})


async def get_current_user(token: str = Depends(oauth2_scheme)) -> int:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"require": ["exp", "sub"]})
        subject = payload["sub"]
        if not isinstance(subject, str) or not re.fullmatch(r"[1-9][0-9]{0,18}", subject):
            raise ValueError
        user_id = int(subject)
        if user_id > 2**63 - 1:
            raise ValueError
    except jwt.ExpiredSignatureError:
        raise unauthorized("Token wygasł") from None
    except (jwt.InvalidTokenError, ValueError, TypeError, KeyError):
        raise unauthorized("Nieprawidłowy token") from None
    async with database() as db:
        result = await db.execute("SELECT id FROM users WHERE id = ?", [user_id])
        if not result.rows:
            raise unauthorized("Konto nie istnieje")
    return user_id


def verify_and_upgrade(password: str, stored: str, dummy_hash: str) -> tuple[bool, str | None]:
    if not isinstance(stored, str):
        return False, None
    if stored.startswith("$argon2id$"):
        try:
            password_hasher.verify(stored, password)
            return True, password_hasher.hash(password) if password_hasher.check_needs_rehash(stored) else None
        except (VerificationError, InvalidHashError):
            return False, None
    # The old API trimmed passwords; preserve this behavior only for old hashes.
    legacy_password = password.strip()
    if re.fullmatch(r"[a-f0-9]{32}\$[a-f0-9]{64}", stored):
        salt, expected = stored.split("$")
        calculated = hashlib.pbkdf2_hmac("sha256", legacy_password.encode(), salt.encode(), 100000).hex()
        valid = secrets.compare_digest(calculated, expected)
    elif "$" not in stored and ALLOW_LEGACY_PLAINTEXT:
        valid = secrets.compare_digest(legacy_password.encode(), stored.encode())
    else:
        valid = False
    if valid:
        return True, password_hasher.hash(legacy_password)
    # Comparable computational work for failed legacy or unknown accounts.
    try:
        password_hasher.verify(dummy_hash, password)
    except (VerificationError, InvalidHashError):
        pass
    return False, None


@app.post("/register")
async def register(data: RegisterInput, request: Request):
    launch.check_registration(data)
    launch.rate_auth(request, "register")
    async with request.app.state.password_slots:
        hashed = await run_in_threadpool(password_hasher.hash, data.password)
    async with transaction() as db:
        result = await db.execute("SELECT id FROM users WHERE username = ?", [data.username])
        if result.rows:
            raise HTTPException(409, "Użytkownik o takiej nazwie już istnieje.")
        try:
            await launch.register_user(db, data.username, hashed, data.policy_version)
        except Exception as exc:
            if getattr(exc, "code", None) == "SQLITE_CONSTRAINT_UNIQUE":
                raise HTTPException(409, "Użytkownik o takiej nazwie już istnieje.") from None
            raise
    return {"status": "success", "message": "Rejestracja udana!"}


@app.post("/login")
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    launch.rate_auth(request, "login")
    username = form_data.username.strip()
    password = form_data.password  # Never trim passwords for new accounts.
    if not username or len(username) > 100 or not password or len(password) > 1024:
        raise unauthorized()
    async with database() as db:
        result = await db.execute("SELECT id, password_hash FROM users WHERE username = ?", [username])
    stored = result.rows[0][1] if result.rows else request.app.state.dummy_hash
    async with request.app.state.password_slots:
        valid, upgraded = await run_in_threadpool(verify_and_upgrade, password, stored, request.app.state.dummy_hash)
    if not result.rows or not valid:
        raise unauthorized()
    user_id = result.rows[0][0]
    if upgraded:
        async with database() as db:
            update = await db.execute("UPDATE users SET password_hash = ? WHERE id = ? AND password_hash = ?", [upgraded, user_id, stored])
            if update.rows_affected != 1:
                raise unauthorized("Dane konta zostały zmienione. Zaloguj się ponownie.")
    await launch.record_activity(database, user_id)
    return {"access_token": create_access_token(user_id), "token_type": "bearer", "user_id": user_id, "username": username}


# ==========================================
# TWITCH / IGDB (NON-BLOCKING, TOKEN CACHE)
# ==========================================
async def get_twitch_token(state, rejected_token=None):
    if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET:
        return None
    async with state.twitch_lock:
        if (state.twitch_token and state.twitch_token != rejected_token
                and time.monotonic() < state.twitch_expires_at):
            return state.twitch_token
        try:
            response = await state.http.post("https://id.twitch.tv/oauth2/token", data={
                "client_id": TWITCH_CLIENT_ID, "client_secret": TWITCH_CLIENT_SECRET,
                "grant_type": "client_credentials",
            })
            response.raise_for_status()
            data = response.json()
            token, expires = data["access_token"], int(data["expires_in"])
            if not isinstance(token, str) or not token or expires <= 0:
                raise ValueError
            state.twitch_token = token
            state.twitch_expires_at = time.monotonic() + max(0, expires - 60)
            return token
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            logger.warning("Twitch token request failed (%s)", type(exc).__name__)
            return None


async def get_igdb_cover_url(title: str, state) -> str | None:
    token = await get_twitch_token(state)
    if not token:
        return None
    # Search for a safe approximation of titles containing APICalypse delimiters.
    safe_title = " ".join(re.sub(r'["\\;\x00-\x1f\x7f]', " ", title).split())
    if not safe_title:
        return None
    query = f'search "{safe_title}"; fields cover.image_id; limit 1;'
    try:
        for attempt in range(2):
            response = await state.http.post("https://api.igdb.com/v4/games", headers={
                "Client-ID": TWITCH_CLIENT_ID, "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            }, content=query.encode("utf-8"))
            if response.status_code == 401 and attempt == 0:
                token = await get_twitch_token(state, rejected_token=token)
                if not token:
                    return None
                continue
            response.raise_for_status()
            data = response.json()
            image_id = data[0].get("cover", {}).get("image_id") if data else None
            if isinstance(image_id, str) and re.fullmatch(r"[A-Za-z0-9_-]+", image_id):
                return f"https://images.igdb.com/igdb/image/upload/t_cover_big/{image_id}.jpg"
            return None
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
        logger.warning("IGDB cover request failed (%s)", type(exc).__name__)
    return None


# ==========================================
# PREORDERS AND OFFERS
# ==========================================
@app.get("/get_preorders")
async def get_preorders(current_user: int = Depends(get_current_user)):
    async with database() as db:
        result = await db.execute("""
            SELECT g.id, g.title, g.platform, g.release_date, g.in_budget, g.cover_url,
                   o.game_id, o.store_name, o.price, o.order_number, o.url
            FROM games g LEFT JOIN store_offers o ON o.game_id = g.id
            WHERE g.user_id = ? ORDER BY g.id
        """, [current_user])
    games = {}
    for row in result.rows:
        game_id, title, platform, release, budget, cover, offer_game_id, store, price, order_no, url = tuple(row)
        if game_id not in games:
            games[game_id] = {"id": game_id, "game_id": game_id, "title": title, "platform": platform,
                              "release_date": release, "in_budget": bool(budget) if budget is not None else True,
                              "cover_url": cover, "offers": []}
        if offer_game_id is not None:
            games[game_id]["offers"].append({"store_name": store, "price": price, "order_number": order_no, "url": url})
    await launch.record_activity(database, current_user)
    return list(games.values())


@app.post("/add")
async def add_preorder(data: AddPreorderInput, request: Request, current_user: int = Depends(get_current_user)):
    cover = await get_igdb_cover_url(data.title, request.app.state)
    async with transaction() as db:
        if not (await db.execute("SELECT id FROM users WHERE id = ?", [current_user])).rows:
            raise unauthorized("Konto nie istnieje")
        await ensure_unique_game(db, current_user, data.title, data.platform)
        result = await db.execute("""
            INSERT INTO games (user_id, title, platform, release_date, cover_url, in_budget)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [current_user, data.title, data.platform, data.release_date, cover, int(data.in_budget)])
        game_id = result.last_insert_rowid
        if game_id is None:
            raise RuntimeError("INSERT did not return a game ID")
        await insert_offers(db, game_id, data.offers)
    return {"status": "success", "message": "Preorder dodany pomyślnie!", "game_id": game_id}


@app.put("/edit")
async def edit_preorder(data: EditPreorderInput, request: Request, current_user: int = Depends(get_current_user)):
    # External HTTP must not be executed inside a database transaction.
    async with database() as db:
        snapshot = await find_game(db, current_user, data.game_id, data.original_title, data.original_platform)
    game_id = snapshot[0]
    change_title = data.title is not None and normalize(data.title) != normalize(snapshot[1] or "")
    cover = await get_igdb_cover_url(data.title, request.app.state) if change_title else None

    async with transaction() as db:
        game = await find_game(db, current_user, game_id)
        if data.title is not None and game[1] != snapshot[1]:
            raise HTTPException(409, "Tytuł został zmieniony równolegle. Odśwież listę.")
        title = data.title if data.title is not None else game[1]
        platform = data.platform if data.platform is not None else game[2]
        if not isinstance(title, str) or not title.strip() or not isinstance(platform, str) or not platform.strip():
            raise HTTPException(422, "Uzupełnij tytuł i platformę gry.")
        if normalize(title) != normalize(game[1] or "") or normalize(platform) != normalize(game[2] or ""):
            await ensure_unique_game(db, current_user, title, platform, exclude_id=game_id)
        fields = data.model_fields_set
        release = data.release_date if "release_date" in fields else game[3]
        budget = int(data.in_budget) if "in_budget" in fields else game[4]
        # If the game title changes but IGDB fails, preserve the previous cover.
        new_cover = cover if change_title and cover is not None else game[5]
        await db.execute("""
            UPDATE games SET title = ?, platform = ?, release_date = ?, in_budget = ?, cover_url = ?
            WHERE id = ? AND user_id = ?
        """, [title, platform, release, budget, new_cover, game_id, current_user])
        if "offers" in fields:
            await db.execute("DELETE FROM store_offers WHERE game_id = ?", [game_id])
            await insert_offers(db, game_id, data.offers)
    return {"status": "success", "message": "Preorder zaktualizowany!", "game_id": game_id}


@app.delete("/delete")
async def delete_game(data: GameReference, current_user: int = Depends(get_current_user)):
    async with transaction() as db:
        game = await find_game(db, current_user, data.game_id, data.title, data.platform)
        await db.execute("DELETE FROM store_offers WHERE game_id = ?", [game[0]])
        await db.execute("DELETE FROM games WHERE id = ? AND user_id = ?", [game[0], current_user])
    return {"status": "success"}


@app.post("/update_budget")
async def update_budget(data: BudgetInput, current_user: int = Depends(get_current_user)):
    async with transaction() as db:
        game = await find_game(db, current_user, data.game_id, data.title, data.platform)
        await db.execute("UPDATE games SET in_budget = ? WHERE id = ? AND user_id = ?",
                         [int(data.in_budget), game[0], current_user])
    return {"status": "success"}


# ==========================================
# COLLECTION
# ==========================================
@app.get("/get_collection")
async def get_collection(current_user: int = Depends(get_current_user)):
    async with database() as db:
        result = await db.execute("""
            SELECT id, title, platform, release_date, date_added, cover_url
            FROM collections WHERE user_id = ? ORDER BY date_added DESC, id DESC
        """, [current_user])
    keys = ("id", "title", "platform", "release_date", "date_added", "cover_url")
    return [dict(zip(keys, row)) for row in result.rows]


@app.post("/move_to_collection")
async def move_to_collection(data: GameReference, current_user: int = Depends(get_current_user)):
    async with transaction() as db:
        game_id, title, platform, release, _, cover = await find_game(db, current_user, data.game_id, data.title, data.platform)
        result = await db.execute("""
            INSERT INTO collections (user_id, title, platform, release_date, cover_url)
            VALUES (?, ?, ?, ?, ?)
        """, [current_user, title, platform, release, cover])
        collection_id = result.last_insert_rowid
        # Original data model: moving to collection deletes preorder offers.
        await db.execute("DELETE FROM store_offers WHERE game_id = ?", [game_id])
        await db.execute("DELETE FROM games WHERE id = ? AND user_id = ?", [game_id, current_user])
    return {"status": "success", "id": collection_id}


@app.delete("/delete_from_collection")
async def delete_from_collection(data: CollectionReference, current_user: int = Depends(get_current_user)):
    async with database() as db:
        result = await db.execute("DELETE FROM collections WHERE id = ? AND user_id = ?", [data.id, current_user])
        if result.rows_affected == 0:
            raise HTTPException(404, "Gra nie została znaleziona w kolekcji.")
    return {"status": "success"}


# ==========================================
# WEEKLY TELEGRAM JOB (AUTHORIZED + DEDUP)
# ==========================================
async def authorize_cron(x_cron_secret: str | None = Header(default=None)):
    if not CRON_SECRET:
        raise HTTPException(503, "Powiadomienia cron są wyłączone.")
    if x_cron_secret is None or not secrets.compare_digest(x_cron_secret.encode(), CRON_SECRET.encode()):
        raise HTTPException(401, "Nieprawidłowy sekret cron.")


def telegram_messages(monday, sunday, games):
    header = f"📅 Preorder Hub — premiery {monday:%d.%m.%Y} – {sunday:%d.%m.%Y}\n\n"
    if not games:
        return [header + "W tym tygodniu brak premier. Portfel bezpieczny! 🎮"]
    messages, message = [], header
    for released, title, platform in games:
        # Limit legacy data; no parse_mode means user content is plain text.
        entry = f"🎮 {str(title)[:300]}\n📅 Premiera: {released:%d.%m.%Y}\n🕹️ Platforma: {str(platform)[:100]}\n--------------------\n"
        if len((message + entry).encode("utf-16-le")) // 2 > 4000:
            messages.append(message)
            message = header
        message += entry
    messages.append(message)
    return messages


@app.post("/cron/weekly_summary", dependencies=[Depends(authorize_cron)])
async def send_weekly_summary(request: Request, user_id: int | None = None):
    target = int(TELEGRAM_USER_ID)
    if user_id is not None and user_id != target:
        raise HTTPException(403, "Ten odbiorca Telegrama nie jest przypisany do użytkownika.")
    today = datetime.now(APP_TIMEZONE).date()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    week = monday.isoformat()
    async with transaction() as db:
        owner = await db.execute("SELECT id FROM users WHERE id = ?", [target])
        if not owner.rows:
            raise HTTPException(404, "Użytkownik nie istnieje.")
        existing = await db.execute("SELECT status FROM weekly_summary_runs WHERE user_id = ? AND week_start = ?", [target, week])
        if existing.rows:
            if existing.rows[0][0] == "sent":
                return {"status": "already_sent", "week_start": week}
            raise HTTPException(409, "Wysyłka trwa lub wymaga sprawdzenia. Nie ponowiono automatycznie.")
        result = await db.execute("SELECT title, platform, release_date FROM games WHERE user_id = ?", [target])
        claimed = await db.execute("""
            INSERT INTO weekly_summary_runs (user_id, week_start, status) VALUES (?, ?, 'sending')
            ON CONFLICT(user_id, week_start) DO NOTHING
        """, [target, week])
        if claimed.rows_affected != 1:
            raise HTTPException(409, "Wysyłka została już zarezerwowana.")
    games = []
    for title, platform, release in result.rows:
        released = parse_game_date(release)
        if released and monday <= released <= sunday:
            games.append((released, title, platform))
    games.sort(key=lambda game: (game[0], str(game[1]).casefold(), str(game[2]).casefold()))
    messages = telegram_messages(monday, sunday, games)
    try:
        for message in messages:
            response = await request.app.state.http.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": message},
            )
            response.raise_for_status()
            if response.json().get("ok") is not True:
                raise ValueError("Telegram did not acknowledge message")
    except (httpx.HTTPError, ValueError, AttributeError) as exc:
        logger.warning("Telegram delivery uncertain (%s)", type(exc).__name__)
        # Never retry blindly: a timeout or partial delivery may mean the message was sent.
        try:
            async with database() as db:
                await db.execute("UPDATE weekly_summary_runs SET status = 'uncertain' WHERE user_id = ? AND week_start = ? AND status = 'sending'", [target, week])
        except HTTPException:
            logger.error("Could not mark weekly summary as uncertain")
        raise HTTPException(502, "Nie potwierdzono pełnej wysyłki Telegrama. Sprawdź wiadomości przed ponowieniem.") from None
    async with database() as db:
        await db.execute("UPDATE weekly_summary_runs SET status = 'sent' WHERE user_id = ? AND week_start = ? AND status = 'sending'", [target, week])
    return {"status": "success", "sent_games_count": len(games), "sent_messages_count": len(messages)}


@app.get("/ping")
def keep_alive():
    return {"status": "ok", "message": "Preorder API is running!"}


# Optional public-launch account and feedback routes. Existing API stays on api_v2:app.
def configured_telegram_user():
    try:
        return int(TELEGRAM_USER_ID or 0) or None
    except ValueError:
        return None

launch.add_routes(app, database=database, transaction=transaction,
                  current_user=get_current_user, verify_password=verify_and_upgrade,
                  telegram_user_id=configured_telegram_user)
