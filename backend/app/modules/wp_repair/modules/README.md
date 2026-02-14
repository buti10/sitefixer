# modules/

Each folder is one module (workflow or fix).

Rules
- Keep modules self-contained: module code + its assets live together.
- Shared state should be written into customer webspace:
  `<wp_root>/.sitefixer/state/project.json`
- Actions that change files should write rollback info into:
  `<wp_root>/.sitefixer/quarantine/actions/<timestamp>_<fix-id>/meta.json`
