import time
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from noyaux.security import (
    generer_token_session, 
    verifier_token_session, 
    hacher_mot_de_passe,
    verifier_mot_de_passe,
    generer_token_activation,
    valider_format_email
)


def test_module_securite():
    print("--- Test du module de sécurité ---")
    
    # 1. Hachage et vérification de mot de passe
    print("[1] Test hachage et vérification PBKDF2-HMAC-SHA256...")
    mdp = 'MonSuperMotDePasse2026!'
    sel, empreinte = hacher_mot_de_passe(mdp)
    assert verifier_mot_de_passe(mdp, sel, empreinte) is True
    assert verifier_mot_de_passe('MotDePasseIncorrect', sel, empreinte) is False
    print("    -> PBKDF2-HMAC-SHA256 : OK")

    # 2. Validation d'email
    print("[2] Test validation de syntaxe email...")
    assert valider_format_email("test@gmail.com") is True
    assert valider_format_email("user.name+tag@domain.co.uk") is True
    assert valider_format_email("invalid-email") is False
    assert valider_format_email("@domain.com") is False
    assert valider_format_email("") is False
    print("    -> Validation email : OK")

    # 3. Génération de token d'activation
    print("[3] Test jeton d'activation...")
    token_act1 = generer_token_activation()
    token_act2 = generer_token_activation()
    assert len(token_act1) >= 32
    assert token_act1 != token_act2
    print("    -> Génération jetons uniques d'activation : OK")

    # 4. Token de session et vérification
    print("[4] Test génération et vérification de token session...")
    token = generer_token_session('justo', duree_validite=3)
    user = verifier_token_session(token)
    assert user == 'justo'
    print("    -> Token valide : OK")

    # 5. Token falsifié
    token_falsification = token[:-8] + 'X' * 8
    assert verifier_token_session(token_falsification) is None
    print("    -> Détection falsification : OK")

    # 6. Expiration de token
    print("[5] Test expiration du token de session...")
    time.sleep(3.5)
    assert verifier_token_session(token) is None
    print("    -> Détection token expiré : OK")

    print("\n TOUS LES TESTS DE SECURITE SONT VALIDES !\n")


if __name__ == '__main__':
    test_module_securite()