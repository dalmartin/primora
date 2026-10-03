"""Where pipeline data lives. Locally: <repo>/data. On Modal: the mounted volume."""
import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("PRIMORA_DATA_DIR", Path(__file__).resolve().parents[3] / "data"))
SIMPLIFY_REPO_URL = "https://github.com/SimplifyJobs/Summer2027-Internships.git"
LISTINGS_PATH = ".github/scripts/listings.json"
