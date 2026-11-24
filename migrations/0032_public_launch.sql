-- Additive migration for Preorder Hub 3.2. Back up and inspect the actual schema first.
-- No changes to the existing games, store_offers, collections or users rows.
CREATE TABLE IF NOT EXISTS public_activity (
    user_id INTEGER PRIMARY KEY,
    last_active TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS public_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('idea', 'bug', 'other')),
    message TEXT NOT NULL CHECK (length(message) BETWEEN 10 AND 2000),
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS public_feedback_user_date ON public_feedback(user_id, created_at);
CREATE TABLE IF NOT EXISTS public_terms_acceptance (
    user_id INTEGER PRIMARY KEY,
    version TEXT NOT NULL,
    accepted_at TEXT NOT NULL
);
-- Never reallocate a retired user ID to a new account: old JWTs may still exist.
-- Contains only the retired numeric ID, no login, hash or game data.
CREATE TABLE IF NOT EXISTS public_retired_users (
    id INTEGER PRIMARY KEY
);
