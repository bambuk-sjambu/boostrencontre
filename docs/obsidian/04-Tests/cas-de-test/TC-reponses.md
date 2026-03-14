# Tests des reponses et auto-reply (TC-040 a TC-043)

Prerequis : [[04-Tests/prerequis|Prerequis]] -- serveur lance, navigateur ouvert, connecte sur Wyylde, profil IA renseigne.

---

## TC-040 : Reponse aux discussions non lues (sidebar)

**Objectif** : Verifier le flow complet de reponse automatique aux messages non lus dans le sidebar droit de Wyylde.

**Prerequis specifique** : Avoir au moins 1 message non lu dans le sidebar de Wyylde. La section "Discussions non lues" doit etre visible avec un badge indiquant le nombre.

**Etapes** :

1. Verifier visuellement dans le navigateur Playwright qu'il y a des discussions non lues (bouton jaune-vert dans le sidebar droit, a x~1006)
2. Lancer les reponses via le dashboard (bouton "Repondre Non-Lus Sidebar") ou via l'API :
   ```bash
   curl -X POST http://127.0.0.1:8888/api/replies/wyylde \
     -H "Content-Type: application/json" \
     -d '{"style": "auto"}'
   ```
   Reponse attendue :
   ```json
   {"status": "started", "message": "Reponses aux non-lus sidebar lancees sur wyylde !"}
   ```
3. Observer le navigateur Playwright pendant l'execution
4. Surveiller les logs du serveur

**Ce qu'il faut observer dans le navigateur** :

1. Le bot detecte la section "Discussions non lues" (bouton jaune-vert a droite)
2. Il clique dessus pour deplier la liste des pseudos non lus
3. Pour chaque pseudo non lu :
   a. Il clique sur le pseudo pour ouvrir la conversation
   b. Il lit le contenu de la conversation existante
   c. Il ouvre le profil du correspondant dans un nouvel onglet pour lire sa bio
   d. Il genere une reponse contextuelle (qui rebondit sur le dernier message recu)
   e. Il tape la reponse dans l'editeur TipTap du chat sidebar
   f. Il clique sur le bouton d'envoi
4. Il passe au pseudo suivant

**Ce qu'il faut observer dans les logs** :

- `Unread section found` -- section non lue detectee
- `Found N unread pseudos` -- nombre de pseudos non lus
- `Reading conversation for: NomDuPseudo` -- lecture de la conversation
- `Profile info: ...` -- informations du profil extraites
- `Reply sent to NomDuPseudo: debut de la reponse...` -- reponse envoyee

**Verification du statut** :
```bash
curl http://127.0.0.1:8888/api/job-status/replies/wyylde
```

