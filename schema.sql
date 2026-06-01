-- SQL DDL to create the contacts table in Cloudflare D1 (SQLite)
-- Run this in Cloudflare Dashboard > D1 > Console, or via Wrangler CLI:
--   wrangler d1 execute <DB_NAME> --file=schema.sql

CREATE TABLE IF NOT EXISTS tiktok_contacts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE,
  display_name TEXT,
  aliases TEXT DEFAULT '[]',  -- Stores JSON array of alias strings
  profile_url TEXT,
  user_id TEXT,
  sec_uid TEXT,
  conversation_id TEXT,
  last_resolved_at TEXT,
  resolve_confidence TEXT DEFAULT 'low',
  last_sent TEXT,
  last_sent_at TEXT,
  success_count INTEGER DEFAULT 0,
  failure_count INTEGER DEFAULT 0,
  enabled INTEGER DEFAULT 1,
  created_at TEXT DEFAULT (datetime('now'))
);
