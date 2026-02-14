# permissions/

Fix module:
- Normalize permissions (chmod) where possible via SFTP
- Prefer preview mode first (show what would change)
- Record changed paths in meta.json for best-effort rollback
