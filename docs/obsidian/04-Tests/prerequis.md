# Prerequis -- Checklist avant tests

Valider chaque point avant de commencer les tests manuels.

## Environnement technique

- [ ] **Python 3.12** installe et accessible :
  ```bash
  python3 --version
  # Attendu : Python 3.12.x
  ```

- [ ] **Virtualenv active** et dependances installees :
  ```bash
  cd /media/stef/Photos\ -\ Sauv/DEV-JAMBU/boostrencontre
  source venv/bin/activate
  pip list | grep -E "fastapi|playwright|openai|aiosqlite"
  ```
  Verifier que ces 4 packages apparaissent dans la liste.

- [ ] **Playwright Chromium** installe :
  ```bash
  venv/bin/python -m playwright install chromium
  ```

- [ ] **Fichier `.env`** present a la racine du projet avec au minimum :
  ```
  OPENAI_API_KEY=sk-...
  ```
  Verifier :
  ```bash
  cat .env | grep OPENAI_API_KEY
  ```
  La cle doit commencer par `sk-`.

## Compte Wyylde

- [ ] **Compte Wyylde actif** avec un abonnement valide (necessaire pour envoyer des messages)
- [ ] **Identifiants** connus (email + mot de passe) pour le login manuel
- [ ] **Au moins quelques profils en ligne** visibles dans le chat sidebar (necessaire pour les tests de likes et messages)

## Lancement du serveur

- [ ] **Serveur lance** :
  ```bash
  cd /media/stef/Photos\ -\ Sauv/DEV-JAMBU/boostrencontre
  venv/bin/python main.py
  ```
  Verifier dans les logs que le serveur demarre sans erreur. La ligne suivante doit apparaitre :
  ```
  INFO:     Uvicorn running on http://0.0.0.0:8888
  ```

- [ ] **Dashboard accessible** : ouvrir http://127.0.0.1:8888 dans un navigateur classique (Firefox, Chrome).
  La page doit afficher le titre "BoostRencontre" et les 3 cartes de plateformes (Tinder, Meetic, Wyylde).

## Ouverture du navigateur Playwright

- [ ] **Navigateur ouvert** via l'API :
  ```bash
  curl -X POST http://127.0.0.1:8888/api/browser/wyylde
  ```
  Reponse attendue :
  ```json
  {"status": "opening", "message": "Ouverture de wyylde... Le navigateur va s'ouvrir."}
  ```
  Un navigateur Chrome doit s'ouvrir automatiquement avec la page Wyylde.

## Login manuel

- [ ] **Login effectue** : dans le navigateur Playwright qui vient de s'ouvrir, se connecter manuellement avec ses identifiants Wyylde. Attendre d'arriver sur le dashboard Wyylde (URL contenant `/dashboard`).

- [ ] **Login verifie** :
  ```bash
  curl http://127.0.0.1:8888/api/check-login/wyylde
  ```
  Reponse attendue :
  ```json
  {"logged_in": true}
  ```

## Profil IA

- [ ] **Profil IA renseigne** : ouvrir http://127.0.0.1:8888/profile et verifier que les champs suivants sont remplis :
  - Pseudo (le pseudo utilise sur Wyylde)
  - Type (ex: Homme hetero, Couple F Bi, etc.)
  - Age
  - Localisation
  - Description

  Si le profil est vide, le remplir avant de lancer les tests de messages IA.

## Verification finale

- [ ] Le terminal du serveur affiche les logs en temps reel
- [ ] Le navigateur Playwright est visible et affiche le dashboard Wyylde
- [ ] Le dashboard BoostRencontre affiche "Connecte" en vert pour Wyylde

Quand tous les points sont coches, commencer les tests par [[04-Tests/cas-de-test/TC-connexion|TC-connexion]].
