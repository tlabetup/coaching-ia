# Démarrage rapide

## 1. Prérequis

- Python 3.8 ou plus récent
- Une clé API Anthropic

## 2. Installation (une seule fois)

Ouvre un terminal et tape :

```bash
pip install anthropic
```

## 3. Clé API

Dans ton terminal, ajoute ta clé API :

```bash
export ANTHROPIC_API_KEY="ta-clé-ici"
```

> Pour ne pas avoir à le refaire à chaque fois, ajoute cette ligne à ton fichier `~/.zshrc` ou `~/.bashrc`.

## 4. Lancer l'assistant

```bash
cd chemin/vers/coach-ia
python coach.py
```

## 5. Utilisation

- Tape ton message et appuie sur **Entrée**
- Tape `quitter` pour terminer
- Ta progression est sauvegardée automatiquement dans le dossier `apprenants/`

---

*Ta progression est conservée entre les sessions — l'assistant reprend où tu t'es arrêté.*
