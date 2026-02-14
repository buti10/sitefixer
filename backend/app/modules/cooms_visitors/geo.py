# app/modules/cooms_visitors/geo.py

from ipaddress import ip_address

reader = None

try:
    # Versuche, geoip2 zu importieren und die Datenbank zu öffnen.
    # Wenn geoip2 nicht installiert ist oder die Datei fehlt, bleibt reader = None
    import geoip2.database  # type: ignore

    try:
        # Pfad ggf. anpassen, falls du die Datei woanders abgelegt hast
        reader = geoip2.database.Reader("/var/www/sitefixer/GeoLite2-City.mmdb")
    except Exception:
        reader = None
except Exception:
    reader = None


def lookup_geo(ip: str):
    """
    Gibt (country_code, city) zurück oder (None, None),
    wenn GeoIP nicht verfügbar oder IP ungültig ist.
    """
    if not reader:
        return None, None

    try:
        ip_address(ip)  # einfache Validierung
        r = reader.city(ip)
        country = r.country.iso_code or None
        city = r.city.name or None
        return country, city
    except Exception:
        return None, None
