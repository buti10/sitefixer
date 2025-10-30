-- Schema: Repair-Grundgerüst
-- Engine/Charset
SET NAMES utf8mb4;
SET time_zone = '+00:00';

CREATE TABLE IF NOT EXISTS repair_sessions (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  ticket_id    INT NOT NULL,
  sid          VARCHAR(64)  NOT NULL,                 -- SFTP-Session-ID
  root         VARCHAR(1024) NOT NULL,                -- gewähltes Webroot (Remote-Pfad)
  cms          VARCHAR(32)  NULL,                     -- z.B. wordpress|joomla|shopware|php
  cms_version  VARCHAR(32)  NULL,
  created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  closed_at    DATETIME NULL,
  INDEX idx_repair_sessions_ticket (ticket_id),
  INDEX idx_repair_sessions_sid (sid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS repair_actions (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  session_id   INT NOT NULL,
  kind         VARCHAR(40) NOT NULL,                  -- move|replace|delete|chmod|patch|config_fix
  src          VARCHAR(2048) NULL,                    -- Originalpfad
  dst          VARCHAR(2048) NULL,                    -- Ziel/Quarantäne/Neu
  meta         JSON NULL,                             -- {hash_old,hash_new,reason,rule_id,...}
  success      TINYINT(1) NOT NULL DEFAULT 0,
  error_msg    TEXT NULL,
  executed_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_actions_session (session_id),
  CONSTRAINT fk_actions_session
    FOREIGN KEY (session_id) REFERENCES repair_sessions(id)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS repair_checkpoints (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  session_id    INT NOT NULL,
  label         VARCHAR(80) NOT NULL,                 -- z.B. 'pre-core-replace'
  snapshot_dir  VARCHAR(2048) NOT NULL,               -- Ablage Quarantäne/Snapshot
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_checkpoints_session (session_id),
  CONSTRAINT fk_checkpoints_session
    FOREIGN KEY (session_id) REFERENCES repair_sessions(id)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Optionale Log-Tabelle für freie Textlogs je Session/Step
CREATE TABLE IF NOT EXISTS repair_logs (
  id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  session_id   INT NOT NULL,
  level        ENUM('DEBUG','INFO','WARN','ERROR') NOT NULL DEFAULT 'INFO',
  message      TEXT NOT NULL,
  context      JSON NULL,                              -- beliebige Zusatzdaten
  created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_logs_session (session_id),
  CONSTRAINT fk_logs_session
    FOREIGN KEY (session_id) REFERENCES repair_sessions(id)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
