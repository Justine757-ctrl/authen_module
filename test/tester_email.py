import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD
from noyaux.email_service import envoyer_email_activation


def tester_envoi():
    print("=" * 60)
    print("TEST DE CONNEXION SMTP GOOGLE")
    print("=" * 60)
    print(f"Serveur  : {SMTP_HOST}:{SMTP_PORT}")
    print(f"Compte   : {SMTP_USER}")
    print(f"Mot de passe configuré : {'*' * len(SMTP_PASSWORD) if SMTP_PASSWORD else '(vide)'} ({len(SMTP_PASSWORD)} caractères)")

    if len(SMTP_PASSWORD) != 16:
        print("\nATTENTION : Un mot de passe d'application Google comporte EXACTEMENT 16 lettres.")
        print(f"Votre mot de passe actuel fait {len(SMTP_PASSWORD)} caractères.")

    print("\nTentative d'envoi d'un email de test...")
    succes, message = envoyer_email_activation(
        destinataire_email=SMTP_USER,
        nom_utilisateur="Justine",
        token_activation="test_token_verification_123"
    )

    print("\n" + "=" * 60)
    if succes and "succès" in message:
        print("SUCCÈS ! L'email a bien été envoyé via Google.")
        print("Vérifiez votre boîte de réception Gmail !")
    else:
        print("ÉCHEC :", message)
    print("=" * 60)


if __name__ == '__main__':
    tester_envoi()
