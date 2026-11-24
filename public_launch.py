"""Optional public-launch features. No database writes at import/startup.
Enable only after the additive SQL migration and operational/privacy review.
"""
from __future__ import annotations

import logging
import os
import re
import time
from collections import OrderedDict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from typing import Literal

from fastapi import Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, StringConstraints
from typing import Annotated

logger = logging.getLogger(__name__)


def flag(name):
    return os.getenv(name, "false").strip().lower() == "true"


@dataclass(frozen=True)
class LaunchSettings:
    enabled: bool = False
    signup: bool = False
    admin_id: str = ""
    operator: str = ""
    email: str = ""
    privacy_url: str = ""
    terms_url: str = ""
    policy_version: str = ""

    @property
    def policy_ready(self):
        def valid_url(value):
            try:
                u = urlsplit(value)
                return u.scheme == 'https' and bool(u.hostname) and not u.username and not u.password and not any(ch.isspace() for ch in value)
            except ValueError:
                return False
        return bool(self.operator.strip()
                    and re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', self.email)
                    and valid_url(self.privacy_url) and valid_url(self.terms_url)
                    and re.fullmatch(r'[A-Za-z0-9._-]{1,40}', self.policy_version))

    @property
    def signup_ready(self):
        return bool(self.enabled and self.signup and self.policy_ready)

    @property
    def admin(self):
        try:
            value = int(self.admin_id)
            return value if 0 < value <= 2**63 - 1 else None
        except (ValueError, TypeError):
            return None


settings = LaunchSettings(
    enabled=flag('PUBLIC_LAUNCH_ENABLED'), signup=flag('PUBLIC_SIGNUP_ENABLED'),
    admin_id=os.getenv('PUBLIC_ADMIN_USER_ID', ''), operator=os.getenv('PUBLIC_OPERATOR_NAME', ''),
    email=os.getenv('PUBLIC_CONTACT_EMAIL', ''), privacy_url=os.getenv('PUBLIC_PRIVACY_URL', ''),
    terms_url=os.getenv('PUBLIC_TERMS_URL', ''), policy_version=os.getenv('PUBLIC_POLICY_VERSION', ''),
)


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


class RateLimiter:
    """Bounded per-worker sliding windows. Use edge limits for public deployment.
    Global limits prevent unlimited IPs from exhausting the key store or Argon2.
    No raw forwarded header is trusted here. Do not log bucket keys.
    """
    def __init__(self):
        self.buckets = OrderedDict()

    def check(self, action, key, limit, window):
        now = time.monotonic()
        ident = (action, str(key))
        bucket = self.buckets.get(ident)
        if bucket is None:
            # Do not evict live buckets (which would allow a trivial bypass).
            if len(self.buckets) >= 4096:
                for k, values in list(self.buckets.items()):
                    if not values or values[-1] <= now - 3600:
                        self.buckets.pop(k, None)
                if len(self.buckets) >= 4096:
                    raise HTTPException(429, 'Za dużo prób. Spróbuj później.', headers={'Retry-After': '60'})
            bucket = self.buckets.setdefault(ident, deque())
        while bucket and bucket[0] <= now - window:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(429, 'Za dużo prób. Spróbuj później.', headers={'Retry-After': str(max(1, int(bucket[0] + window - now) + 1))})
        bucket.append(now)
        self.buckets.move_to_end(ident)


def init_state(app):
    app.state.launch_limits = RateLimiter()
    if settings.enabled and settings.signup and not settings.signup_ready:
        logger.warning('Public signup disabled: missing or invalid operator/policy configuration')


def rate_auth(request, action):
    limiter = request.app.state.launch_limits
    ip = request.client.host if request.client else 'unknown'
    if action == 'login':
        limiter.check('login-global', '*', 120, 60)
        limiter.check('login-ip', ip, 15, 300)
    elif action == 'register':
        limiter.check('register-global', '*', 30, 3600)
        limiter.check('register-ip', ip, 5, 3600)
    else:
        limiter.check(action, ip, 10, 300)


def check_registration(data):
    if not settings.signup_ready:
        raise HTTPException(403, 'Rejestracja nowych kont jest obecnie zamknięta. Możesz skorzystać z demo.')
    if len(data.password) < 12:
        raise HTTPException(422, 'Hasło nowego konta musi mieć co najmniej 12 znaków.')
    if data.accept_terms is not True or data.policy_version != settings.policy_version:
        raise HTTPException(422, 'Przeczytaj aktualny regulamin i informację o prywatności, a następnie zaakceptuj regulamin.')