**Resultat attendu** :
- Chaque discussion non lue recoit une reponse pertinente
- Les reponses rebondissent sur le contenu de la conversation
- Les reponses ne commencent pas par "Salut" ou "Bonjour" (c'est une conversation en cours)

**Criteres de validation** :
- [ ] Le bot detecte correctement la section "non lues" dans le sidebar
- [ ] Le bot deplie la section si elle est repliee
- [ ] Chaque conversation non lue est ouverte
- [ ] La reponse generee rebondit sur le dernier message de l'interlocuteur
- [ ] La reponse ne commence PAS par une formule d'accueil (Salut, Hey, Coucou)
- [ ] La reponse fait 1-3 phrases (50 mots max)
- [ ] Le tutoiement/vouvoiement est correct selon le type de profil
- [ ] La reponse est coherente avec l'historique de la conversation
- [ ] L'activite est enregistree dans le log

**Verification synchrone** (alternative sans job async) :
```bash
curl -X POST http://127.0.0.1:8888/api/check-replies/wyylde
```
Cette variante est synchrone : la reponse ne revient qu'une fois toutes les discussions traitees.
Reponse attendue : `{"status": "done", "replied": [...], "count": N}`

---

## TC-041 : Anti-doublon

**Objectif** : Verifier que le bot ne repond pas deux fois a la meme conversation dans un intervalle court.

**Etapes** :

1. Lancer les reponses une premiere fois :
   ```bash
   curl -X POST http://127.0.0.1:8888/api/check-replies/wyylde
   ```
   Noter le nombre de reponses envoyees.

2. Relancer immediatement les reponses :
   ```bash
   curl -X POST http://127.0.0.1:8888/api/check-replies/wyylde
   ```

**Resultat attendu** :
- La deuxieme execution ne renvoie aucune reponse (ou moins que la premiere)
- Les logs montrent "Already replied recently" ou "Our last message detected" pour les conversations deja traitees

**Criteres de validation** :
- [ ] Le bot detecte qu'il a deja repondu recemment (dans les 3 dernieres minutes)
- [ ] Le bot detecte que c'est lui qui a envoye le dernier message
- [ ] Aucun doublon n'est envoye
- [ ] Les logs indiquent clairement pourquoi chaque conversation est skippee

**Mecanismes anti-doublon verifies** :
1. `_replied_recently()` -- verifie si une reponse a ete envoyee dans les 3 dernieres minutes
2. `detect_our_last_message()` -- verifie si le dernier message de la conversation est le notre
3. `_get_last_sent_message()` -- compare le contenu du dernier message envoye

---

## TC-042 : Detection de rejet

**Objectif** : Verifier que le bot arrete de repondre quand l'interlocuteur rejette la conversation.

**Prerequis** : Avoir une conversation ou quelqu'un a dit "non merci", "stop", "pas interesse", "desole", ou equivalent.

**Etapes** :

1. Identifier une conversation contenant un rejet dans le sidebar Wyylde
2. Lancer les reponses :
   ```bash
   curl -X POST http://127.0.0.1:8888/api/check-replies/wyylde
   ```
3. Observer les logs du serveur

**Resultat attendu** :
- Le bot detecte le rejet dans la conversation
- Le log affiche "Rejection detected" ou equivalent
- Aucune reponse n'est envoyee pour cette conversation
- Le contact est marque comme "rejected" dans la base de donnees

**Criteres de validation** :
- [ ] Le mot-cle de rejet est detecte dans le texte de la conversation
- [ ] Les logs indiquent "rejected" avec le nom du pseudo
- [ ] La reponse n'est PAS envoyee
- [ ] Le contact est enregistre comme rejete dans activity_log (action = "rejected")
- [ ] Les prochaines executions skipperont aussi ce contact

**Autre mecanisme de blocage** :
- Si la conversation affiche "filtres des messages" (= bloque par Wyylde), le bot doit aussi skipper
- Les logs indiqueront "message filter detected" ou equivalent

---

## TC-043 : Auto-reply (boucle continue)

**Objectif** : Tester le mode auto-reply qui surveille en continu les messages non lus et repond automatiquement.

**Etapes** :

1. Activer l'auto-reply via le dashboard (bouton "Veille Auto-Reply - Wyylde") ou via l'API :
   ```bash
   curl -X POST http://127.0.0.1:8888/api/auto-reply/wyylde \
     -H "Content-Type: application/json" \
     -d '{"action": "start", "interval": 60, "style": "auto"}'
   ```
   Reponse attendue :
   ```json
   {"status": "started", "interval": 60}
   ```

2. Observer les logs du serveur : toutes les 60 secondes, une verification des non-lus doit apparaitre :
   ```
   INFO: Auto-reply started for wyylde (every 60s)
   ```

3. Attendre au moins 2-3 cycles (2-3 minutes) pour verifier que la boucle fonctionne

4. Desactiver l'auto-reply :
   ```bash
   curl -X POST http://127.0.0.1:8888/api/auto-reply/wyylde \
     -H "Content-Type: application/json" \
     -d '{"action": "stop"}'
   ```
   Reponse attendue :
   ```json
   {"status": "stopped"}
   ```

**Resultat attendu** :
- La boucle se lance et verifie les non-lus a intervalle regulier
- Si des messages non lus arrivent pendant la veille, ils sont traites automatiquement
- La boucle s'arrete proprement quand on envoie "stop"

**Criteres de validation** :
- [ ] La boucle demarre avec le message "Auto-reply started" dans les logs
- [ ] Les verifications ont lieu toutes les 60 secondes (ou l'intervalle configure)
- [ ] Si un nouveau message non lu arrive, il est traite au cycle suivant
- [ ] La boucle s'arrete proprement avec le message "Auto-reply stopped"
- [ ] Le bouton du dashboard change de texte ("STOP Veille") quand la veille est active
- [ ] Un second appel "start" ne cree pas de doublon de boucle
- [ ] Les memes protections anti-doublon et anti-rejet s'appliquent

**Verification dans le dashboard** :
- Le bouton doit passer de "Veille Auto-Reply - Wyylde" (vert) a "STOP Veille - Wyylde" (rouge) quand la veille est active
