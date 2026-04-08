#!/usr/bin/env python3
"""
Learning Assistant — Coach IA
------------------------------
Prérequis :
  1. Python 3.8+
  2. pip install anthropic
  3. Variable d'environnement ANTHROPIC_API_KEY définie

Lancement :
  python coach.py
"""

import os
import json
from pathlib import Path
import anthropic

# ─── Configuration ────────────────────────────────────────────────────────────

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096
BASE_DIR = Path(__file__).parent
APPRENANTS_DIR = BASE_DIR / "apprenants"

# ─── System prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """
Tu es un learning assistant spécialisé dans le développement de compétences en entreprise.

## Ton rôle

Tu accompagnes les apprenants sur la durée pour qu'ils progressent sur des compétences réelles.
Tu as accès à des outils pour lire et écrire des fichiers — utilise-les pour sauvegarder et retrouver la progression de chaque apprenant.

## Au démarrage de chaque conversation

1. Demande le prénom de l'apprenant
2. Lis le fichier `apprenants/[prénom]/profil.md` s'il existe
3. Lis le fichier `apprenants/[prénom]/scores.md` s'il existe
4. Adapte ton accueil selon ce que tu trouves :
   - Nouvel apprenant → commence par le profil (intake)
   - Apprenant connu → résume sa progression et propose la prochaine étape

## Les 4 phases d'apprentissage

### Phase 1 — Intake (profil)
Collecte 5 informations en 5 questions, une à la fois :
① Rôle et contexte (entreprise, poste)
② Compétence à développer (en ses propres mots)
③ Situation réelle à venir où mobiliser cette compétence
④ Niveau actuel (débutant / intermédiaire / avancé avec angle mort)
⑤ Ce que "réussir" signifie pour lui

Génère ensuite un Profil Apprenant structuré, demande validation, puis sauvegarde dans `apprenants/[prénom]/profil.md`.

### Phase 2 — Contenu
Présente le contenu en 5 blocs, UN à la fois. Attend validation avant chaque bloc suivant.
Après chaque bloc, pose une question de vérification naturellement intégrée.

Blocs :
① Pourquoi c'est difficile pour toi spécifiquement
② Le renversement clé (une phrase mémorable)
③ L'erreur que tu fais probablement
④ La technique prioritaire (avec formulation concrète à réutiliser)
⑤ Le signal de réussite observable

### Phase 3 — Simulation
Joue le rôle de l'interlocuteur réel. Reste en personnage.
Introduis des obstacles réalistes (questions sans réponse, dérives, silences).
Après 5-8 échanges ou si l'apprenant dit "stop" : sors du personnage, donne un feedback en 3 points.
Sauvegarde un résumé dans `apprenants/[prénom]/sessions.md`.

### Phase 4 — Débrief transcript
Si l'apprenant importe un transcript, score chaque sous-dimension avec citation.
Identifie le pattern récurrent et le point fort à ancrer.
Sauvegarde les scores dans `apprenants/[prénom]/scores.md`.

## Règles générales

- Une question ou un bloc à la fois — jamais de liste
- Ton conversationnel, pas celui d'un formulaire
- Ancre toujours le contenu dans SA situation réelle
- Sauvegarde systématiquement après chaque phase clé

## Format des fichiers de sauvegarde

**profil.md** :
```
# Profil — [Prénom]
**Rôle :** ...
**Compétence :** ...
**Sous-dimensions :** liste
**Situation réelle :** ...
**Niveau actuel :** ...
**Objectif :** ...
**Priorité :** ...
**Date :** ...
```

**scores.md** — ajoute une entrée par session :
```
## Session [N] — [date]
**Situation :** ...
| Sous-dimension | Score |
|---|---|
| ... | X/10 |
**Score global :** X/10
**Pattern :** ...
**Axe de travail :** ...
```

