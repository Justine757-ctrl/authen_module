from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import logging
import os
import sys
import urllib.parse

# Résolution automatique du dossier racine
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

# Configuration globale du logging (console + fichier app.log)
log_file = os.path.join(BASE_DIR, 'app.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler(log_file, encoding='utf-8'), logging.StreamHandler()],
)

from config import PORT, BASE_URL, MODE_DEV
from database.stockage import (
    ajouter_utilisateur,
    authentifier_utilisateur,
    activer_compte,
    renouveler_token_activation,
)
from noyaux.security import (
    generer_token_session,
    verifier_token_session,
    generer_token_activation,
    valider_format_email,
)
from noyaux.email_service import envoyer_email_activation


def html_page_activation(succes: bool, titre: str, message: str, nom_utilisateur: str = "") -> str:
    """Génère une page web de confirmation d'activation soignée et responsive."""
    couleur = "#198754" if succes else "#dc3545"
    icone = "&#10004;" if succes else "&#10008;"
    
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{titre} - Authentification Sécurisée</title>
  <style>
    body {{
      font-family: system-ui, -apple-system, sans-serif;
      background: #f4f5f7;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      margin: 0;
      color: #212529;
    }}
    .card {{
      background: #ffffff;
      padding: 2.5rem 2rem;
      border-radius: 14px;
      box-shadow: 0 8px 30px rgba(0, 0, 0, 0.08);
      max-width: 440px;
      width: 90%;
      text-align: center;
    }}
    .icon {{
      width: 70px;
      height: 70px;
      border-radius: 50%;
      background: {couleur}15;
      color: {couleur};
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 32px;
      margin: 0 auto 1.5rem auto;
    }}
    h1 {{
      margin: 0 0 0.8rem 0;
      font-size: 1.6rem;
      color: {couleur};
    }}
    p {{
      color: #555;
      line-height: 1.5;
      margin-bottom: 2rem;
    }}
    .btn {{
      display: inline-block;
      background: #6f42c1;
      color: white;
      text-decoration: none;
      padding: 0.8rem 1.8rem;
      border-radius: 8px;
      font-weight: 600;
      transition: background 0.2s;
    }}
    .btn:hover {{
      background: #593196;
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">{icone}</div>
    <h1>{titre}</h1>
    <p>{message}</p>
    <a href="/index.html?activated={'1' if succes else '0'}" class="btn">Se connecter</a>
  </div>
</body>
</html>"""


class AuthentificationRouter(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        """Désactive le formatage de log par défaut de Python pour éviter les doublons."""
        pass

    def _obtenir_infos_client(self) -> str:
        """Récupère l'adresse IP et le navigateur (User-Agent) du client."""
        ip_client = self.client_address[0]
        user_agent = self.headers.get('User-Agent', 'Inconnu')
        return f'IP: {ip_client} | Agent: {user_agent}'

    def _envoyer_reponse_json(self, statut: int, donnees: dict):
        try:
            corps = json.dumps(donnees, ensure_ascii=False).encode('utf-8')
            self.send_response(statut)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(corps)))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header(
                'Access-Control-Allow-Headers', 'Content-Type, Authorization'
            )
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.end_headers()
            self.wfile.write(corps)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass

    def _envoyer_reponse_html(self, statut: int, html_contenu: str):
        try:
            corps = html_contenu.encode('utf-8')
            self.send_response(statut)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(corps)))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(corps)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header(
            'Access-Control-Allow-Headers', 'Content-Type, Authorization'
        )
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_POST(self):
        infos_client = self._obtenir_infos_client()
        longueur_contenu = int(self.headers.get('Content-Length', 0))
        corps_brut = self.rfile.read(longueur_contenu)

        try:
            donnees = json.loads(corps_brut.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            logging.warning(f'ÉCHEC PARSING JSON [{infos_client}]')
            self._envoyer_reponse_json(400, {'erreur': 'Données JSON invalides.'})
            return

        # Route /register
        if self.path == '/register':
            nom = donnees.get('nom_utilisateur', '').strip()
            email = donnees.get('email', '').strip().lower()
            mdp = donnees.get('mot_de_passe', '')

            if not nom:
                self._envoyer_reponse_json(400, {'erreur': "Le nom d'utilisateur est requis."})
                return
            if not email:
                self._envoyer_reponse_json(400, {'erreur': "L'adresse email est requise pour l'activation."})
                return
            if not valider_format_email(email):
                self._envoyer_reponse_json(400, {'erreur': "Format d'adresse email invalide."})
                return
            if not mdp or len(mdp) < 6:
                self._envoyer_reponse_json(400, {'erreur': "Le mot de passe doit comporter au moins 6 caractères."})
                return

            # Génération d'un jeton unique d'activation
            token_activation = generer_token_activation()

            # Enregistrement dans la base de données (inactif par défaut)
            succes, msg_bdd = ajouter_utilisateur(nom, email, mdp, token_activation)
            if not succes:
                logging.warning(f"ÉCHEC INSCRIPTION [{infos_client}] : {msg_bdd}")
                self._envoyer_reponse_json(400, {'erreur': msg_bdd})
                return

            # Envoi de l'email d'activation avec Google SMTP
            succes_mail, msg_mail = envoyer_email_activation(email, nom, token_activation)

            logging.info(f"INSCRIPTION : User '{nom}' ({email}) créé. Statut email : {msg_mail} [{infos_client}]")

            self._envoyer_reponse_json(201, {
                'message': (
                    "Compte créé avec succès ! Un email d'activation a été envoyé à votre adresse. "
                    "Veuillez cliquer sur le lien pour activer votre compte."
                ),
                'email': email,
                'email_envoye': succes_mail,
                'details': msg_mail
            })

        # Route /login
        elif self.path == '/login':
            identifiant = donnees.get('nom_utilisateur') or donnees.get('identifiant', '')
            mdp = donnees.get('mot_de_passe', '')

            statut, nom_reel = authentifier_utilisateur(identifiant, mdp)

            if statut == "SUCCES":
                token = generer_token_session(nom_reel)
                logging.info(f"CONNEXION RÉUSSIE : User '{nom_reel}' [{infos_client}]")
                self._envoyer_reponse_json(200, {
                    'token': token,
                    'nom_utilisateur': nom_reel,
                    'message': 'Connexion réussie.'
                })

            elif statut == "NON_ACTIVE":
                logging.warning(f"CONNEXION REFUSÉE (COMPTE NON ACTIVÉ) : '{identifiant}' [{infos_client}]")
                self._envoyer_reponse_json(403, {
                    'erreur': "Votre compte n'est pas encore activé. Veuillez cliquer sur le lien reçu par email.",
                    'inactif': True,
                    'identifiant': identifiant
                })

            else:
                logging.warning(f"ÉCHEC CONNEXION : Identifiants faux pour '{identifiant}' [{infos_client}]")
                self._envoyer_reponse_json(401, {'erreur': 'Identifiants invalides.'})

        # Route /resend-activation (renvoi du mail d'activation)
        elif self.path == '/resend-activation':
            identifiant = donnees.get('identifiant') or donnees.get('email') or donnees.get('nom_utilisateur', '')
            if not identifiant:
                self._envoyer_reponse_json(400, {'erreur': "L'identifiant ou l'email est requis."})
                return

            nouveau_token = generer_token_activation()
            succes, msg_bd, email_dest, nom_user = renouveler_token_activation(identifiant, nouveau_token)

            if not succes:
                self._envoyer_reponse_json(400, {'erreur': msg_bd})
                return

            succes_mail, msg_mail = envoyer_email_activation(email_dest, nom_user, nouveau_token)
            logging.info(f"RENVOI EMAIL ACTIVATION pour '{nom_user}' ({email_dest}) : {msg_mail} [{infos_client}]")

            self._envoyer_reponse_json(200, {
                'message': f"Un nouvel email d'activation a été envoyé à {email_dest}.",
                'email': email_dest,
                'email_envoye': succes_mail
            })

        else:
            logging.error(f'ROUTE INCONNUE : {self.command} {self.path} [{infos_client}]')
            self._envoyer_reponse_json(404, {'erreur': 'Route introuvable.'})

    def do_GET(self):
        infos_client = self._obtenir_infos_client()
        url_decoupee = urllib.parse.urlparse(self.path)
        chemin = url_decoupee.path

        # Route /activate?token=...
        if chemin == '/activate':
            parametres = urllib.parse.parse_qs(url_decoupee.query)
            token = parametres.get('token', [''])[0]

            succes, message, nom_user = activer_compte(token)

            if succes:
                logging.info(f"ACTIVATION RÉUSSIE : User '{nom_user}' [{infos_client}]")
                html = html_page_activation(
                    succes=True,
                    titre="Compte activé !",
                    message=f"Félicitations <strong>{nom_user or ''}</strong> ! Votre adresse email a été vérifiée et votre compte est désormais actif. Vous pouvez maintenant vous connecter en toute sécurité.",
                    nom_utilisateur=nom_user or ""
                )
                self._envoyer_reponse_html(200, html)
            else:
                logging.warning(f"ÉCHEC ACTIVATION (token invalide/expiré) [{infos_client}] : {message}")
                html = html_page_activation(
                    succes=False,
                    titre="Lien invalide ou expiré",
                    message="Ce lien d'activation est invalide ou a déjà été utilisé. Si votre compte n'est pas encore actif, vous pouvez demander un nouveau lien depuis la page de connexion."
                )
                self._envoyer_reponse_html(400, html)

        # Route /profile (protégée)
        elif chemin == '/profile':
            auth_header = self.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                logging.warning(f'ACCÈS REFUSÉ /profile : Token manquant [{infos_client}]')
                self._envoyer_reponse_json(401, {'erreur': 'Token manquant ou format incorrect.'})
                return

            token = auth_header.split(' ')[1]
            nom = verifier_token_session(token)

            if nom:
                logging.info(f"ACCÈS PROFIL AUTORISÉ : User '{nom}' [{infos_client}]")
                self._envoyer_reponse_json(200, {'message': f'Bienvenue sur votre profil, {nom} !'})
            else:
                logging.warning(f'ACCÈS REFUSÉ /profile : Token invalide [{infos_client}]')
                self._envoyer_reponse_json(401, {'erreur': 'Token invalide ou expiré.'})

        # Servir index.html sur / ou /index.html
        elif chemin in ('/', '/index.html'):
            chemin_index = os.path.join(BASE_DIR, 'index.html')
            if os.path.exists(chemin_index):
                with open(chemin_index, 'r', encoding='utf-8') as f:
                    contenu = f.read()
                self._envoyer_reponse_html(200, contenu)
            else:
                self._envoyer_reponse_json(404, {'erreur': 'Fichier index.html introuvable.'})

        else:
            logging.error(f'ROUTE INCONNUE : {self.command} {self.path} [{infos_client}]')
            self._envoyer_reponse_json(404, {'erreur': 'Route introuvable.'})


class ServeurAuthentification(HTTPServer):
    allow_reuse_address = True


if __name__ == '__main__':
    logging.info(f'Démarrage du serveur d\'authentification sur http://localhost:{PORT}')
    serveur = ServeurAuthentification(('0.0.0.0', PORT), AuthentificationRouter)
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        logging.info('Arrêt du serveur.')
        serveur.server_close()