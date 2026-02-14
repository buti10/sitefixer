CREATE TABLE IF NOT EXISTS repair_runs (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  ticket_id INT NOT NULL,
  kind VARCHAR(32) NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'running',
  root_path TEXT NULL,
  actor_user_id INT NULL,
  started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at DATETIME NULL,
  summary_json JSON NULL,
  INDEX idx_repair_runs_ticket_started (ticket_id, started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS repair_action_logs (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  run_id BIGINT NOT NULL,
  ticket_id INT NOT NULL,
  action_key VARCHAR(64) NOT NULL,
  status VARCHAR(16) NOT NULL,
  message TEXT NULL,
  details_json JSON NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_repair_action_logs_run (run_id),
  INDEX idx_repair_action_logs_ticket (ticket_id, created_at),
  CONSTRAINT fk_repair_action_logs_run
    FOREIGN KEY (run_id) REFERENCES repair_runs(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS repair_artifacts (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  run_id BIGINT NOT NULL,
  ticket_id INT NOT NULL,
  type VARCHAR(64) NOT NULL,
  path TEXT NOT NULL,
  sha256 VARCHAR(64) NULL,
  size BIGINT NULL,
  meta_json JSON NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_repair_artifacts_run (run_id),
  INDEX idx_repair_artifacts_ticket (ticket_id, created_at),
  CONSTRAINT fk_repair_artifacts_run
    FOREIGN KEY (run_id) REFERENCES repair_runs(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
