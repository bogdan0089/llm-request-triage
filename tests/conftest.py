import os

# Settings requires GEMINI_API_KEY at import time. Tests never call the API,
# so a placeholder keeps the suite runnable on a fresh clone with no .env.
os.environ.setdefault("GEMINI_API_KEY", "test-key-unused")
