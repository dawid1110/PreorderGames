"""Regression tests through the HTTPS adapter and a simulated Turso server.
Run: python -m pytest -q test_preorder_https.py
"""
import hashlib
import json
import uuid
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient

import api_v2 as main

SCHEMA = """
CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL);
CREATE TABLE games (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, title TEXT NOT NULL,
 platform TEXT NOT NULL, release_date TEXT, in_budget INTEGER DEFAULT 1, cover_url TEXT);
CREATE TABLE store_offers (id INTEGER PRIMARY KEY, game_id INTEGER NOT NULL, store_name TEXT NOT NULL
 CHECK(store_name <> 'FAIL_DB'), price REAL NOT NULL, order_number TEXT, url TEXT);
CREATE TABLE collections (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, title TEXT NOT NULL,
 platform TEXT NOT NULL, release_date TEXT, date_added TEXT DEFAULT CURRENT_TIMESTAMP, cover_url TEXT);
"""


class TursoHTTPStub:
    """In-process HTTP server using SQLite and a new single-use baton per reply."""
    def __init__(self, path):
        self.path = path
        self.streams = {}
        self.requests = []
        self.fail_next = False
        self.route = False
        self.close_after_begin = False

    def handle(self, request):
        assert request.url.scheme == 'https'
        assert request.url.path == '/v2/pipeline'
        assert request.headers['Authorization'] == 'Bearer test-token'
        payload = json.loads(request.content)
        self.requests.append((str(request.url), payload))
        if self.fail_next:
            self.fail_next = False
            return httpx.Response(400, json={'error': 'simulated transport error'})
        baton = payload['baton']
        if baton is None:
            conn = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False)
        else:
            conn = self.streams.pop(baton)
        command, = payload['requests']
        if command['type'] == 'close':
            conn.close()
            return httpx.Response(200, json={'baton': None, 'base_url': None,
                'results': [{'type': 'ok', 'response': {'type': 'close'}}]})
        stmt = command['stmt']
        try:
            cursor = conn.execute(stmt['sql'], [main.decode_db_value(arg) for arg in stmt['args']])
            result = {'cols': [], 'rows': [[main.encode_db_value(val) for val in row] for row in cursor.fetchall()],
                      'affected_row_count': max(0, cursor.rowcount), 'last_insert_rowid': str(cursor.lastrowid) if cursor.lastrowid is not None else None}
            item = {'type': 'ok', 'response': {'type': 'execute', 'result': result}}
        except sqlite3.Error as exc:
            item = {'type': 'error', 'error': {'message': 'simulated SQL failure', 'code': exc.sqlite_errorname}}
        if self.close_after_begin and stmt['sql'] == 'BEGIN IMMEDIATE':
            conn.close()
            next_baton = None
        else:
            next_baton = uuid.uuid4().hex
            self.streams[next_baton] = conn
        base_url = 'https://regional.test.turso.io' if self.route else None
        return httpx.Response(200, json={'baton': next_baton, 'base_url': base_url, 'results': [item]})

    def close(self):
        for conn in self.streams.values():
            conn.close()
        self.streams.clear()


class TelegramStub:
    def __init__(self):
        self.messages = []
        self.fail = False

    async def post(self, url, *, json):
        self.messages.append(json)
        if self.fail:
            raise httpx.ReadTimeout('simulated timeout')
        return httpx.Response(200, json={'ok': True}, request=httpx.Request('POST', 'https://example.invalid'))


@pytest.fixture
def api(tmp_path, monkeypatch):
    path = tmp_path / 'db.sqlite'
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)
        conn.executescript(Path(__file__).with_name('weekly_summary.sql').read_text())
        conn.executemany('INSERT INTO users(id, username, password_hash) VALUES (?, ?, ?)',
                         [(1, 'user1', 'not-a-password'), (2, 'user2', 'not-a-password')])
    for key, value in {
        'SECRET_KEY': 'jwt-test-key-' * 4,
        'DATABASE_URL': 'https://test.turso.io',
        'DATABASE_TOKEN': 'test-token',
        'TWITCH_CLIENT_ID': None,
        'TWITCH_CLIENT_SECRET': None,
        'TELEGRAM_BOT_TOKEN': 'fake',
        'TELEGRAM_CHAT_ID': '42',
        'TELEGRAM_USER_ID': '1',
        'CRON_SECRET': 'cron-test-key-' * 4,
        'ALLOW_LEGACY_PLAINTEXT': False,
    }.items():
        monkeypatch.setattr(main, key, value)
    stub = TursoHTTPStub(path)
    # Test the actual application's HTTP adapter, not a substitute get_db_client.
    http = httpx.AsyncClient(transport=httpx.MockTransport(stub.handle))
    original_lifespan = main.app.router.lifespan_context
    from contextlib import asynccontextmanager
    @asynccontextmanager
    async def lifespan(app):
        async with original_lifespan(app):
            async with http:
                app.state.db_http = http
                yield
    monkeypatch.setattr(main.app.router, 'lifespan_context', lifespan)
    try:
        with TestClient(main.app) as client:
            telegram = TelegramStub()
            main.app.state.http = telegram
            client.headers['Authorization'] = 'Bearer ' + main.create_access_token(1)
            client.db_stub = stub
            yield client, path, telegram
            assert not stub.streams, 'Leaked SQL stream'
    finally:
        stub.close()


