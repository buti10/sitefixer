# scan_patterns.py
MALWARE_PATTERNS = [
    # Rot: Kritisch, Orange: Mittel, Gruen: Info
    {'regex': r'eval\s*\(', 'level': 'rot', 'desc': 'eval()-Funktion'},
    {'regex': r'base64_decode\s*\(', 'level': 'orange', 'desc': 'base64_decode'},
    {'regex': r'system\s*\(', 'level': 'rot', 'desc': 'system()-Funktion'},
    {'regex': r'gzinflate\s*\(', 'level': 'orange', 'desc': 'gzinflate'},
    {'regex': r'passthru\s*\(', 'level': 'rot', 'desc': 'passthru()-Funktion'},
    {'regex': r'phpinfo\s*\(', 'level': 'gruen', 'desc': 'phpinfo()-Funktion'},
]
