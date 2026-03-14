# Tests du profil IA (TC-010 a TC-012)

Prerequis : [[04-Tests/prerequis|Prerequis]] -- serveur lance, navigateur ouvert, connecte sur Wyylde.

---

## TC-010 : Consultation du profil IA

**Objectif** : Verifier que la page de profil IA s'affiche correctement avec tous les champs.

**Etapes** :

1. Ouvrir http://127.0.0.1:8888/profile dans un navigateur classique (Firefox ou Chrome)
2. Verifier que la page s'affiche sans erreur
3. Verifier la presence des champs d'identite :
   - Pseudo
   - Type (dropdown : Homme hetero, Femme Bi, Couple F Bi, etc.)
   - Age
   - Localisation
   - Description (zone de texte)
4. Verifier la presence des 10 categories de profil :
   - Passions
   - Pratiques
   - Personnalite
   - Physique
   - Etudes/Metier
   - Voyages
   - Musique/Culture
   - Sport
   - Humour
   - Valeurs
5. Verifier la presence du bouton "Sauvegarder"
6. Verifier la presence du bouton "Enrichir avec l'IA"

**Resultat attendu** : Page affichee avec tous les champs mentionnes.

**Verification API** :
```bash
curl http://127.0.0.1:8888/api/user-profile
```
Doit retourner un JSON avec les cles `profile` et `messages_sent`.

**Criteres de validation** :
- [ ] La page se charge sans erreur 500
- [ ] Les 5 champs d'identite sont visibles
- [ ] Les 10 categories de profil sont visibles
- [ ] Les boutons "Sauvegarder" et "Enrichir avec l'IA" sont presents

---

## TC-011 : Modification du profil IA

**Objectif** : Modifier le profil IA et verifier que les changements sont persistes en base de donnees.

**Etapes** :

1. Ouvrir http://127.0.0.1:8888/profile
2. Modifier les champs suivants :
   - Pseudo : entrer un pseudo de test (ex: "TestBot42")
   - Description : entrer une description de test (ex: "Profil de test pour validation")
3. Cliquer sur "Sauvegarder"
4. Verifier qu'un message de confirmation s'affiche
5. Recharger la page (F5)
6. Verifier que les modifications sont toujours presentes

**Verification API** :
```bash
curl -X POST http://127.0.0.1:8888/api/user-profile \
  -H "Content-Type: application/json" \
  -d '{"pseudo": "TestBot42", "description": "Profil de test pour validation"}'
```
Reponse attendue : `{"status": "saved", "profile": {...}}`

Puis relire :
```bash
curl http://127.0.0.1:8888/api/user-profile
```
Verifier que `profile.pseudo` vaut "TestBot42".

**Resultat attendu** : Les modifications sont conservees apres rechargement de la page.

**Criteres de validation** :
- [ ] La sauvegarde affiche un message de confirmation
- [ ] Apres rechargement, les nouvelles valeurs sont presentes
- [ ] L'API GET retourne les valeurs modifiees

**Verification des limites** :
- Tenter de sauvegarder un pseudo de plus de 100 caracteres :
  ```bash
  curl -X POST http://127.0.0.1:8888/api/user-profile \
    -H "Content-Type: application/json" \
    -d '{"pseudo": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}'
  ```
  Doit retourner une erreur `pseudo_too_long`.

---

## TC-012 : Enrichissement IA du profil

**Objectif** : Tester la fonctionnalite d'enrichissement automatique du profil via l'API OpenAI.

**Prerequis** :
- `OPENAI_API_KEY` valide dans `.env`
- Idealement, quelques messages deja envoyes (la fonctionnalite analyse les messages passes pour deduire la personnalite)

**Etapes** :

1. Ouvrir http://127.0.0.1:8888/profile
2. Remplir au minimum le pseudo, le type et la description
3. Laisser quelques categories vides (ex: "Personnalite", "Voyages")
4. Cliquer sur "Enrichir avec l'IA"
5. Attendre la reponse (peut prendre 5-10 secondes)
6. Verifier que les categories precedemment vides ont ete remplies avec des suggestions

**Verification API** :
```bash
curl -X POST http://127.0.0.1:8888/api/user-profile/enrich \
  -H "Content-Type: application/json" \
  -d '{"pseudo": "TestBot42", "type": "Homme hetero", "age": "35", "location": "Paris", "description": "Amateur de voyages et de bons vins", "categories": {"passions": "Voyages, oenologie", "pratiques": "", "personnalite": "", "physique": "", "etudes_metier": "", "voyages": "", "musique_culture": "", "sport": "", "humour": "", "valeurs": ""}}'
```
Reponse attendue : `{"status": "enriched", "profile": {...}}`

**Resultat attendu** :
- Les categories vides sont remplies avec des suggestions coherentes
- Les categories deja remplies sont conservees ou enrichies (jamais effacees)
- Le profil enrichi est sauvegarde automatiquement en base

**Criteres de validation** :
- [ ] L'appel n'echoue pas (pas d'erreur 500)
- [ ] Les categories precedemment vides contiennent du texte
- [ ] Le texte genere est coherent avec le pseudo, type et description
- [ ] Les logs serveur montrent un appel OpenAI reussi
- [ ] Apres rechargement de la page, les enrichissements sont presents

**Points d'attention** :
- Cet appel consomme des tokens OpenAI (modele gpt-4o-mini)
- En cas d'erreur API OpenAI, la reponse contient `"status": "error"` avec un message
- Verifier dans les logs serveur qu'il n'y a pas d'erreur de cle API