def add(client, title='Game', **kwargs):
    response = client.post('/add', json={
        'title': title, 'platform': 'PS5', 'offers': [{'store_name': 'Shop', 'price': '12.34'}], **kwargs,
    })
    assert response.status_code == 200, response.text
    return response.json()['game_id']


def preorders(client):
    response = client.get('/get_preorders')
    assert response.status_code == 200, response.text
    return response.json()


def test_add_and_list(api):
    client, _, _ = api
    game_id = add(client)
    add(client, 'Other', offers=[])
    result = preorders(client)
    assert result[0]['game_id'] == game_id
    assert result[0]['offers'][0]['price'] == 12.34
    assert result[1]['offers'] == []


def test_edit_keeps_offers_if_omitted_and_clears_if_explicit(api):
    client, _, _ = api
    game_id = add(client)
    assert client.put('/edit', json={'game_id': game_id, 'title': 'Renamed'}).status_code == 200
    assert preorders(client)[0]['offers'][0]['store_name'] == 'Shop'
    assert client.put('/edit', json={'game_id': game_id, 'offers': []}).status_code == 200
    assert preorders(client)[0]['offers'] == []


def test_invalid_offer_does_not_modify_database(api):
    client, _, _ = api
    game_id = add(client)
    before = preorders(client)
    assert client.put('/edit', json={'game_id': game_id, 'title': 'Bad', 'offers': [None]}).status_code == 422
    assert preorders(client) == before


def test_database_failure_rolls_back_edit(api):
    client, _, _ = api
    game_id = add(client)
    before = preorders(client)
    response = client.put('/edit', json={'game_id': game_id, 'title': 'Bad', 'offers': [{'store_name': 'FAIL_DB', 'price': 1}]})
    assert response.status_code == 500
    assert 'FAIL_DB' not in response.text
    assert preorders(client) == before


def test_database_failure_rolls_back_add(api):
    client, _, _ = api
    response = client.post('/add', json={'title': 'Bad', 'platform': 'PC', 'offers': [{'store_name': 'FAIL_DB', 'price': 1}]})
    assert response.status_code == 500
    assert preorders(client) == []


def test_missing_and_foreign_games_return_404(api):
    client, path, _ = api
    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO games(id,user_id,title,platform) VALUES (99,2,'Foreign','PC')")
    for game_id in (98, 99):
        assert client.request('DELETE', '/delete', json={'game_id': game_id}).status_code == 404
        assert client.put('/edit', json={'game_id': game_id, 'title': 'bad'}).status_code == 404
        assert client.post('/move_to_collection', json={'game_id': game_id}).status_code == 404
        assert client.post('/update_budget', json={'game_id': game_id, 'in_budget': False}).status_code == 404


def test_legacy_reference_and_duplicate_records(api):
    client, path, _ = api
    game_id = add(client)
    assert client.post('/add', json={'title': '  game ', 'platform': 'ps5'}).status_code == 409
    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO games(user_id,title,platform) VALUES (1,' game ','ps5')")
    assert len(preorders(client)) == 2
    assert client.request('DELETE', '/delete', json={'title': 'Game', 'platform': 'PS5'}).status_code == 409
    assert client.request('DELETE', '/delete', json={'game_id': game_id}).status_code == 200
    assert len(preorders(client)) == 1
    assert client.request('DELETE', '/delete', json={'title': 'Game', 'platform': 'PS5'}).status_code == 200


def test_budget_is_strict_boolean(api):
    client, _, _ = api
    game_id = add(client)
    assert client.post('/update_budget', json={'game_id': game_id, 'in_budget': 'false'}).status_code == 422
    assert preorders(client)[0]['in_budget'] is True
    assert client.post('/update_budget', json={'game_id': game_id, 'in_budget': False}).status_code == 200
    assert preorders(client)[0]['in_budget'] is False


def test_move_and_delete_collection(api):
    client, _, _ = api
    game_id = add(client)
    response = client.post('/move_to_collection', json={'game_id': game_id})
    assert response.status_code == 200
    assert preorders(client) == []
    collection = client.get('/get_collection').json()
    assert collection[0]['title'] == 'Game'
    assert client.request('DELETE', '/delete_from_collection', json={'id': collection[0]['id']}).status_code == 200
    assert client.get('/get_collection').json() == []


