# diagnose/

Workflow module:
- Identify WP install details and common failure causes
- Save structured result in customer webspace:
  `<wp_root>/.sitefixer/state/project.json`

Typical outputs:
- wp_root path
- wp-config found/parse status
- WordPress version
- multisite detection
- writable checks (root/wp-content/uploads)
- maintenance mode indicator
