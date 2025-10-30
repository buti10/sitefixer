import mysql.connector
import json
from config import WP_DB_CONFIG
import phpserialize

def parse_name_field(raw_value):
    # Versuch 1: JSON
    try:
        n = json.loads(raw_value)
        if isinstance(n, dict):
            return (n.get('first-name', '') + ' ' + n.get('last-name', '')).strip()
        return str(n)
    except Exception:
        pass
    # Versuch 2: PHP-serialized
    try:
        n = phpserialize.loads(raw_value.encode(), decode_strings=True)
        if isinstance(n, dict):
            return (n.get('first-name', '') + ' ' + n.get('last-name', '')).strip()
        return str(n)
    except Exception:
        pass
    # Fallback: einfach anzeigen
    return raw_value

def get_wp_customers():
    db = mysql.connector.connect(
        host=WP_DB_CONFIG['host'],
        user=WP_DB_CONFIG['user'],
        password=WP_DB_CONFIG['password'],
        database=WP_DB_CONFIG['database']
    )
    cursor = db.cursor(dictionary=True)
    prefix = WP_DB_CONFIG['prefix']

    cursor.execute(f"SELECT entry_id FROM {prefix}frmt_form_entry ORDER BY entry_id DESC")
    entries = cursor.fetchall()
    customers = []

    for e in entries:
        entry_id = int(e['entry_id'])
        cursor.execute(f"SELECT meta_key, meta_value FROM {prefix}frmt_form_entry_meta WHERE entry_id = %s", (entry_id,))
        meta = cursor.fetchall()
        data = {m['meta_key']: m['meta_value'] for m in meta}

        name = ""
        if 'name-1' in data and data['name-1']:
            name = parse_name_field(data['name-1'])

        customers.append({
            'ticket_id': entry_id,
            'name': name,
            'email': data.get('email-1', ''),
            'domain': data.get('url-1', '')
            
        })

    cursor.close()
    db.close()
    return customers

def get_kundendetails(ticket_id):
    db = mysql.connector.connect(
        host=WP_DB_CONFIG['host'],
        user=WP_DB_CONFIG['user'],
        password=WP_DB_CONFIG['password'],
        database=WP_DB_CONFIG['database']
    )
    cursor = db.cursor(dictionary=True)
    prefix = WP_DB_CONFIG['prefix']

    cursor.execute(f"SELECT meta_key, meta_value FROM {prefix}frmt_form_entry_meta WHERE entry_id = %s", (ticket_id,))
    rows = cursor.fetchall()
    data = {r['meta_key']: r['meta_value'] for r in rows}

    cursor.close()
    db.close()
    return {
        'ftp_host': data.get('zugang_ftp_host', ''),
        'ftp_user': data.get('zugang_ftp_user', ''),
        'ftp_pass': data.get('zugang_ftp_pass', ''),
        'domain'  : data.get('url-1', ''),
        'website_user': data.get('zugang_website_user', ''),
        'website_pass': data.get('zugang_website_pass', ''),
        'name': data.get('name-1', ''),
        'email': data.get('email-1', '')
    }

