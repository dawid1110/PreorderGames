-- Apply once before enabling the Telegram cron. No existing records are modified.
CREATE TABLE IF NOT EXISTS weekly_summary_runs (
    user_id INTEGER NOT NULL,
    week_start TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('sending', 'sent', 'uncertain')),
    PRIMARY KEY (user_id, week_start)
);
