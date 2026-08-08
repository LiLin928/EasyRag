import os
# Fallbacks for required settings if .env absent during test collection.
# DATABASE_URL is provided by backend/.env (VM); do NOT override here.
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("INIT_ADMIN_PASSWORD", "pw12345")
