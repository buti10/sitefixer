# pagespeed.py
import requests
from seo_config import GOOGLE_PAGESPEED_API_KEY

def get_pagespeed(domain):
    url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={domain}&key={GOOGLE_PAGESPEED_API_KEY}&category=PERFORMANCE&category=SEO&category=ACCESSIBILITY&category=BEST_PRACTICES"
    resp = requests.get(url)
    data = resp.json()
    if 'lighthouseResult' not in data:
        return {"error": data.get("error", {}).get("message", "Unbekannter Fehler")}
    lh = data['lighthouseResult']
    categories = lh.get('categories', {})
    result = {
        "performance": round(categories.get('performance', {}).get('score', 0)*100),
        "accessibility": round(categories.get('accessibility', {}).get('score', 0)*100),
        "best_practices": round(categories.get('best-practices', {}).get('score', 0)*100),
        "seo": round(categories.get('seo', {}).get('score', 0)*100),
        "screenshot": None
    }
    try:
        audits = lh.get('audits', {})
        screenshot = audits.get('final-screenshot', {}).get('details', {}).get('data')
        if screenshot:
            result['screenshot'] = screenshot
    except Exception:
        result['screenshot'] = None
    return result
