import hashlib
import secrets
import hmac
import base64
import json
import time

ITERATIONS = 600_000
CLE_SECRETE = b"chaine_secret_ultra_securisee_2026"


def hacher_mot_de_passe(mot_de_passe: str, sel: bytes = None) -> tuple[bytes, bytes]:
    """
    Hache un mot de passe en utilisant PBKDF2 avec SHA-256.
    Génère un nouveau sel aléatoire de 16 octets si aucun n'est fourni.
    """
    if sel is None:
        sel = secrets.token_bytes(16)  # 128 bits de sel aléatoire
    
    mot_de_passe_bytes = mot_de_passe.encode('utf-8')
    
    empreinte = hashlib.pbkdf2_hmac(
        'sha256',
        mot_de_passe_bytes,
        sel,
        ITERATIONS
    )
    
    return sel, empreinte
def verifier_mot_de_passe(mot_de_passe_saisi: str , sel_stocker: bytes , empreinte_stocker:bytes)-> bool:
   
    #Verifier si le mot de passe saisi correspond à l'empreinte stockée.
    #Utiliser une comparaison à temps constant pour éviter les timing attacks.
   
   _, nouvelle_empreinte = hacher_mot_de_passe(mot_de_passe_saisi , sel= sel_stocker)

   return hmac.compare_digest (empreinte_stocker, nouvelle_empreinte)


def  generer_token_session (nom_utilisateur: str, duree_validite: int = 3600) -> str:
    """
    Génère un token de session pour un utilisateur donné.
    Le token contient le nom d'utilisateur et un timestamp d'expiration.
    """
    timestamp_expiration = int(time.time()) + duree_validite
    payload = {
        "nom_utilisateur": nom_utilisateur,
        "expiration": timestamp_expiration
    }
    payload_json = json.dumps(payload).encode('utf-8')
    payload_b64 = base64.urlsafe_b64encode(payload_json).decode('utf-8')
    
    signature = hmac.new(
        CLE_SECRETE, 
        payload_b64.encode('utf-8'), 
        'sha256'
    ).hexdigest()
    
    return f"{payload_b64}.{signature}"


def valider_format_email(email: str) -> bool:
    """Vérifie si une adresse email a une syntaxe valide."""
    import re
    if not email or len(email) > 254:
        return False
    motif = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return bool(re.match(motif, email))


def generer_token_activation() -> str:
    """Génère un jeton cryptographique aléatoire et sécurisé pour l'activation par email."""
    return secrets.token_urlsafe(32)


def verifier_token_session(token: str) -> str | None:
    """
    Vérifie la validité d'un token de session.
    Retourne le nom d'utilisateur si le token est valide et non expiré, sinon None.
    """
    try:
        payload_b64, signature = token.rsplit('.')
        signature_attendue = hmac.new(
            CLE_SECRETE, 
            payload_b64.encode('utf-8'), 
            'sha256'
        ).hexdigest()

        if not hmac.compare_digest(signature, signature_attendue):
            return None

        payload_json = base64.urlsafe_b64decode(payload_b64).decode('utf-8')
        payload = json.loads(payload_json)

        if time.time() > payload["expiration"]:
            return None

        return payload["nom_utilisateur"]
    except Exception:
        return None

if __name__ == '__main__':
    print("--- Test du module core/security.py ---")
    
    mdp_test = "MonSuperMotDePasse2026!"
    # 1. Hachage
    sel, empreinte = hacher_mot_de_passe(mdp_test)
    print(f"[OK] Sel généré (hex) : {sel.hex()}")
    print(f"[OK] Empreinte générée (hex) : {empreinte.hex()}")
    # 2. Vérification bon mot de passe
    valide = verifier_mot_de_passe(mdp_test, sel, empreinte)
    print(f"[OK] Test bon mot de passe : {valide}")  # Doit afficher True
    # 3. Vérification mauvais mot de passe
    invalide = verifier_mot_de_passe("MauvaisMDP", sel, empreinte)
    print(f"[OK] Test mauvais mot de passe : {invalide}")  # Doit afficher False