# core/

Fix module group:
- verify: detect modified core files (optional hash/cached signatures)
- replace: restore clean core files for detected WP version

Safety:
- Never overwrite wp-config.php or wp-content/
- Always quarantine replaced files and record action meta
