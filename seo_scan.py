PAGESPEED_API_KEY = "AIzaSyCIGRgS1Ii2ynga5sUyQ3CjUMAqIA0LIx8"
import requests
from bs4 import BeautifulSoup
import re


def run_seo_scan(domain):
    url = domain if domain.startswith("http") else "http://" + domain
    results = {
        "domain": domain,
        "status_code": None,
        "ssl": False,
        "load_time": "-",
        "title": "",
        "meta_description": "",
        "h1": [],
        "h2": [],
        "word_count": 0,
        "robots_txt": "",
        "indexable": False,
        "canonical": "",
        "sitemap": "",
        "favicon": "",
        "img_count": 0,
        "img_missing_alt": 0,
        "internal_links": [],
        "external_links": [],
        "broken_external_links": [],
        "mobile_friendly": False,
        "structured_data": False,
        "open_graph": False,
        "twitter_card": False,
        "warnings": [],
        "errors": [],
        "recommendations": [],
    }
    try:
        resp = requests.get(url, timeout=8)
        results["status_code"] = resp.status_code
        results["ssl"] = url.startswith("https")
        html = resp.text
        soup = BeautifulSoup(html, "html.parser")
        # Title
        title = soup.title.string.strip() if soup.title else ""
        results["title"] = title
        if not title:
            results["recommendations"].append("Fehlender <title> Tag – Title dringend setzen.")
        # Meta-Description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        meta_desc = meta_desc["content"].strip() if meta_desc and "content" in meta_desc.attrs else ""
        results["meta_description"] = meta_desc
        if not meta_desc:
            results["recommendations"].append("Meta-Description fehlt – für bessere CTR dringend anlegen.")
        # H1/H2
        h1 = [h.get_text().strip() for h in soup.find_all("h1")]
        results["h1"] = h1
        if len(h1) == 0:
            results["recommendations"].append("Keine H1-Überschrift gefunden – wichtig für SEO.")
        elif len(h1) > 1:
            results["warnings"].append("Mehrere H1-Tags – ideal nur 1x pro Seite.")
        results["h2"] = [h.get_text().strip() for h in soup.find_all("h2")]
        # Wortanzahl
        text = soup.get_text(separator=" ").strip()
        word_count = len(text.split())
        results["word_count"] = word_count
        if word_count < 150:
            results["warnings"].append("Wenig Text – mindestens 200+ Wörter pro Seite empfohlen.")
        # Canonical
        canonical = soup.find("link", rel="canonical")
        results["canonical"] = canonical["href"] if canonical and "href" in canonical.attrs else ""
        # Robots.txt
        robots_url = url.rstrip("/") + "/robots.txt"
        try:
            robots_resp = requests.get(robots_url, timeout=3)
            robots_txt = robots_resp.text if robots_resp.status_code == 200 else ""
            results["robots_txt"] = robots_txt[:300]
            results["indexable"] = "noindex" not in robots_txt.lower()
            if "noindex" in robots_txt.lower():
                results["warnings"].append("Achtung: 'noindex' in robots.txt – Seite wird nicht gelistet!")
        except:
            results["warnings"].append("Robots.txt nicht auffindbar – Suchmaschinen könnten Probleme haben.")
        # Sitemap
        sitemap = re.search(r"Sitemap:\s*(.+)", results["robots_txt"])
        results["sitemap"] = sitemap.group(1) if sitemap else ""
        # Favicon
        icon = soup.find("link", rel=lambda x: x and "icon" in x)
        results["favicon"] = icon["href"] if icon and "href" in icon.attrs else ""
        # Bilder mit/ohne ALT
        images = soup.find_all("img")
        results["img_count"] = len(images)
        results["img_missing_alt"] = sum(1 for img in images if not img.get("alt"))
        if results["img_missing_alt"]:
            results["recommendations"].append(f"{results['img_missing_alt']} Bilder ohne ALT-Text – immer beschreiben!")
        # Links
        links = soup.find_all("a", href=True)
        for l in links:
            href = l["href"]
            if href.startswith("http"):
                if domain in href or href.startswith(url):
                    results["internal_links"].append(href)
                else:
                    results["external_links"].append(href)
            elif href.startswith("/"):
                results["internal_links"].append(href)
        # Broken Links
        broken = []
        for l in results["external_links"][:8]:  # Maximal 8 für Speed!
            try:
                check = requests.head(l, timeout=4)
                if check.status_code >= 400:
                    broken.append(l)
            except Exception:
                broken.append(l)
        results["broken_external_links"] = broken
        if broken:
            results["warnings"].append(f"{len(broken)} defekte externe Links gefunden – prüfen!")
        # Mobile-friendliness
        viewport = soup.find("meta", attrs={"name": "viewport"})
        results["mobile_friendly"] = bool(viewport)
        if not results["mobile_friendly"]:
            results["recommendations"].append("Keine 'viewport' Meta-Tag – Seite ist nicht mobilfreundlich!")
        # Structured Data
        structured = soup.find_all("script", type="application/ld+json")
        results["structured_data"] = len(structured) > 0
    except Exception as e:
        results["errors"].append(str(e))
    return results

def get_pagespeed_insights(domain, api_key):
    import requests
    results = {}
    for strategy in ['desktop', 'mobile']:
        url = (
            "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
            f"?url={domain}&strategy={strategy}&key={api_key}"
        )
        try:
            resp = requests.get(url, timeout=20)
            data = resp.json()
            lhr = data.get('lighthouseResult', {})
            categories = lhr.get('categories', {})
            audits = lhr.get('audits', {})
            results[strategy] = {
                'performance': int(categories.get('performance', {}).get('score', 0) * 100) if categories.get('performance') else None,
                'seo': int(categories.get('seo', {}).get('score', 0) * 100) if categories.get('seo') else None,
                'best_practices': int(categories.get('best-practices', {}).get('score', 0) * 100) if categories.get('best-practices') else None,
                'accessibility': int(categories.get('accessibility', {}).get('score', 0) * 100) if categories.get('accessibility') else None,
                'screenshot': audits.get('final-screenshot', {}).get('details', {}).get('data', None),
                'metrics': {k: audits[k].get('displayValue') for k in [
                    'first-contentful-paint', 'speed-index', 'largest-contentful-paint',
                    'total-blocking-time', 'cumulative-layout-shift'] if k in audits}
            }
        except Exception as e:
            results[strategy] = {'error': str(e)}
    return results