**sessions.md** — ajoute un résumé par session :
```
## [date] — [type : simulation / débrief]
[2-3 lignes sur ce qui s'est passé]
```
"""

# ─── Outils fichiers ──────────────────────────────────────────────────────────

tools = [
    {
        "name": "lire_fichier",
        "description": "Lire le contenu d'un fichier apprenant.",
        "input_schema": {
            "type": "object",
            "properties": {
                "chemin": {
                    "type": "string",
                    "description": "Chemin relatif depuis la racine du projet. Ex: apprenants/tristan/profil.md"
                }
            },
            "required": ["chemin"]
        }
    },
    {
        "name": "ecrire_fichier",
        "description": "Écrire ou mettre à jour un fichier apprenant. Crée les dossiers si nécessaire.",
        "input_schema": {
            "type": "object",
            "properties": {
                "chemin": {
                    "type": "string",
                    "description": "Chemin relatif. Ex: apprenants/tristan/profil.md"
                },
                "contenu": {
                    "type": "string",
                    "description": "Contenu complet à écrire dans le fichier."
                },
                "mode": {
                    "type": "string",
                    "enum": ["remplacer", "ajouter"],
                    "description": "remplacer = écrase le fichier, ajouter = ajoute à la fin."
                }
            },
            "required": ["chemin", "contenu", "mode"]
        }
    },
    {
        "name": "lister_fichiers",
        "description": "Lister les fichiers d'un dossier apprenant.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dossier": {
                    "type": "string",
                    "description": "Chemin relatif du dossier. Ex: apprenants/tristan"
                }
            },
            "required": ["dossier"]
        }
    }
]

# ─── Exécution des outils ─────────────────────────────────────────────────────

def executer_outil(nom, params):
    try:
        if nom == "lire_fichier":
            chemin = BASE_DIR / params["chemin"]
            if chemin.exists():
                return chemin.read_text(encoding="utf-8")
            return f"Fichier introuvable : {params['chemin']}"

        elif nom == "ecrire_fichier":
            chemin = BASE_DIR / params["chemin"]
            chemin.parent.mkdir(parents=True, exist_ok=True)
            mode = "a" if params.get("mode") == "ajouter" else "w"
            with open(chemin, mode, encoding="utf-8") as f:
                if mode == "a":
                    f.write("\n" + params["contenu"])
                else:
                    f.write(params["contenu"])
            return f"Fichier sauvegardé : {params['chemin']}"

        elif nom == "lister_fichiers":
            dossier = BASE_DIR / params["dossier"]
            if dossier.exists():
                fichiers = [f.name for f in dossier.iterdir()]
                return ", ".join(fichiers) if fichiers else "Dossier vide"
            return "Dossier introuvable"

    except Exception as e:
        return f"Erreur : {str(e)}"

# ─── Boucle de conversation ───────────────────────────────────────────────────

def chat():
    # Vérification clé API
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n❌ Clé API manquante.")
        print("   Définissez la variable d'environnement ANTHROPIC_API_KEY.")
        print("   Sur Mac/Linux : export ANTHROPIC_API_KEY='votre-clé'")
        return

    client = anthropic.Anthropic()
    conversation = []

    print("\n" + "═" * 50)
    print("   LEARNING ASSISTANT — COACH IA")
    print("═" * 50)
    print("Tapez votre message et appuyez sur Entrée.")
    print("Tapez 'quitter' pour terminer.")
    print("─" * 50 + "\n")

    while True:
        try:
            user_input = input("Vous : ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nÀ bientôt !")
            break

        if not user_input:
            continue
        if user_input.lower() in ["quitter", "quit", "exit", "q"]:
            print("\nÀ bientôt !")
            break

        conversation.append({"role": "user", "content": user_input})

        # Boucle outil — Claude peut appeler plusieurs outils avant de répondre
        while True:
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                tools=tools,
                messages=conversation
            )

            # Si Claude a fini (pas d'appel outil), on affiche et on sort
            if response.stop_reason == "end_turn":
                texte = next(
                    (b.text for b in response.content if b.type == "text"), ""
                )
                print(f"\nCoach : {texte}\n")
                conversation.append({
                    "role": "assistant",
                    "content": response.content
                })
                break

            # Claude appelle des outils
            if response.stop_reason == "tool_use":
                conversation.append({
                    "role": "assistant",
                    "content": response.content
                })

                resultats = []
                for bloc in response.content:
                    if bloc.type == "tool_use":
                        resultat = executer_outil(bloc.name, bloc.input)
                        resultats.append({
                            "type": "tool_result",
                            "tool_use_id": bloc.id,
                            "content": resultat
                        })

                conversation.append({
                    "role": "user",
                    "content": resultats
                })
                # Continue la boucle — Claude va traiter les résultats
            else:
                # Cas inattendu
                break

if __name__ == "__main__":
    chat()
