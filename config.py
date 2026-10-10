import os
from pathlib import Path

# Chargement du fichier .env
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent / '.env'
    load_dotenv(dotenv_path=env_path, override=True)
except ImportError:
    # Fallback si python-dotenv n'est pas installé
    env_path = Path(__file__).resolve().parent / '.env'
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, val = line.split('=', 1)
                    os.environ[key.strip()] = val.strip().strip('"').strip("'")

# Paramètres du serveur
PORT = int(os.getenv("PORT", 8080))
BASE_URL = os.getenv("BASE_URL", f"http://localhost:{PORT}").rstrip('/')

# Mode développement : affiche le lien d'activation dans la console pour tester facilement
MODE_DEV = os.getenv("MODE_DEV", "True").lower() in ("1", "true", "yes")

# Configuration SMTP (Google Gmail par défaut)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "").strip()
# Nettoyage des espaces éventuels du mot de passe d'application Google (ex: "abcd efgh ijkl mnop")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip().replace(" ", "")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Authentification App")
