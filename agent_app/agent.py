# agent_app/agent.py
from typing import List, Dict, Any
from google.adk.agents import Agent
from pathlib import Path
import re

from .tools import collect_companies, save_csv

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(exist_ok=True)

def _safe_filename(city_state: str) -> str:
    """
    Convert 'City, ST' into a safe lowercase filename fragment.
    Example: 'Boston, MA' -> 'boston_ma'
    """
    name = city_state.strip().lower()
    name = re.sub(r"[^a-z0-9]+", "_", name)
    return name.strip("_")

# ---------- Tool wrappers ----------

def find_pool_companies(city_state: str) -> Dict[str, Any]:
    """
    Given 'City, ST', return a list of company dicts with contact info.
    """
    rows = collect_companies(city_state)
    return {
        "status": "success",
        "count": len(rows),
        "results": [r.dict() for r in rows],
    }

def write_csv(rows: List[Dict[str, Any]], city_state: str) -> Dict[str, Any]:
    """
    Save a list of company dicts to CSV in data/ with city name in file name.
    """
    filename = f"{_safe_filename(city_state)}_pool_companies.csv"
    path = DATA_DIR / filename

    # Shim so save_csv accepts this list
    class _RowShim:
        def __init__(self, d: Dict[str, Any]): self._d = d
        def dict(self) -> Dict[str, Any]: return self._d

    shimmed = [_RowShim(r) for r in rows]
    save_csv(shimmed, str(path))
    return {"status": "success", "path": str(path), "count": len(rows)}

def find_and_save(city_state: str) -> Dict[str, Any]:
    """
    Do both steps: find companies and write CSV.
    """
    rows = collect_companies(city_state)
    filename = f"{_safe_filename(city_state)}_pool_companies.csv"
    path = DATA_DIR / filename
    save_csv(rows, str(path))
    return {
        "status": "success",
        "path": str(path),
        "count": len(rows),
        "city_state": city_state,
    }

# ---------- Root agent ----------
root_agent = Agent(
    name="pool_company_finder",
    model="gemini-2.0-flash",
    description="Finds pool companies for a given city/state and exports them to CSV.",
    instruction=(
        "Ask for a U.S. city and state like 'Boston, MA'. "
        "Then either:\n"
        " - Call find_pool_companies(city_state) and pass its 'results' to write_csv(rows, city_state), or\n"
        " - Call find_and_save(city_state) to do it in one shot.\n"
        "The CSV will be saved in the data/ folder with the city in its filename."
    ),
    tools=[find_pool_companies, write_csv, find_and_save],
)
