# Tests de securite (TC-060 a TC-062)

Prerequis : [[04-Tests/prerequis|Prerequis]] -- serveur lance.

---

## TC-060 : Token d'authentification du dashboard

**Objectif** : Verifier que le mecanisme de token protege l'acces au dashboard.

### Cas 1 : Token auto-genere (pas de DASHBOARD_TOKEN dans .env)

**Etapes** :

1. S'assurer que la variable `DASHBOARD_TOKEN` n'est PAS definie dans `.env`
2. Lancer le serveur :
   ```bash
   venv/bin/python main.py
   ```
3. Observer les logs de demarrage : un token auto-genere doit etre affiche
   ```
   INFO: Dashboard token: XXXXXXXX
   ```
4. Le dashboard est accessible sans token supplementaire (le token est pour les appels API externes)

### Cas 2 : Token personnalise (DASHBOARD_TOKEN dans .env)

**Etapes** :

1. Ajouter dans `.env` :
   ```
   DASHBOARD_TOKEN=mon_token_secret_123
   ```
2. Relancer le serveur
3. Observer les logs : le token personnalise est charge

**Verification** :
- Les appels API doivent fonctionner normalement depuis le dashboard (meme origine)
- Pour les appels depuis un client externe, le token peut etre requis selon la configuration

**Criteres de validation** :
- [ ] Sans DASHBOARD_TOKEN dans .env, un token est auto-genere et affiche dans les logs
- [ ] Avec DASHBOARD_TOKEN dans .env, le token personnalise est utilise
- [ ] Le header Content-Security-Policy est present sur toutes les reponses

**Verification du header CSP** :
```bash
curl -I http://127.0.0.1:8888/
```
Verifier la presence de `content-security-policy` dans les headers de reponse.

---

## TC-061 : Routes debug protegees

**Objectif** : Verifier que les routes de debug ne sont accessibles que lorsque `DEBUG=true` est configure.

### Cas 1 : DEBUG non defini ou false

**Etapes** :

1. S'assurer que `DEBUG` n'est PAS dans `.env` (ou est egal a `false`)
2. Lancer le serveur
3. Tester l'acces aux routes debug :
   ```bash
   curl http://127.0.0.1:8888/api/debug/wyylde
   ```
   ```bash
   curl http://127.0.0.1:8888/api/debug-sidebar/wyylde
   ```
   ```bash
   curl -X POST http://127.0.0.1:8888/api/reload
   ```
   ```bash
   curl -X POST http://127.0.0.1:8888/api/explore/wyylde
   ```

**Resultat attendu** : Toutes ces routes doivent retourner un code 404 (Not Found) ou une erreur indiquant que la route n'existe pas.

### Cas 2 : DEBUG=true

**Etapes** :

1. Ajouter dans `.env` :
   ```
   DEBUG=true
   ```
2. Relancer le serveur
3. Retester les memes routes

**Resultat attendu** : Les routes sont accessibles et retournent des donnees (ou une erreur "not_connected" si le navigateur n'est pas ouvert).

**Routes debug a tester** :

| Route | Methode | Description |
|-------|---------|-------------|
| `/api/debug/{platform}` | GET | Debug general (liens, boutons, images, cartes) |
| `/api/debug-sidebar/{platform}` | GET | Debug sidebar (discussions, boutons) |
| `/api/debug-chat/{platform}` | GET | Debug chat (editeurs, messages) |
| `/api/debug-mailbox/{platform}` | GET | Debug mailbox (conversations, DOM) |
| `/api/debug-unread-sidebar/{platform}` | GET | Debug non-lus sidebar |
| `/api/debug-profile/{platform}` | GET | Debug profil (boutons, icones) |
| `/api/test-message/{platform}` | POST | Test flow message complet |
| `/api/test-click/{platform}` | POST | Test resultats recherche |
| `/api/test-sidebar-buttons/{platform}` | GET | Test boutons sidebar |
| `/api/explore/{platform}` | POST | Exploration complete du site |
| `/api/reload` | POST | Hot-reload des modules |

**Criteres de validation** :
- [ ] Sans DEBUG=true, toutes les routes debug retournent 404
- [ ] Avec DEBUG=true, les routes debug sont accessibles
- [ ] La route `/api/reload` recharge les modules sans fermer le navigateur

---

## TC-062 : Filtre de securite IA (anti-fuite)

**Objectif** : Verifier que les messages generes par l'IA ne contiennent pas de "fuites" revelant qu'il s'agit d'un bot.

**Etapes** :

1. Lancer un envoi de messages :
   ```bash
   curl -X POST http://127.0.0.1:8888/api/messages/wyylde \
     -H "Content-Type: application/json" \
     -d '{"style": "auto"}'
   ```
2. Observer les logs du serveur
3. Verifier les messages envoyes dans le log d'activite

**Patterns bloques** :
Le filtre de securite rejette automatiquement tout message contenant :
- "en tant qu'ia" / "en tant qu'assistant"
- "je suis un assistant" / "je suis une ia"
- "openai" / "chatgpt" / "gpt-4" / "gpt-3"
- "language model" / "as an ai"
- "je suis programme" / "cette conversation est fictive"
- "ceci est un message genere"
- "je ne suis pas une vraie personne"
- Et d'autres patterns similaires

**Verification dans les logs** :
Si un message est bloque, les logs affichent :
```
WARNING: AI message rejected: matched bad pattern 'PATTERN' in: debut du message...
```
Dans ce cas, le message n'est PAS envoye.

**Verification de la troncature** :
Les messages sont automatiquement tronques a 500 caracteres maximum. Si un message depasse cette limite, les logs indiquent :
```
INFO: AI message truncated to N chars (max 500)
```

**Criteres de validation** :
- [ ] Aucun message envoye ne contient de reference a l'IA, ChatGPT, ou OpenAI
- [ ] Les logs montrent le filtre en action si un mauvais pattern est detecte
- [ ] Les messages trop longs sont tronques proprement (a la derniere phrase complete)
- [ ] Un message rejete ne declenche PAS d'envoi (le bot passe au profil suivant)
- [ ] Les messages vides ou null sont rejetes avec un warning dans les logs
