import os

# Set fake env vars BEFORE any server package imports.
# config.py calls settings.validate() at import time, so these must exist
# or every test module will crash on collection with RuntimeError.
os.environ.setdefault("SUPABASE_URL", "https://fake.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "fake-service-role-key")
os.environ.setdefault("LOGO_DEV_KEY", "fake-logo-dev-key")
os.environ.setdefault("LOGO_NAME_SALT", "fake-salt")
os.environ.setdefault("SEC_USER_AGENT", "Test Suite test@example.com")
os.environ.setdefault("OPENROUTER_API_KEY", "fake-openrouter-key")
