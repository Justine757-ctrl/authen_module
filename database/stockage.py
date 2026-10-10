import sqlite3
import os
import sys

# Résolution automatique du chemin absolu de la base de données
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from noyaux.security import hacher_mot_de_passe, verifier_mot_de_passe

DB_FILE = os.path.join(BASE_DIR, "authentification.db")


def initialiser_base():
    """Crée ou met à jour la table 'utilisateurs' dans SQLite."""
    connexion = sqlite3.connect(DB_FILE)
    curseur = connexion.cursor()

    # Création initiale si la table n'existe pas
    curseur.execute("""
        CREATE TABLE IF NOT EXISTS utilisateurs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom_utilisateur TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE,
            sel BLOB NOT NULL,
            empreinte BLOB NOT NULL,
            est_actif INTEGER DEFAULT 0,
            token_activation TEXT,
            date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Migration automatique pour les bases de données existantes (ajout des colonnes manquantes)
    curseur.execute("PRAGMA table_info(utilisateurs)")
    colonnes_existantes = [col[1] for col in curseur.fetchall()]

    if "email" not in colonnes_existantes:
        curseur.execute("ALTER TABLE utilisateurs ADD COLUMN email TEXT")

    if "est_actif" not in colonnes_existantes:
        # Les anciens utilisateurs sans activation restent actifs
        curseur.execute("ALTER TABLE utilisateurs ADD COLUMN est_actif INTEGER DEFAULT 1")
        curseur.execute("UPDATE utilisateurs SET est_actif = 1 WHERE est_actif IS NULL")

    if "token_activation" not in colonnes_existantes:
        curseur.execute("ALTER TABLE utilisateurs ADD COLUMN token_activation TEXT")

    connexion.commit()
    connexion.close()


def ajouter_utilisateur(
    nom_utilisateur: str, email: str, mot_de_passe: str, token_activation: str
) -> tuple[bool, str]:
    """
    Insère un nouvel utilisateur inactif (est_actif=0) avec son jeton d'activation.
    Retourne (succès: bool, message: str)
    """
    initialiser_base()

    if not nom_utilisateur or not nom_utilisateur.strip():
        return False, "Le nom d'utilisateur est requis."
    if not email or not email.strip():
        return False, "L'adresse email est requise."
    if not mot_de_passe:
        return False, "Le mot de passe est requis."

    nom_utilisateur = nom_utilisateur.strip()
    email = email.strip().lower()

    # Génération du sel et du hachage PBKDF2
    sel, empreinte = hacher_mot_de_passe(mot_de_passe)

    connexion = sqlite3.connect(DB_FILE)
    curseur = connexion.cursor()

    # Vérification d'unicité du nom d'utilisateur
    curseur.execute(
        "SELECT id FROM utilisateurs WHERE nom_utilisateur = ?", (nom_utilisateur,)
    )
    if curseur.fetchone():
        connexion.close()
        return False, "Ce nom d'utilisateur est déjà utilisé."

    # Vérification d'unicité de l'email
    curseur.execute(
        "SELECT id FROM utilisateurs WHERE email = ?", (email,)
    )
    if curseur.fetchone():
        connexion.close()
        return False, "Cette adresse email est déjà enregistrée."

    # Insertion avec est_actif = 0
    curseur.execute(
        """
        INSERT INTO utilisateurs (nom_utilisateur, email, sel, empreinte, est_actif, token_activation)
        VALUES (?, ?, ?, ?, 0, ?)
    """,
        (nom_utilisateur, email, sel, empreinte, token_activation),
    )

    connexion.commit()
    connexion.close()
    return True, "Utilisateur créé avec succès. En attente d'activation."


def activer_compte(token_activation: str) -> tuple[bool, str, str | None]:
    """
    Active le compte associé au jeton fourni.
    Supprime le jeton après activation pour qu'il soit à usage unique.
    
    Retourne (succès: bool, message: str, nom_utilisateur: str | None)
    """
    if not token_activation or not token_activation.strip():
        return False, "Jeton d'activation manquant.", None

    initialiser_base()
    connexion = sqlite3.connect(DB_FILE)
    curseur = connexion.cursor()

    curseur.execute(
        """
        SELECT id, nom_utilisateur, est_actif 
        FROM utilisateurs 
        WHERE token_activation = ?
    """,
        (token_activation.strip(),),
    )

    resultat = curseur.fetchone()

    if not resultat:
        connexion.close()
        return False, "Lien d'activation invalide ou déjà utilisé.", None

    user_id, nom_utilisateur, est_actif = resultat

    if est_actif == 1:
        # Déjà actif, on nettoie le token
        curseur.execute(
            "UPDATE utilisateurs SET token_activation = NULL WHERE id = ?", (user_id,)
        )
        connexion.commit()
        connexion.close()
        return True, "Ce compte est déjà activé.", nom_utilisateur

    # Activation du compte et invalidation du token
    curseur.execute(
        """
        UPDATE utilisateurs 
        SET est_actif = 1, token_activation = NULL 
        WHERE id = ?
    """,
        (user_id,),
    )

    connexion.commit()
    connexion.close()
    return True, "Votre compte a été activé avec succès !", nom_utilisateur


def renouveler_token_activation(
    identifiant: str, nouveau_token: str
) -> tuple[bool, str, str | None, str | None]:
    """
    Met à jour le jeton d'activation d'un compte non actif pour renvoyer un email.
    Retourne (succès: bool, message: str, email: str | None, nom_utilisateur: str | None)
    """
    initialiser_base()
    connexion = sqlite3.connect(DB_FILE)
    curseur = connexion.cursor()

    identifiant = identifiant.strip().lower()

    curseur.execute(
        """
        SELECT id, nom_utilisateur, email, est_actif 
        FROM utilisateurs 
        WHERE LOWER(nom_utilisateur) = ? OR LOWER(email) = ?
    """,
        (identifiant, identifiant),
    )

    resultat = curseur.fetchone()
    if not resultat:
        connexion.close()
        return False, "Aucun compte associé à cet identifiant.", None, None

    user_id, nom_utilisateur, email, est_actif = resultat

    if est_actif == 1:
        connexion.close()
        return False, "Ce compte est déjà activé. Vous pouvez vous connecter.", email, nom_utilisateur

    curseur.execute(
        "UPDATE utilisateurs SET token_activation = ? WHERE id = ?",
        (nouveau_token, user_id),
    )
    connexion.commit()
    connexion.close()

    return True, "Nouveau jeton généré.", email, nom_utilisateur


def authentifier_utilisateur(
    identifiant: str, mot_de_passe_saisi: str
) -> tuple[str, str | None]:
    """
    Vérifie les identifiants d'un utilisateur (pseudo OU email) et son statut d'activation.
    
    Retourne :
      - ("SUCCES", nom_utilisateur) si identifiants valides et compte actif
      - ("NON_ACTIVE", nom_utilisateur) si mot de passe bon mais compte inactif
      - ("MOT_DE_PASSE_INCORRECT", None) si mauvais mot de passe
      - ("INTROUVABLE", None) si l'utilisateur n'existe pas
    """
    initialiser_base()

    if not identifiant or not mot_de_passe_saisi:
        return "INTROUVABLE", None

    connexion = sqlite3.connect(DB_FILE)
    curseur = connexion.cursor()

    identifiant = identifiant.strip()

    curseur.execute(
        """
        SELECT nom_utilisateur, sel, empreinte, est_actif 
        FROM utilisateurs 
        WHERE LOWER(nom_utilisateur) = LOWER(?) OR LOWER(email) = LOWER(?)
    """,
        (identifiant, identifiant),
    )

    resultat = curseur.fetchone()
    connexion.close()

    if not resultat:
        return "INTROUVABLE", None

    nom_utilisateur, sel_stocke, empreinte_stockee, est_actif = resultat

    # Vérification PBKDF2
    if not verifier_mot_de_passe(mot_de_passe_saisi, sel_stocke, empreinte_stockee):
        return "MOT_DE_PASSE_INCORRECT", None

    # Vérification si le compte a été activé par email
    if est_actif != 1:
        return "NON_ACTIVE", nom_utilisateur

    return "SUCCES", nom_utilisateur


if __name__ == '__main__':
    print('--- Test de la persistance SQLite et activation ---')
    initialiser_base()
    print('[OK] Base de données initialisée et migrée avec succès.')