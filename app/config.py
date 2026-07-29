"""Application configuration."""
import os
import uuid

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_env_files() -> None:
    """Load KEY=VALUE from .env / .env.local without requiring python-dotenv."""
    for name in (".env", ".env.local"):
        path = os.path.join(BASE_DIR, name)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                for raw in fh:
                    line = raw.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    if line.startswith("export "):
                        line = line[7:].strip()
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip("'").strip('"')
                    if key and key not in os.environ:
                        os.environ[key] = value
        except OSError:
            pass


_load_env_files()

IS_VERCEL = os.getenv("VERCEL") == "1"
PUBLIC_APP_URL = os.getenv(
    "PUBLIC_APP_URL",
    "https://adm-swh.vercel.app" if IS_VERCEL else "http://localhost:8001",
).rstrip("/")
PUBLIC_LOGIN_URL = f"{PUBLIC_APP_URL}/masuk"

# SECURITY: SECRET_KEY must be set via environment variable in production.
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    if IS_VERCEL:
        raise RuntimeError("SECRET_KEY environment variable is required")
    secret_path = os.path.join(BASE_DIR, ".secret_key")
    try:
        if os.path.isfile(secret_path):
            with open(secret_path, encoding="utf-8") as fh:
                SECRET_KEY = fh.read().strip()
        if not SECRET_KEY:
            SECRET_KEY = f"dev-{uuid.uuid4().hex}"
            with open(secret_path, "w", encoding="utf-8") as fh:
                fh.write(SECRET_KEY)
            print("⚠️  WARNING: Generated local .secret_key for development only.")
            print("   Set SECRET_KEY in environment for production use.")
    except OSError:
        SECRET_KEY = f"dev-{uuid.uuid4().hex}"
        print("⚠️  WARNING: Using ephemeral SECRET_KEY (could not write .secret_key).")

SESSION_COOKIE_NAME = "sppg_session"

UPLOAD_DIR = "/tmp/sppg-uploads" if IS_VERCEL else os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "nota"), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "lampiran"), exist_ok=True)