CREATE TABLE IF NOT EXISTS repair_run (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  ticket_id INT NOT NULL,
  actor_user_id INT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'running',
  kind VARCHAR(32) NOT NULL DEFAULT 'repair',
  root_path TEXT NULL,
  started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TIMESTAMP NULL,
  summary_json JSON NULL,
  INDEX idx_repair_run_ticket (ticket_id),
  INDEX idx_repair_run_started (started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS repair_action_log (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  run_id BIGINT NOT NULL,
  ticket_id INT NOT NULL,
  action_key VARCHAR(64) NOT NULL,
  status VARCHAR(16) NOT NULL,
  message TEXT NULL,
  details_json JSON NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_repair_action_run (run_id),
  INDEX idx_repair_action_ticket (ticket_id),
  CONSTRAINT fk_repair_action_run FOREIGN KEY (run_id) REFERENCES repair_run(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS repair_artifact (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  run_id BIGINT NOT NULL,
  ticket_id INT NOT NULL,
  type VARCHAR(32) NOT NULL,
  path TEXT NOT NULL,
  sha256 VARCHAR(64) NULL,
  size BIGINT NULL,
  meta_json JSON NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_repair_artifact_run (run_id),
  INDEX idx_repair_artifact_ticket (ticket_id),
  CONSTRAINT fk_repair_artifact_run FOREIGN KEY (run_id) REFERENCES repair_run(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
