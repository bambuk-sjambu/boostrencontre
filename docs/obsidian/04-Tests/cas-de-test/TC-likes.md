# Tests des likes (TC-020 a TC-021)

Prerequis : [[04-Tests/prerequis|Prerequis]] -- serveur lance, navigateur ouvert, connecte sur Wyylde, profil IA renseigne.

---

## TC-020 : Lancer les likes (follow + crush)

**Objectif** : Verifier le flow complet de likes : navigation vers les profils en ligne, follow et crush.

**Prerequis specifique** : Au moins quelques profils en ligne visibles dans le chat sidebar de Wyylde.

**Etapes** :

1. Dans le dashboard (http://127.0.0.1:8888), verifier que le statut Wyylde est "Connecte"
2. Lancer les likes via le dashboard (bouton "Liker - Wyylde") ou via l'API :
   ```bash
   curl -X POST http://127.0.0.1:8888/api/likes/wyylde
   ```
   Reponse attendue :
   ```json
   {"status": "started", "message": "Likes lances sur wyylde ! Regarde le navigateur."}
   ```
3. Observer le navigateur Playwright pendant l'execution (les actions sont visibles)
4. Surveiller les logs du serveur dans le terminal

**Ce qu'il faut observer dans le navigateur** :

Le bot execute la sequence suivante pour chaque profil :
1. Se positionne sur le dashboard Wyylde
2. Clique sur un profil dans le chat sidebar (liste des utilisateurs en ligne)
3. Un chat popup s'ouvre -- le bot clique sur le lien vers la page profil
4. La page du profil s'affiche
5. Le bot clique sur "Suivre" (icone user-plus) -- probabilite 80%
6. Le bot clique sur "Crush" (icone coeur) -- probabilite 70%
7. Le bot revient au dashboard
8. Delai aleatoire entre chaque profil (configurable dans les parametres)
9. Passe au profil suivant

**Resultat attendu** :
- Le bot visite plusieurs profils successivement
- Des actions follow et crush sont executees sur chaque profil
- L'activite apparait dans le log du dashboard apres rechargement de la page

**Verification du statut du job** :
```bash
curl http://127.0.0.1:8888/api/job-status/likes/wyylde
```
- Pendant l'execution : `{"status": "running"}`
- Apres fin : `{"status": "done", "liked": [...], "count": N}`

**Criteres de validation** :
- [ ] Le bot navigue correctement vers les profils
- [ ] Le bouton "Suivre" est clique (visible dans le navigateur et les logs)
- [ ] Le bouton "Crush" est clique (visible dans le navigateur et les logs)
- [ ] Le bot revient au dashboard entre chaque profil
- [ ] Les delais entre actions sont de 2-8 secondes (pas instantane)
- [ ] Le log d'activite affiche les likes avec le nom des profils
- [ ] Le nombre de likes respecte la limite configuree dans les parametres
- [ ] Les popups eventuelles (cookies, modales) sont fermees automatiquement

**Points d'attention** :
- Le bot skip aleatoirement ~10% des profils (simple navigation sans action) pour paraitre humain
- Le bot skip ~20% des follow et ~30% des crush aleatoirement
- Si un profil est deja suivi, le log indique "Already following this profile"
- Les limites journalieres (configurables) empechent de depasser le quota
- Verifier les limites journalieres :
  ```bash
  curl http://127.0.0.1:8888/api/daily-stats/wyylde
  ```

---

## TC-021 : Likes avec filtre de profil

**Objectif** : Verifier que le filtre de type de profil fonctionne correctement.

**Etapes** :

1. Dans le dashboard, selectionner un filtre dans le dropdown "Type de profil" (ex: "Couple F Bi")
2. Lancer les likes via le bouton ou l'API avec filtre :
   ```bash
   curl -X POST http://127.0.0.1:8888/api/likes/wyylde \
     -H "Content-Type: application/json" \
     -d '{"profile_filter": "Couple F Bi"}'
   ```
3. Observer les logs du serveur pour voir le filtrage

**Ce qu'il faut observer dans les logs** :
- La ligne `After filter 'Couple F Bi': N profiles` indique combien de profils correspondent
- Seuls les profils dont le texte contient "Couple F Bi" sont visites

**Resultat attendu** :
- Les logs montrent le nombre de profils apres filtrage
- Seuls les profils du type selectionne sont visites et likes

**Criteres de validation** :
- [ ] Les logs affichent le filtre applique
- [ ] Les profils visites correspondent au filtre (verifier le type dans les logs)
- [ ] Si aucun profil ne correspond, le bot termine proprement avec un message "No profiles matching filter"

**Test avec filtre vide** :
```bash
curl -X POST http://127.0.0.1:8888/api/likes/wyylde \
  -H "Content-Type: application/json" \
  -d '{"profile_filter": ""}'
```
Avec un filtre vide, tous les profils en ligne doivent etre pris en compte.