async def record_activity(database, user_id):
    if not settings.enabled:
        return
    # Best-effort, no failure of the main operation. Do not collect IPs or browsing history.
    try:
        now = now_iso()
        async with database() as db:
            await db.execute('''INSERT INTO public_activity (user_id, last_active)
                SELECT id, ? FROM users WHERE id = ?
                ON CONFLICT(user_id) DO UPDATE SET last_active = excluded.last_active
                WHERE substr(public_activity.last_active, 1, 10) <> substr(excluded.last_active, 1, 10)''', [now, user_id])
    except HTTPException:
        logger.warning('Public activity could not be recorded; verify migration')


async def register_user(db, username, hashed, policy_version):
    # Serialized by the caller's BEGIN IMMEDIATE. Retired IDs are never reused.
    r = await db.execute('''SELECT MAX(n) FROM (
        SELECT COALESCE(MAX(id), 0) AS n FROM users
        UNION ALL SELECT COALESCE(MAX(id), 0) FROM public_retired_users)''')
    new_id = int(r.rows[0][0]) + 1
    if new_id > 2**53 - 1:  # frontend uses JS safe integers
        raise HTTPException(503, 'Nie można przydzielić identyfikatora konta.')
    await db.execute('INSERT INTO users (id, username, password_hash) VALUES (?, ?, ?)', [new_id, username, hashed])
    await db.execute('INSERT INTO public_terms_acceptance (user_id, version, accepted_at) VALUES (?, ?, ?)', [new_id, policy_version, now_iso()])


class FeedbackInput(BaseModel):
    category: Literal['idea', 'bug', 'other']
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=2000)]


class DeleteAccountInput(BaseModel):
    password: Annotated[str, StringConstraints(min_length=1, max_length=1024)]
    confirmation: Literal['USUN']


