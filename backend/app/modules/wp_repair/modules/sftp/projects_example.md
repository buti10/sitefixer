## Typical project roots (examples)

Common hosting folder names you can scan:
- /httpdocs
- /htdocs
- /public_html
- /www
- /home/<user>/public_html
- /clickandbuilds/* (Plesk 1-click installers)

projects.py should return a normalized list for the frontend:
- label: "/clickandbuilds/MySite"
- root_path: "/clickandbuilds/MySite"
