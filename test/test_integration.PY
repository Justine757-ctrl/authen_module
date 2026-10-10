import json
import urllib.error
import urllib.request
import sqlite3
import os
import sys
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from config import PORT, BASE_URL
from database.stockage import DB_FILE


def faire_requete(
    url: str,
    methode: str = 'GET',
    donnees: dict = None,
    headers: dict = None,
) -> tuple[int, dict | str]:
    """Helper pour effectuer des requêtes HTTP sans paquets externes."""
    if headers is None:
        headers = {}

    body = json.dumps(donnees).encode('utf-8') if donnees else None
    if body:
        headers['Content-Type'] = 'application/json'

    req = urllib.request.Request(
        url, data=body, headers=headers, method=methode
    )

    try:
        with urllib.request.urlopen(req) as reponse:
            ctype = reponse.headers.get('Content-Type', '')
            contenu = reponse.read().decode('utf-8')
            if 'application/json' in ctype:
                return reponse.status, json.loads(contenu)
            return reponse.status, contenu
    except urllib.error.HTTPError as e:
        ctype = e.headers.get('Content-Type', '')
        contenu = e.read().decode('utf-8')
        if 'application/json' in ctype:
            try:
                return e.code, json.loads(contenu)
            except Exception:
                return e.code, contenu
        return e.code, contenu


def executer_flux_integration():
    print('=== FLUX INTEGRATION COMPLET (ACTIVATION PAR EMAIL) ===\n')

    # Identifiant unique pour ce test
    timestamp_test = int(time.time())
    pseudo = f'user_test_{timestamp_test}'
    email = f'test_{timestamp_test}@example.com'
    mot_de_passe = 'MonMotDePasse2026!'

    # 1. Tentative d'accès à /profile sans token (Doit échouer 401)
    statut, corps = faire_requete(f'{BASE_URL}/profile')
    print(f'[TEST 1] Accès /profile anonyme -> Statut: {statut}')
    assert statut == 401, f"Attendu 401, obtenu {statut}"

    # 2. Inscription d'un nouvel utilisateur avec email
    payload_user = {
        'nom_utilisateur': pseudo,
        'email': email,
        'mot_de_passe': mot_de_passe,
    }
    statut, corps = faire_requete(
        f'{BASE_URL}/register', methode='POST', donnees=payload_user
    )
    print(f'[TEST 2] Inscription -> Statut: {statut} | Message: {corps.get("message")}')
    assert statut == 201, f"Attendu 201, obtenu {statut}"

    # 3. Tentative de connexion AVANT activation (Doit échouer 403 - Compte inactif)
    payload_login = {
        'nom_utilisateur': pseudo,
        'mot_de_passe': mot_de_passe,
    }
    statut, corps = faire_requete(
        f'{BASE_URL}/login', methode='POST', donnees=payload_login
    )
    print(f'[TEST 3] Connexion avant activation -> Statut: {statut} | Réponse: {corps}')
    assert statut == 403, f"Attendu 403, obtenu {statut}"
    assert corps.get('inactif') is True, "Le compte devrait être marqué inactif"

    # 4. Récupération du jeton d'activation dans la BDD pour simuler le clic sur l'email
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT token_activation FROM utilisateurs WHERE nom_utilisateur = ?", (pseudo,))
    row = cur.fetchone()
    conn.close()
    assert row is not None and row[0], "Le token d'activation doit exister en base"
    token_activation = row[0]
    print(f'[INFO] Token d\'activation généré : {token_activation[:15]}...')

    # 5. Clic sur le lien d'activation : GET /activate?token=...
    statut, corps_html = faire_requete(f'{BASE_URL}/activate?token={token_activation}')
    print(f'[TEST 4] Clic sur lien activation -> Statut: {statut}')
    assert statut == 200, f"Attendu 200, obtenu {statut}"
    assert "Compte activé" in corps_html, "La page HTML doit confirmer l'activation"

    # 6. Tentative de réutilisation du même token (Doit échouer 400 - Jeton déjà utilisé)
    statut, corps_invalide = faire_requete(f'{BASE_URL}/activate?token={token_activation}')
    print(f'[TEST 5] Réutilisation du jeton d\'activation -> Statut: {statut} (Usage unique)')
    assert statut == 400, f"Attendu 400, obtenu {statut}"

    # 7. Connexion APRÈS activation (Doit réussir 200)
    statut, corps = faire_requete(
        f'{BASE_URL}/login', methode='POST', donnees=payload_login
    )
    print(f'[TEST 6] Connexion après activation -> Statut: {statut}')
    assert statut == 200, f"Attendu 200, obtenu {statut}"
    token_session = corps.get('token')
    assert token_session, "Un token de session doit être renvoyé"
    print(f'         Session Token: {token_session[:30]}...')

    # 8. Connexion via EMAIL au lieu du nom d'utilisateur
    statut_email_login, corps_email_login = faire_requete(
        f'{BASE_URL}/login', methode='POST', donnees={'nom_utilisateur': email, 'mot_de_passe': mot_de_passe}
    )
    print(f'[TEST 7] Connexion avec Email au lieu du Pseudo -> Statut: {statut_email_login}')
    assert statut_email_login == 200, "La connexion par email doit également fonctionner"

    # 9. Accès à /profile AVEC le token de session (Doit réussir 200)
    entetes = {'Authorization': f'Bearer {token_session}'}
    statut, corps = faire_requete(
        f'{BASE_URL}/profile', methode='GET', headers=entetes
    )
    print(f'[TEST 8] Accès /profile authentifié -> Statut: {statut}')
    print(f'         Message serveur: {corps.get("message")}')
    assert statut == 200, f"Attendu 200, obtenu {statut}"

    print('\n TOUS LES TESTS D\'INTÉGRATION AVEC ACTIVATION PAR EMAIL ONT RÉUSSI !')


if __name__ == '__main__':
    executer_flux_integration()