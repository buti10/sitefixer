"""Database repair module.

This module relies on WordPress' built-in database repair script:
  /wp-admin/maint/repair.php

wp_repair operates primarily via SFTP and HTTP (no SSH/WP-CLI). Therefore the
recommended approach is:
1) Backup wp-config.php
2) Temporarily enable WP_ALLOW_REPAIR
3) Call the repair endpoint (?repair=1 or ?repair=2)
4) Restore the original wp-config.php
"""

from .preview import db_repair_preview
from .scan import db_repair_scan
from .fix import db_repair_apply

__all__ = ["db_repair_preview", "db_repair_scan", "db_repair_apply"]
