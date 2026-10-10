import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import sys
import os
from pathlib import Path


def obtenir_config():
    """Charge dynamiquement la configuration la plus à jour depuis le fichier .env."""
    try:
        from dotenv import load_dotenv
        env_path = Path(__file__).resolve().parent.parent / '.env'
        load_dotenv(dotenv_path=env_path, override=True)
    except ImportError:
        pass

    host = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
    port = int(os.getenv("SMTP_PORT", 587))
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip().replace(" ", "")
    from_name = os.getenv("SMTP_FROM_NAME", "Authentification Sécurisée").strip().strip('"')
    base_url = os.getenv("BASE_URL", "http://localhost:8080").rstrip('/')
    mode_dev = os.getenv("MODE_DEV", "True").lower() in ("1", "true", "yes")

    return host, port, user, password, from_name, base_url, mode_dev


def creer_message_html(nom_utilisateur: str, lien_activation: str) -> str:
    """Génère le corps HTML stylisé du message d'activation."""
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <style>
    body {{
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      background-color: #f4f5f7;
      margin: 0;
      padding: 20px;
    }}
    .email-card {{
      max-width: 550px;
      margin: 0 auto;
      background-color: #ffffff;
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 4px 15px rgba(0, 0, 0, 0.08);
      border: 1px solid #e1e4e8;
    }}
    .header {{
      background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
      padding: 30px 20px;
      text-align: center;
      color: #ffffff;
    }}
    .header h1 {{
      margin: 0;
      font-size: 24px;
      letter-spacing: 0.5px;
    }}
    .body {{
      padding: 35px 30px;
      color: #333333;
      line-height: 1.6;
    }}
    .greeting {{
      font-size: 18px;
      font-weight: 600;
      margin-bottom: 15px;
      color: #212529;
    }}
    .btn-container {{
      text-align: center;
      margin: 30px 0;
    }}
    .btn {{
      display: inline-block;
      background: #6366f1;
      color: #ffffff !important;
      text-decoration: none;
      padding: 14px 32px;
      border-radius: 8px;
      font-weight: bold;
      font-size: 16px;
      box-shadow: 0 4px 10px rgba(99, 102, 241, 0.35);
    }}
    .link-fallback {{
      background-color: #f8f9fa;
      border: 1px dashed #ced4da;
      padding: 12px;
      border-radius: 6px;
      word-break: break-all;
      font-size: 13px;
      color: #495057;
      margin-top: 20px;
    }}
    .footer {{
      background-color: #f8f9fa;
      padding: 20px 30px;
      text-align: center;
      font-size: 12px;
      color: #6c757d;
      border-top: 1px solid #e9ecef;
    }}
  </style>
</head>
<body>
  <div class="email-card">
    <div class="header">
      <h1>Activation de votre compte</h1>
    </div>
    <div class="body">
      <div class="greeting">Bonjour {nom_utilisateur},</div>
      <p>Merci pour votre inscription ! Pour finaliser la création de votre compte et vérifier votre adresse email, veuillez cliquer sur le bouton ci-dessous :</p>
      
      <div class="btn-container">
        <a href="{lien_activation}" class="btn" target="_blank">Activer mon compte</a>
      </div>
      
      <p style="font-size: 14px; color: #555;">Si le bouton ne fonctionne pas, vous pouvez copier et coller ce lien dans votre navigateur :</p>
      <div class="link-fallback">
        <a href="{lien_activation}" style="color: #6366f1;">{lien_activation}</a>
      </div>
    </div>
    <div class="footer">
      <p>Ce lien est valable pendant 24 heures. Si vous n'êtes pas à l'origine de cette demande, vous pouvez ignorer cet email.</p>
      <p>&copy; 2026 Authentification Sécurisée - Tous droits réservés.</p>
    </div>
  </div>
</body>
</html>"""


def creer_message_texte(nom_utilisateur: str, lien_activation: str) -> str:
    """Génère le corps texte brut alternatif."""
    return f"""Bonjour {nom_utilisateur},

Merci pour votre inscription !

Pour activer votre compte, veuillez ouvrir le lien suivant dans votre navigateur :
{lien_activation}

Ce lien est valable pendant 24 heures.
Si vous n'êtes pas à l'origine de cette demande, veuillez ignorer cet email.

