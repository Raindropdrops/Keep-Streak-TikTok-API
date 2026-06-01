-- SQL DDL to create the contacts table in phpMyAdmin
-- Upload or copy-paste this into the SQL tab of your phpMyAdmin on Tenten hosting.

CREATE TABLE IF NOT EXISTS `tiktok_contacts` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `username` VARCHAR(100) NOT NULL UNIQUE,
  `display_name` VARCHAR(150),
  `aliases` TEXT, -- Stores JSON array of alias strings (e.g. '["Alias 1", "Alias 2"]')
  `profile_url` VARCHAR(255),
  `user_id` VARCHAR(100),
  `sec_uid` VARCHAR(255),
  `conversation_id` VARCHAR(100),
  `last_resolved_at` DATETIME,
  `resolve_confidence` VARCHAR(20) DEFAULT 'low',
  `last_sent` VARCHAR(20),
  `last_sent_at` DATETIME,
  `success_count` INT DEFAULT 0,
  `failure_count` INT DEFAULT 0,
  `enabled` TINYINT(1) DEFAULT 1,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
