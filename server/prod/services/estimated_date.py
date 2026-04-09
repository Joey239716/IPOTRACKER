from .nasdaq_updater import fetch_upcoming, apply_updates
from supabase import create_client
import os
from pathlib import Path
from dotenv import load_dotenv

# Load Supabase client
load_dotenv(dotenv_path=(Path(__file__).resolve().parents[1] / ".env"), override=False)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def upsert_to_supabase():
    data = fetch_upcoming()
    apply_updates(data, apply=True, supabase=supabase)

if __name__ == "__main__":
    upsert_to_supabase()