---
Authentification Sécurisée
"""


def _tenter_envoi_smtp(host: str, port: int, user: str, password: str, destinataire: str, msg_str: str):
    """Effectue l'envoi SMTP avec gestion de port 465 (SSL) ou 587 (STARTTLS)."""
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=15) as s:
            s.login(user, password)
            s.sendmail(user, [destinataire], msg_str)
    else:
        with smtplib.SMTP(host, port, timeout=15) as s:
            s.ehlo()
            s.starttls()
            s.ehlo()
            s.login(user, password)
            s.sendmail(user, [destinataire], msg_str)


def envoyer_email_activation(
    destinataire_email: str, nom_utilisateur: str, token_activation: str
) -> tuple[bool, str]:
    """
    Envoie un email d'activation contenant un lien sécurisé via Google SMTP.
    Supporte le basculement automatique STARTTLS (587) / SSL (465) en cas de blocage réseau.
    
    Retourne (succès: bool, message: str)
    """
    host, port, user, password, from_name, base_url, mode_dev = obtenir_config()
    lien_activation = f"{base_url}/activate?token={token_activation}"

    # Log en console en mode DEV
    if mode_dev:
        logging.info("\n" + "=" * 70)
        logging.info("[DEVELOPPEMENT] EMAIL D'ACTIVATION")
        logging.info(f"Destinataire : {destinataire_email} (User: '{nom_utilisateur}')")
        logging.info(f"Lien direct  : {lien_activation}")
        logging.info("=" * 70 + "\n")

    if not user or not password:
        msg = f"Identifiants SMTP manquants dans .env. Lien direct : {lien_activation}"
        logging.warning(msg)
        if mode_dev:
            return True, "Email simulé (identifiants SMTP non configurés)."
        return False, "Identifiants SMTP non configurés."

    # Construction du message MIME
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Activez votre compte - Authentification Sécurisée"
    msg["From"] = f"{from_name} <{user}>"
    msg["To"] = destinataire_email

    texte_part = MIMEText(creer_message_texte(nom_utilisateur, lien_activation), "plain", "utf-8")
    html_part = MIMEText(creer_message_html(nom_utilisateur, lien_activation), "html", "utf-8")
    msg.attach(texte_part)
    msg.attach(html_part)
    msg_str = msg.as_string()

    # Tentative d'envoi principale
    try:
        logging.info(f"Connexion au serveur SMTP {host}:{port}...")
        _tenter_envoi_smtp(host, port, user, password, destinataire_email, msg_str)
        logging.info(f"EMAIL ENVOYÉ AVEC SUCCÈS à {destinataire_email} via Google SMTP (Port {port}) !")
        return True, "Email d'activation envoyé avec succès."

    except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, ConnectionResetError, TimeoutError, OSError) as e:
        # Basculement intelligent vers le port alternatif (465 SSL ou 587 TLS)
        port_alternatif = 465 if port != 465 else 587
        logging.warning(f"Port {port} indisponible ({e}). Tentative de secours sur le port {port_alternatif}...")
        try:
            _tenter_envoi_smtp(host, port_alternatif, user, password, destinataire_email, msg_str)
            logging.info(f"EMAIL ENVOYÉ AVEC SUCCÈS à {destinataire_email} via port de secours {port_alternatif} !")
            return True, "Email d'activation envoyé avec succès."
        except Exception as e_secours:
            logging.error(f"Échec sur le port de secours {port_alternatif} : {e_secours}")
            if mode_dev:
                return True, f"Erreur réseau SMTP. Lien de test : {lien_activation}"
            return False, f"Impossible de joindre le serveur SMTP ({e_secours})"

    except smtplib.SMTPAuthenticationError as e:
        erreur_diag = (
            "ÉCHEC D'AUTHENTIFICATION GOOGLE (Erreur 535 / 534) :\n"
            "Google a refusé la connexion. Vérifiez que :\n"
            "1. La 'Validation en deux étapes' (2FA) est bien active sur votre compte Google.\n"
            "2. Vous utilisez le 'Mot de passe d'application' de 16 caractères généré sur "
            "https://myaccount.google.com/apppasswords et non votre mot de passe usuel."
        )
        logging.error(erreur_diag)
        if mode_dev:
            return True, f"Google a rejeté le mot de passe SMTP. Lien de test : {lien_activation}"
        return False, "Authentification Google refusée. Mot de passe d'application requis."

    except Exception as e:
        logging.error(f"Erreur inattendue envoi email : {e}")
        if mode_dev:
            return True, f"Erreur envoi email ({e}). Lien de test : {lien_activation}"
        return False, str(e)
