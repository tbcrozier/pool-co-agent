import os, re, time, csv
import requests
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse
from pydantic import BaseModel
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

MAPS_KEY = os.getenv("GOOGLE_MAPS_KEY")
BASE_PLACES = "https://places.googleapis.com/v1"
BASE_HEADERS = {
    "Content-Type": "application/json",
    "X-Goog-Api-Key": MAPS_KEY,
}
RADIUS_METERS = 32187 

class Company(BaseModel):
    company: str
    address: str
    city: str
    state: str
    phone: Optional[str] = ""
    email: Optional[str] = ""
    website: Optional[str] = ""

def geocode_city(city_state: str) -> Tuple[float, float]:
    url = f"{BASE_PLACES}/places:searchText"
    payload = {"textQuery": city_state, "languageCode": "en"}
    headers = {**BASE_HEADERS,
               "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.location"}
    r = requests.post(url, json=payload, headers=headers, timeout=30)
    if r.status_code >= 400:
        print("[places] searchText error:", r.status_code, r.text[:800])
    r.raise_for_status()
    data = r.json()
    place = (data.get("places") or [{}])[0]
    loc = place.get("location") or {}
    return float(loc["latitude"]), float(loc["longitude"])


def search_text_pool_candidates(city_state: str) -> list[str]:
    """
    Use Places searchText to find pool-related businesses for a city/state.
    Returns a list of place IDs (no radius/geocode).
    """
    url = f"{BASE_PLACES}/places:searchText"
    payload = {
        "textQuery": f"pool company OR pool service OR pool contractor in {city_state}",
        "languageCode": "en",
        "maxResultCount": 50
    }
    headers = {**BASE_HEADERS,
               "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.location,places.types"}
    r = requests.post(url, json=payload, headers=headers, timeout=30)
    if r.status_code >= 400:
        print("[places] searchText error:", r.status_code, r.text[:800])
    r.raise_for_status()
    data = r.json()
    return [p["id"] for p in data.get("places", [])]



def place_details(place_id: str) -> Dict:
    url = f"{BASE_PLACES}/places/{place_id}"
    headers = {**BASE_HEADERS,
        "X-Goog-FieldMask": (
            "id,displayName,formattedAddress,addressComponents,"
            "nationalPhoneNumber,internationalPhoneNumber,"
            "websiteUri,googleMapsUri"
        )
    }
    r = requests.get(url, headers=headers, timeout=30)
    if r.status_code >= 400:
        print("[places] details error:", r.status_code, r.text[:800])
    r.raise_for_status()
    return r.json()


def split_city_state(components: List[Dict]) -> Tuple[str, str]:
    city, state = "", ""
    for c in components or []:
        types = c.get("types", [])
        if "locality" in types or "postal_town" in types:
            city = (c.get("longText") or c.get("shortText") or "")
        if "administrative_area_level_1" in types:
            state = (c.get("shortText") or c.get("longText") or "")
    return city, state

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)

def fetch_email_from_site(url: str) -> Optional[str]:
    if not url:
        return None
    # Normalize to homepage
    parsed = urlparse(url)
    if not parsed.scheme:
        url = "https://" + url
    try:
        html = requests.get(url, timeout=15).text
        m = EMAIL_RE.search(html)
        return m.group(0) if m else None
    except Exception:
        return None

def normalize_city_state(s: str) -> tuple[str, str]:
    # very light parser; accepts "City, ST" or "City ST"
    parts = [x.strip() for x in re.split(r"[,\s]+", s) if x.strip()]
    if len(parts) >= 2:
        city = " ".join(parts[:-1])
        state = parts[-1]
        return city.lower(), state.lower()
    return s.lower(), ""  # fallback

def collect_companies(city_state: str) -> List[Company]:
    ids = search_text_pool_candidates(city_state)  # or your existing finder
    out: List[Company] = []
    for pid in ids:
        d = place_details(pid)
        name = ((d.get("displayName") or {}).get("text")) or ""
        addr = d.get("formattedAddress") or ""
        comps = d.get("addressComponents", []) or []
        phone = d.get("nationalPhoneNumber") or d.get("internationalPhoneNumber") or ""
        website = d.get("websiteUri") or d.get("googleMapsUri") or ""
        city, state = split_city_state(comps)

        email = fetch_email_from_site(website) or ""  # still optional
        out.append(Company(
            company=name,
            address=addr,
            city=city,
            state=state,
            phone=phone,
            email=email,
            website=website
        ))
        time.sleep(0.2)
    return out


def save_csv(rows: List[Company], path: str = "pool_companies.csv") -> str:
    cols = ["company", "address", "city", "state", "phone", "email", "website"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r.dict())
    return path
