"""
Learning Assistant — Coach IA
Interface web Streamlit

Déploiement : https://share.streamlit.io
"""

import os
import io
import zipfile
from pathlib import Path
import streamlit as st
import anthropic
import openai

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
                    "description": "Chemin relatif. Ex: apprenants/tristan/profil.md"
                }
            },
            "required": ["chemin"]
        }
    },
    {
        "name": "ecrire_fichier",
        "description": "Écrire ou mettre à jour un fichier apprenant.",
        "input_schema": {
            "type": "object",
            "properties": {
                "chemin": {"type": "string"},
                "contenu": {"type": "string"},
                "mode": {
                    "type": "string",
                    "enum": ["remplacer", "ajouter"]
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
                "dossier": {"type": "string"}
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

# ─── Appel Claude ─────────────────────────────────────────────────────────────

def appeler_claude(conversation):
    api_key = st.secrets.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key)

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=conversation
        )

        if response.stop_reason == "end_turn":
            texte = next((b.text for b in response.content if b.type == "text"), "")
            conversation.append({"role": "assistant", "content": response.content})
            return texte

        if response.stop_reason == "tool_use":
            conversation.append({"role": "assistant", "content": response.content})
            resultats = []
            for bloc in response.content:
                if bloc.type == "tool_use":
                    resultat = executer_outil(bloc.name, bloc.input)
                    resultats.append({
                        "type": "tool_result",
                        "tool_use_id": bloc.id,
                        "content": resultat
                    })
            conversation.append({"role": "user", "content": resultats})
        else:
            break

    return ""

# ─── Interface Streamlit ──────────────────────────────────────────────────────

st.set_page_config(
    page_title="Learning Assistant",
    page_icon="🎯",
    layout="centered"
)

# ─── Sidebar : export / import ────────────────────────────────────────────────

with st.sidebar:
    st.header("Ma progression")

    prenom = st.text_input("Ton prénom (pour export/import)", key="prenom_sidebar")

    # Export
    if prenom:
        dossier = BASE_DIR / "apprenants" / prenom.lower()
        if dossier.exists():
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for fichier in dossier.rglob("*"):
                    if fichier.is_file():
                        zf.write(fichier, fichier.relative_to(BASE_DIR))
            buffer.seek(0)
            st.download_button(
                label="⬇️ Exporter ma progression",
                data=buffer,
                file_name=f"progression_{prenom.lower()}.zip",
                mime="application/zip"
            )
        else:
            st.caption("Pas encore de progression sauvegardée.")

    st.divider()

    # Import
    st.caption("Reprendre une session précédente :")
    fichier_importe = st.file_uploader(
        "Importer ma progression (.zip)",
        type="zip",
        key="import_zip"
    )
    if fichier_importe:
        with zipfile.ZipFile(io.BytesIO(fichier_importe.read())) as zf:
            zf.extractall(BASE_DIR)
        st.success("Progression restaurée ✓")
        st.rerun()


# ─── Interface principale ─────────────────────────────────────────────────────

st.title("🎯 Learning Assistant")
st.caption("Coach IA — Développement de compétences en entreprise")

# Initialisation de l'état
if "conversation" not in st.session_state:
    st.session_state.conversation = []
if "messages_affiches" not in st.session_state:
    st.session_state.messages_affiches = []
if "transcription_pending" not in st.session_state:
    st.session_state.transcription_pending = None
if "last_audio_hash" not in st.session_state:
    st.session_state.last_audio_hash = None

# Affichage de l'historique
for msg in st.session_state.messages_affiches:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Message d'accueil si première visite
if not st.session_state.messages_affiches:
    with st.chat_message("assistant"):
        st.markdown("Bonjour ! Je suis ton learning assistant. Pour commencer, quel est ton prénom ?")
    st.session_state.messages_affiches.append({
        "role": "assistant",
        "content": "Bonjour ! Je suis ton learning assistant. Pour commencer, quel est ton prénom ?"
    })
    st.session_state.conversation.append({
        "role": "assistant",
        "content": "Bonjour ! Je suis ton learning assistant. Pour commencer, quel est ton prénom ?"
    })

# ─── Micro inline (à côté du chat input) ─────────────────────────────────────

audio_data = st.audio_input("🎤", label_visibility="collapsed", key="mic_inline")

if audio_data is not None:
    audio_bytes = audio_data.read()
    audio_hash = hash(audio_bytes)
    if audio_hash != st.session_state.last_audio_hash:
        st.session_state.last_audio_hash = audio_hash
        openai_key = st.secrets.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if openai_key:
            with st.spinner("Transcription..."):
                try:
                    oa_client = openai.OpenAI(api_key=openai_key)
                    transcription = oa_client.audio.transcriptions.create(
                        model="whisper-1",
                        file=("audio.wav", audio_bytes),
                    )
                    st.session_state.transcription_pending = transcription.text
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur transcription : {e}")

# Injection de la transcription en attente
if st.session_state.transcription_pending:
    prompt_transcrit = st.session_state.transcription_pending
    st.session_state.transcription_pending = None
    with st.chat_message("user"):
        st.markdown(prompt_transcrit)
    st.session_state.messages_affiches.append({"role": "user", "content": prompt_transcrit})
    st.session_state.conversation.append({"role": "user", "content": prompt_transcrit})
    with st.chat_message("assistant"):
        with st.spinner("..."):
            reponse = appeler_claude(st.session_state.conversation)
        st.markdown(reponse)
    st.session_state.messages_affiches.append({"role": "assistant", "content": reponse})

# Saisie utilisateur
if prompt := st.chat_input("Votre message..."):
    # Affiche le message utilisateur
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages_affiches.append({"role": "user", "content": prompt})
    st.session_state.conversation.append({"role": "user", "content": prompt})

    # Appel Claude
    with st.chat_message("assistant"):
        with st.spinner("..."):
            reponse = appeler_claude(st.session_state.conversation)
        st.markdown(reponse)

    st.session_state.messages_affiches.append({"role": "assistant", "content": reponse})
