# Learning Assistant — Coach IA

Ce dossier contient un prototype de learning assistant pour le développement de compétences en entreprise.

## Comment démarrer

Tape `/la-learning` pour lancer l'assistant.

Il te guidera automatiquement selon où tu en es :
- Première fois → il te pose quelques questions pour créer ton profil
- Sessions suivantes → il reprend ta progression et propose la prochaine étape

## Ce que fait l'assistant

Il t'entraîne sur une compétence réelle en 4 phases :
1. **Profil** — comprendre ta situation et ce que tu veux développer
2. **Contenu** — t'apporter les clés adaptées à ton contexte
3. **Simulation** — te mettre en conditions réelles pour t'entraîner
4. **Débrief** — analyser tes vraies conversations et mesurer ta progression

## Ta progression est sauvegardée

Ton profil et tes scores sont conservés dans `apprenants/[ton prénom]/`.
À chaque nouvelle session, l'assistant repart de là où tu t'es arrêté.

## Commandes disponibles

| Commande | Usage |
|---|---|
| `/la-learning` | Point d'entrée principal — commence ici |
| `/la-intake` | Créer ou mettre à jour ton profil |
| `/la-content` | Travailler le contenu sur ta compétence |
| `/la-simulation` | Lancer une simulation |
| `/la-debrief` | Analyser un transcript réel |