def add_routes(app, *, database, transaction, current_user, verify_password, telegram_user_id):
    def require_features():
        if not settings.enabled:
            raise HTTPException(503, 'Funkcja nie jest jeszcze włączona.')

    async def admin(user_id: int = Depends(current_user)):
        require_features()
        if user_id != settings.admin:
            raise HTTPException(403, 'Brak uprawnień administratora.')
        return user_id

    async def active(db, user_id):
        r = await db.execute('SELECT username FROM users WHERE id = ?', [user_id])
        if not r.rows:
            raise HTTPException(401, 'Konto nie istnieje.')
        return r.rows[0][0]

    @app.get('/public/config')
    async def config():
        s = settings
        # The config contains only intentionally public information.
        return JSONResponse({'features_enabled': s.enabled, 'signup_enabled': s.signup_ready,
            'operator': s.operator, 'contact_email': s.email,
            'privacy_url': s.privacy_url if s.policy_ready else '',
            'terms_url': s.terms_url if s.policy_ready else '',
            'policy_version': s.policy_version if s.policy_ready else ''}, headers={'Cache-Control': 'no-store'})

    @app.get('/account/capabilities')
    async def capabilities(user_id: int = Depends(current_user)):
        return {'public_features': settings.enabled, 'admin': settings.enabled and user_id == settings.admin,
                'can_delete': settings.enabled and user_id not in (settings.admin, telegram_user_id())}

    @app.post('/feedback')
    async def feedback(data: FeedbackInput, request: Request, user_id: int = Depends(current_user)):
        require_features()
        request.app.state.launch_limits.check('feedback-user', user_id, 5, 3600)
        async with transaction() as db:
            await active(db, user_id)
            cutoff = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(timespec='seconds')
            count = await db.execute('SELECT COUNT(*) FROM public_feedback WHERE user_id = ? AND created_at >= ?', [user_id, cutoff])
            if count.rows[0][0] >= 10:
                raise HTTPException(429, 'Osiągnięto dzienny limit zgłoszeń.')
            await db.execute('INSERT INTO public_feedback (user_id, category, message, created_at) VALUES (?, ?, ?, ?)', [user_id, data.category, data.message, now_iso()])
        return {'status': 'success'}

    @app.get('/account/export')
    async def export(request: Request, user_id: int = Depends(current_user)):
        require_features()
        request.app.state.launch_limits.check('export-user', user_id, 3, 300)
        async with transaction() as db:
            username = await active(db, user_id)
            async def rows(sql, keys):
                result = await db.execute(sql, [user_id])
                return [dict(zip(keys, row)) for row in result.rows]
            games = await rows('SELECT id,title,platform,release_date,in_budget,cover_url FROM games WHERE user_id = ? ORDER BY id', ('id','title','platform','release_date','in_budget','cover_url'))
            offers = await rows('SELECT o.game_id,o.store_name,o.price,o.order_number,o.url FROM store_offers o JOIN games g ON g.id=o.game_id WHERE g.user_id = ?', ('game_id','store_name','price','order_number','url'))
            collection = await rows('SELECT id,title,platform,release_date,date_added,cover_url FROM collections WHERE user_id = ?', ('id','title','platform','release_date','date_added','cover_url'))
            messages = await rows('SELECT id,category,message,created_at FROM public_feedback WHERE user_id = ?', ('id','category','message','created_at'))
            activity = await rows('SELECT last_active FROM public_activity WHERE user_id = ?', ('last_active',))
            consent = await rows('SELECT version,accepted_at FROM public_terms_acceptance WHERE user_id = ?', ('version','accepted_at'))
            weekly = []
            if (await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='weekly_summary_runs'", [])).rows:
                weekly = await rows('SELECT week_start,status FROM weekly_summary_runs WHERE user_id = ?', ('week_start','status'))
        return JSONResponse({'format_version': 1, 'exported_at': now_iso(), 'account': {'id':user_id,'username':username}, 'games': games,'offers': offers,'collection':collection,'feedback':messages,'activity':activity,'terms_acceptance':consent,'weekly_summary_runs':weekly}, headers={'Cache-Control':'no-store','Content-Disposition':'attachment; filename="preorderhub-export.json"'})

    @app.post('/account/delete')
    async def delete_account(data: DeleteAccountInput, request: Request, user_id: int = Depends(current_user)):
        require_features()
        if user_id in (settings.admin, telegram_user_id()):
            raise HTTPException(403, 'Konto administratora lub odbiorcy Telegrama wymaga wcześniejszej zmiany konfiguracji operatora.')
        rate_auth(request, 'delete-account')
        async with database() as db:
            r = await db.execute('SELECT password_hash FROM users WHERE id = ?', [user_id])
        if not r.rows:
            raise HTTPException(401, 'Konto nie istnieje.')
        stored = r.rows[0][0]
        async with request.app.state.password_slots:
            ok, _ = await run_in_threadpool(verify_password, data.password, stored, request.app.state.dummy_hash)
        if not ok:
            raise HTTPException(403, 'Nieprawidłowe hasło.')
        async with transaction() as db:
            r = await db.execute('SELECT password_hash FROM users WHERE id = ?', [user_id])
            if not r.rows or r.rows[0][0] != stored:
                raise HTTPException(409, 'Dane konta się zmieniły. Zaloguj się ponownie.')
            await db.execute('INSERT INTO public_retired_users (id) VALUES (?)', [user_id])
            await db.execute('DELETE FROM store_offers WHERE game_id IN (SELECT id FROM games WHERE user_id = ?)', [user_id])
            for table in ('games', 'collections', 'public_feedback', 'public_activity', 'public_terms_acceptance'):
                # Fixed internal identifiers, never supplied by the client.
                await db.execute(f'DELETE FROM {table} WHERE user_id = ?', [user_id])
            if (await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='weekly_summary_runs'", [])).rows:
                await db.execute('DELETE FROM weekly_summary_runs WHERE user_id = ?', [user_id])
            await db.execute('DELETE FROM users WHERE id = ?', [user_id])
        return {'status': 'success'}

    @app.get('/admin/overview')
    async def overview(user_id: int = Depends(admin)):
        cutoff = (datetime.now(timezone.utc).date() - timedelta(days=6)).isoformat()
        async with database() as db:
            async def count(sql, args=()):
                return (await db.execute(sql, list(args))).rows[0][0]
            total = await count('SELECT COUNT(*) FROM users')
            active7 = await count('SELECT COUNT(*) FROM public_activity a JOIN users u ON u.id=a.user_id WHERE substr(a.last_active,1,10) >= ?', [cutoff])
            games = await count('SELECT COUNT(*) FROM games')
            feedback_count = await count('SELECT COUNT(*) FROM public_feedback')
            result = await db.execute('SELECT id,category,message,created_at FROM public_feedback ORDER BY id DESC LIMIT 50', [])
        return JSONResponse({'users':total,'active_7d':active7,'preorders':games,'feedback_count':feedback_count,
            'feedback':[dict(zip(('id','category','message','created_at'),r)) for r in result.rows]}, headers={'Cache-Control':'no-store'})
