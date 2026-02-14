# wp_repair (Skeleton)

Minimal, modular skeleton for the Sitefixer WordPress Repair Tool.

Principles
- One entry point: `wp_repair.py` (API / orchestrator).
- Each module is self-contained in `modules/<module_name>/`.
- Backups/quarantine live in the **customer webspace**, typically:
  `<wp_root>/.sitefixer/` (fallback to `wp-content/.sitefixer/` if root not writable).