def test_move_failure_rolls_back(api):
    client, path, _ = api
    game_id = add(client)
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TRIGGER fail_move BEFORE DELETE ON games BEGIN SELECT RAISE(ABORT,'test'); END")
    assert client.post('/move_to_collection', json={'game_id': game_id}).status_code == 500
    assert len(preorders(client)) == 1
    assert client.get('/get_collection').json() == []


def test_password_migration_and_exact_new_password(api):
    client, path, _ = api
    salt = 'a' * 32
    legacy = salt + '$' + hashlib.pbkdf2_hmac('sha256', b'oldpass', salt.encode(), 100000).hex()
    with sqlite3.connect(path) as conn:
        conn.execute('UPDATE users SET password_hash = ? WHERE id = 1', (legacy,))
    assert client.post('/login', data={'username': 'user1', 'password': 'oldpass'}).status_code == 200
    with sqlite3.connect(path) as conn:
        assert conn.execute('SELECT password_hash FROM users WHERE id=1').fetchone()[0].startswith('$argon2id$')
    assert client.post('/register', json={'username':'user3','password':' password '}).status_code == 200
    assert client.post('/login', data={'username':'user3','password':' password '}).status_code == 200
    assert client.post('/login', data={'username':'user3','password':'password'}).status_code == 401
    assert client.post('/register', json={'username':'user3','password':' password '}).status_code == 409


def test_token_validation(api):
    client, _, _ = api
    for payload in ({'sub':'1'}, {'sub':'abc','exp':datetime.now(timezone.utc)+timedelta(hours=1)},
                    {'sub':'1','exp':datetime.now(timezone.utc)-timedelta(hours=1)}):
        token = jwt.encode(payload, main.SECRET_KEY, algorithm=main.ALGORITHM)
        assert client.get('/get_preorders', headers={'Authorization':'Bearer '+token}).status_code == 401


def test_dates_and_cron_dedup(api):
    client, _, telegram = api
    today = datetime.now(main.APP_TIMEZONE).date()
    add(client, 'Exact', release_date=today.isoformat())
    add(client, 'Month only', release_date=today.strftime('%Y-%m'))
    assert client.get('/cron/weekly_summary').status_code == 405
    assert client.post('/cron/weekly_summary').status_code == 401
    assert client.post('/cron/weekly_summary?user_id=2', headers={'X-Cron-Secret':main.CRON_SECRET}).status_code == 403
    headers = {'X-Cron-Secret':main.CRON_SECRET}
    response = client.post('/cron/weekly_summary?user_id=1', headers=headers)
    assert response.status_code == 200
    assert response.json()['sent_games_count'] == 1
    assert 'Exact' in telegram.messages[0]['text']
    assert 'Month only' not in telegram.messages[0]['text']
    assert client.post('/cron/weekly_summary', headers=headers).json()['status'] == 'already_sent'
    assert len(telegram.messages) == 1


def test_cron_timeout_does_not_resend(api):
    client, _, telegram = api
    telegram.fail = True
    headers = {'X-Cron-Secret':main.CRON_SECRET}
    assert client.post('/cron/weekly_summary', headers=headers).status_code == 502
    assert client.post('/cron/weekly_summary', headers=headers).status_code == 409
    assert len(telegram.messages) == 1


def test_bad_input(api):
    client, _, _ = api
    for fields in ({'release_date':'2026-11-24-garbage'}, {'platform':None}, {'offers':[{'store_name':'shop','price':-1}]},
                   {'offers':[{'store_name':'shop','price':1.234}]}, {'offers':[{'store_name':'shop','price':1,'url':'javascript:alert(1)'}]}):
        assert client.post('/add', json={'title':'Game','platform':'PC',**fields}).status_code == 422
    assert preorders(client) == []


def test_libsql_alias_uses_https(api, monkeypatch):
    client, _, _ = api
    monkeypatch.setattr(main, 'DATABASE_URL', 'libsql://test.turso.io')
    assert client.get('/get_preorders').status_code == 200
    assert all(url.startswith('https://') for url, _ in client.db_stub.requests)


def test_http_400_is_not_retried(api):
    client, _, _ = api
    stub = client.db_stub
    stub.fail_next = True
    before = len(stub.requests)
    response = client.post('/login', data={'username': 'user1', 'password': 'not-a-password'})
    assert response.status_code == 500
    assert len(stub.requests) == before + 1


def test_stream_closing_after_begin_does_not_start_new_transaction(api):
    client, path, _ = api
    client.db_stub.close_after_begin = True
    assert client.post('/add', json={'title': 'No write', 'platform': 'PC'}).status_code == 500
    with sqlite3.connect(path) as conn:
        assert conn.execute('SELECT COUNT(*) FROM games').fetchone()[0] == 0


def test_regional_route(api):
    client, _, _ = api
    client.db_stub.route = True
    assert client.get('/get_preorders').status_code == 200
    assert any(url.startswith('https://regional.test.turso.io/') for url, _ in client.db_stub.requests)
