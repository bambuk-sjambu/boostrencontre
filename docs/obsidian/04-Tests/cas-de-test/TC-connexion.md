# Tests de connexion (TC-001 a TC-003)

Prerequis : [[04-Tests/prerequis|Prerequis]] -- serveur lance, pas encore de navigateur ouvert.

---

## TC-001 : Ouverture du navigateur

**Objectif** : Verifier que le navigateur Playwright s'ouvre correctement et charge la page Wyylde.

**Etapes** :

1. S'assurer que le serveur tourne (`venv/bin/python main.py`)
2. Appeler l'API pour ouvrir le navigateur :
   ```bash
   curl -X POST http://127.0.0.1:8888/api/browser/wyylde
   ```
3. Observer qu'un navigateur Chrome s'ouvre automatiquement
4. Verifier que la page Wyylde se charge (page de login ou dashboard si session precedente)

**Resultat attendu** :
- La reponse API contient `"status": "opening"`
- Un navigateur Chrome (Chromium) s'ouvre en mode visible (pas headless)
- La page Wyylde se charge (URL contient `wyylde.com`)

**Criteres de validation** :
- [ ] Le navigateur est visible a l'ecran
- [ ] L'URL affichee contient `wyylde.com`
- [ ] Pas d'erreur dans les logs du serveur

**Verification supplementaire** -- appel en doublon :
```bash
curl -X POST http://127.0.0.1:8888/api/browser/wyylde
```
Doit retourner `"status": "already_open"` sans ouvrir un second navigateur.

---

## TC-002 : Login manuel et detection

**Objectif** : Se connecter manuellement dans le navigateur Playwright et verifier que le bot detecte la connexion.

**Prerequis** : TC-001 execute (navigateur ouvert sur la page de login Wyylde).

**Etapes** :

1. Dans le navigateur Playwright ouvert, entrer ses identifiants Wyylde (email + mot de passe)
2. Cliquer sur le bouton de connexion
3. Attendre d'arriver sur le dashboard Wyylde (URL contenant `/dashboard/wall`)
4. Verifier la detection de connexion :
   ```bash
   curl http://127.0.0.1:8888/api/check-login/wyylde
   ```

**Resultat attendu** :
```json
{"logged_in": true}
```

**Criteres de validation** :
- [ ] La reponse contient `"logged_in": true`
- [ ] Le dashboard BoostRencontre (http://127.0.0.1:8888) affiche "Connecte" en vert pour Wyylde
- [ ] Les logs serveur indiquent la sauvegarde de la session

**Verification negative** -- avant login :
Si on appelle `check-login` avant de se connecter :
```bash
curl http://127.0.0.1:8888/api/check-login/wyylde
```
Doit retourner `{"logged_in": false}`.

---

## TC-003 : Persistance de session

**Objectif** : Verifier que la session navigateur est conservee apres fermeture et reouverture (grace au profil navigateur persistent).

**Prerequis** : TC-002 execute (connecte sur Wyylde).

**Etapes** :

1. Fermer le navigateur via l'API :
   ```bash
   curl -X POST http://127.0.0.1:8888/api/close/wyylde
   ```
   Reponse attendue : `{"status": "closed"}`
   Le navigateur doit se fermer.

2. Attendre 3 secondes.

3. Rouvrir le navigateur :
   ```bash
   curl -X POST http://127.0.0.1:8888/api/browser/wyylde
   ```
   Le navigateur doit s'ouvrir et charger Wyylde.

4. Attendre 10 secondes que la page se charge completement.

5. Verifier la connexion :
   ```bash
   curl http://127.0.0.1:8888/api/check-login/wyylde
   ```

**Resultat attendu** :
```json
{"logged_in": true}
```
Sans avoir eu besoin de re-saisir les identifiants.

**Criteres de validation** :
- [ ] Apres fermeture, le navigateur disparait
- [ ] Apres reouverture, Wyylde charge directement le dashboard (pas la page de login)
- [ ] `check-login` retourne `true` sans re-login
- [ ] Le profil navigateur est stocke dans `~/.boostrencontre/browser_profiles/wyylde/`

**Points d'attention** :
- La persistance repose sur le dossier `~/.boostrencontre/browser_profiles/wyylde/`
- Si ce dossier est supprime, la session sera perdue
- Verifier que le dossier existe :
  ```bash
  ls -la ~/.boostrencontre/browser_profiles/wyylde/
  ```
