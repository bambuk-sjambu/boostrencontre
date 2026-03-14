# Tests du dashboard (TC-050 a TC-052)

Prerequis : [[04-Tests/prerequis|Prerequis]] -- serveur lance.

---

## TC-050 : Affichage du dashboard

**Objectif** : Verifier que le dashboard s'affiche correctement avec tous ses elements.

**Etapes** :

1. Ouvrir http://127.0.0.1:8888 dans un navigateur classique
2. Verifier la presence de chaque section

**Elements a verifier** :

### En-tete
- [ ] Titre "BoostRencontre" affiche
- [ ] Liens de navigation : "Dashboard" et "Mon Profil IA"
- [ ] Instructions en 3 etapes (1. Ouvrir navigateur, 2. Se connecter, 3. Lancer actions)

### Section Plateformes
- [ ] 3 cartes : Tinder, Meetic, Wyylde
- [ ] Chaque carte est cliquable
- [ ] Le statut initial est "Deconnecte" (en rouge)
- [ ] Apres connexion, le statut passe a "Connecte" (en vert)

### Section Filtre Wyylde
- [ ] Dropdown "Type de profil" avec les options : Tous, Couple F Bi (selectionne par defaut), Couple hetero, Couple M Bi, Femme hetero, Femme Bi, Homme hetero, Homme Bi, Travesti
- [ ] Checkboxes "Envies" : Gang bang (coche par defaut), Echangisme, BDSM, Exhibition, Feeling, Fetichisme, Hard, Papouilles, Pluralite
- [ ] Section template (apparait quand au moins une envie est cochee)

### Section Style de communication
- [ ] Dropdown avec les 8 styles : Auto (IA choisit), Romantique, Direct sexe, Humoristique, Intellectuel, Aventurier, Mysterieux, Complice

### Section Actions
- [ ] Boutons "Liker" pour chaque plateforme (Tinder, Meetic, Wyylde)
- [ ] Boutons "Messages IA" pour chaque plateforme
- [ ] Bouton "Messages Recherche - Wyylde"
- [ ] Bouton "Repondre Non-Lus Sidebar - Wyylde"
- [ ] Bouton "Veille Auto-Reply - Wyylde"
- [ ] Lien "Mon Profil IA"

### Section Limites journalieres
- [ ] Dropdown plateforme (Wyylde, Tinder, Meetic)
- [ ] Barres de progression pour chaque type d'action

### Section Parametres
- [ ] Champ "Likes par session" (valeur par defaut ou configuree)
- [ ] Champ "Messages par session"
- [ ] Champ "Delai min (sec)"
- [ ] Champ "Delai max (sec)"
- [ ] Bouton "Sauvegarder"

### Section Statistiques
- [ ] Statistiques du jour : Messages, Reponses, Likes, Follows, Crushes
- [ ] Periode (7 jours) : Envoyes, Reponses recues, Taux reponse
- [ ] Tableau performance par style
- [ ] Graphique d'activite sur 7 jours

### Section Activite recente
- [ ] Tableau avec colonnes : Date, Plateforme, Action, Profil, Message
- [ ] Affiche les dernieres actions ou "Aucune activite" si vide

---

## TC-051 : Configuration des parametres

**Objectif** : Modifier les parametres et verifier qu'ils sont sauvegardes et appliques.

**Etapes** :

1. Ouvrir http://127.0.0.1:8888
2. Dans la section "Parametres" :
   - Modifier "Likes par session" : mettre 5
   - Modifier "Messages par session" : mettre 2
   - Modifier "Delai min" : mettre 4
   - Modifier "Delai max" : mettre 10
3. Cliquer "Sauvegarder"
4. Verifier qu'un message "Parametres sauvegardes" s'affiche en haut

**Verification API** :
```bash
curl -X POST http://127.0.0.1:8888/api/settings \
  -H "Content-Type: application/json" \
  -d '{"likes_per_session": 5, "messages_per_session": 2, "delay_min": 4, "delay_max": 10}'
```

5. Recharger la page
6. Verifier que les nouvelles valeurs sont affichees dans les champs

**Verification d'application** : Lancer un run de likes et verifier que :
- Le nombre de profils visites ne depasse pas 5
- Les delais entre actions sont entre 4 et 10 secondes

**Criteres de validation** :
- [ ] Le message de confirmation s'affiche
- [ ] Apres rechargement, les valeurs sont conservees
- [ ] Les valeurs sont effectivement utilisees lors des runs

---

## TC-052 : Gestion des templates de message

**Objectif** : Creer, modifier et supprimer des templates d'approche.

**Prerequis** : Au moins une "envie" cochee dans la section Filtre (pour que la section templates soit visible).

### Creer un template

**Etapes** :

1. Cocher au moins une envie (ex: "Gang bang")
2. La section template apparait avec un dropdown et une zone de texte
3. Dans le champ "Nom du nouveau template", entrer : "Test approche directe"
4. Dans la zone de texte, entrer : "On a l'air d'avoir les memes envies, ca pourrait etre interessant de se rencontrer..."
5. Cliquer "+ Ajouter"
6. Verifier que le template apparait dans le dropdown

**Verification API** :
```bash
curl "http://127.0.0.1:8888/api/templates?desire=Gang%20bang"
```
Le template cree doit apparaitre dans la liste.

### Modifier un template

1. Selectionner le template dans le dropdown
2. Modifier le contenu dans la zone de texte
3. Cliquer "Sauver"
4. Re-selectionner le template pour verifier que la modification est conservee

### Supprimer un template

1. Selectionner le template dans le dropdown
2. Cliquer "Suppr"
3. Verifier que le template disparait du dropdown

**Verification API** :
```bash
# Creer
curl -X POST http://127.0.0.1:8888/api/templates \
  -H "Content-Type: application/json" \
  -d '{"desire": "Gang bang", "label": "Test API", "content": "Contenu de test"}'

# Lister
curl "http://127.0.0.1:8888/api/templates"

# Supprimer (remplacer ID par l'id retourne)
curl -X DELETE http://127.0.0.1:8888/api/templates/ID
```

**Criteres de validation** :
- [ ] La creation ajoute le template au dropdown
- [ ] La modification est persistee
- [ ] La suppression retire le template du dropdown
- [ ] Les templates sont lies a une categorie d'envie
- [ ] La validation refuse les champs vides (desire, label, content requis)
