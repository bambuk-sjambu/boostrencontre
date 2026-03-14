# Tests des messages IA (TC-030 a TC-033)

Prerequis : [[04-Tests/prerequis|Prerequis]] -- serveur lance, navigateur ouvert, connecte sur Wyylde, profil IA renseigne.

---

## TC-030 : Envoi de premier message IA

**Objectif** : Verifier la generation et l'envoi d'un message IA personnalise a un profil Wyylde.

**Prerequis specifique** : Au moins un profil en ligne dans le chat sidebar, avec une bio remplie de preference.

**Etapes** :

1. Dans le dashboard, selectionner un style dans le dropdown "Style messages" (ex: "romantique")
2. Cliquer sur "Messages IA - Wyylde" ou appeler l'API :
   ```bash
   curl -X POST http://127.0.0.1:8888/api/messages/wyylde \
     -H "Content-Type: application/json" \
     -d '{"style": "romantique"}'
   ```
   Reponse attendue :
   ```json
   {"status": "started", "message": "Messages lances sur wyylde (style: romantique) ! Regarde le navigateur."}
   ```
3. Observer le navigateur Playwright pendant l'execution

**Ce qu'il faut observer dans le navigateur** :

1. Le bot navigue vers les profils en ligne (chat sidebar)
2. Il clique sur un profil pour ouvrir le chat popup
3. Il navigue vers la page profil du membre
4. Il lit les informations du profil (bio, type, age)
5. Il clique sur "Lui ecrire" (bouton avec icone avion)
6. Une popup modale s'ouvre avec un editeur TipTap
7. Un message personnalise est tape caractere par caractere (delay 25ms entre chaque)
8. Le bouton d'envoi (icone avion vers le haut) est clique
9. Le message apparait dans la conversation

**Ce qu'il faut observer dans les logs serveur** :

- `Profile: NomDuProfil | Type | bio=...` -- les infos extraites
- `Message sent to NomDuProfil: debut du message...` -- le message envoye
- Le style utilise et le type de destinataire detecte

**Resultat attendu** :
- Le message est envoye avec succes
- Le message fait reference a la bio du destinataire (personnalise)
- Le message respecte le style choisi (romantique dans cet exemple)

**Verification du statut** :
```bash
curl http://127.0.0.1:8888/api/job-status/messages/wyylde
```

**Criteres de validation** :
- [ ] Le message est tape et envoye dans le navigateur
- [ ] Le message fait reference a un element concret de la bio du destinataire
- [ ] Le message respecte le ton du style choisi
- [ ] Le message fait 2-3 phrases maximum (50 mots max)
- [ ] Le message ne contient PAS de fuite IA ("en tant qu'IA", "ChatGPT", "je suis un programme")
- [ ] Le message utilise le tutoiement pour un profil solo (Homme/Femme)
- [ ] Le message utilise le vouvoiement pour un Couple
- [ ] Le message ne commence PAS par "Salut ca va", "Hey", "Coucou"
- [ ] Le log d'activite enregistre le message avec le nom du profil
- [ ] Le bot ne re-message PAS un profil deja contacte (anti-doublon)

---

## TC-031 : Test de chaque style de communication

**Objectif** : Verifier que chacun des 8 styles genere un message avec le bon ton.

Pour chaque style, envoyer un message et verifier le ton. Il est possible de tester via l'API de recherche pour cibler des profils specifiques :

```bash
curl -X POST http://127.0.0.1:8888/api/message-search/wyylde \
  -H "Content-Type: application/json" \
  -d '{"style": "STYLE_A_TESTER", "count": 1}'
```

### Grille de verification par style

| Style | Commande curl | Ton attendu | A verifier |
|-------|--------------|-------------|------------|
| auto | `'{"style": "auto", "count": 1}'` | IA choisit le meilleur ton | Le style est adapte au profil du destinataire |
| romantique | `'{"style": "romantique", "count": 1}'` | Poetique, emotionnel, chaleureux | Pas de cliches ("tu es belle"), compliments sur la personnalite |
| direct_sexe | `'{"style": "direct_sexe", "count": 1}'` | Franc, desirant, sensuel | Pas vulgaire, respectueux, langage sensuel mais pas porno |
| humoristique | `'{"style": "humoristique", "count": 1}'` | Drole, decale, surprenant | Pas de blagues lourdes, autoderision, jeux de mots |
| intellectuel | `'{"style": "intellectuel", "count": 1}'` | Reflechi, curieux, cultive | Pas pedant, pas une conference, references culturelles |
| aventurier | `'{"style": "aventurier", "count": 1}'` | Dynamique, tourne vers l'action | Propositions concretes, experiences, decouvertes |
| mysterieux | `'{"style": "mystérieux", "count": 1}'` | Intrigant, enigmatique | Sous-entendus elegants, donne envie d'en savoir plus |
| complice | `'{"style": "complice", "count": 1}'` | Familier, decontracte | Comme si on se connaissait, terrain commun, connivence |

**Criteres de validation par style** :
- [ ] auto : le style choisi par l'IA est pertinent par rapport au profil
- [ ] romantique : pas de cliche physique, chaleur emotionnelle
- [ ] direct_sexe : franc mais jamais vulgaire
- [ ] humoristique : fait sourire, pas lourd
- [ ] intellectuel : stimulant sans etre pedant
- [ ] aventurier : propose quelque chose de concret
- [ ] mysterieux : intrigant, pas confus
- [ ] complice : naturel et familier, pas force

---

## TC-032 : Adaptation par type de destinataire

**Objectif** : Verifier que le prompt s'adapte au type de profil du destinataire.

**Etapes** : Pour chaque type, envoyer un message et verifier l'adaptation dans les logs.

### Femme solo

```bash
curl -X POST http://127.0.0.1:8888/api/message-search/wyylde \
  -H "Content-Type: application/json" \
  -d '{"style": "auto", "count": 1, "profile_type": "Femme"}'
```
- Verifier dans les logs : `CONTEXTE DESTINATAIRE` contient "Tu t'adresses a une femme"
- Le message tutoie
- Le ton est respectueux, valorise la personnalite

### Homme

```bash
curl -X POST http://127.0.0.1:8888/api/message-search/wyylde \
  -H "Content-Type: application/json" \
  -d '{"style": "auto", "count": 1, "profile_type": "Homme"}'
```
- Verifier : contexte "Tu t'adresses a un homme"
- Ton direct et naturel
- Tutoiement

### Couple

```bash
curl -X POST http://127.0.0.1:8888/api/message-search/wyylde \
  -H "Content-Type: application/json" \
  -d '{"style": "auto", "count": 1, "profile_type": "Couple hétéro"}'
```
- Verifier : contexte "Tu t'adresses a un couple"
- Le message VOUVOIE (vous, votre, vos)
- Evoque la complicite et le partage

### Couple F Bi

```bash
curl -X POST http://127.0.0.1:8888/api/message-search/wyylde \
  -H "Content-Type: application/json" \
  -d '{"style": "auto", "count": 1, "profile_type": "Couple F Bi"}'
```
- Verifier : contexte contient "femme bisexuelle" et "complicite feminine"
- Le message VOUVOIE
- Possibilite d'evoquer la complicite feminine

**Criteres de validation** :
- [ ] Femme : tutoiement, respect, valorisation personnalite
- [ ] Homme : tutoiement, ton direct
- [ ] Couple : vouvoiement, mention du partage
- [ ] Couple F Bi : vouvoiement + reference complicite feminine possible

---

## TC-033 : Detection des desirs dans la bio

**Objectif** : Verifier que les desirs mentionnes dans la bio du destinataire sont detectes et influencent le message.

**Prerequis** : Trouver un profil dont la bio mentionne des mots-cles comme "echange", "BDSM", "trio", "gang bang", "exhibition", "fetichisme", "feeling", "papouilles", etc.

**Etapes** :

1. Lancer un envoi de message depuis la recherche avec des filtres d'envies :
   ```bash
   curl -X POST http://127.0.0.1:8888/api/message-search/wyylde \
     -H "Content-Type: application/json" \
     -d '{"style": "auto", "count": 1, "desires": ["Gang bang"]}'
   ```
2. Observer les logs du serveur

**Ce qu'il faut observer dans les logs** :
- La ligne `Ses envies detectees : ...` dans le prompt
- Le template d'approche auto-selectionne (si applicable)
- Le message final qui evoque subtilement les centres d'interet

**Verification avec template d'approche** :
```bash
curl -X POST http://127.0.0.1:8888/api/message-search/wyylde \
  -H "Content-Type: application/json" \
  -d '{"style": "auto", "count": 1, "desires": ["Feeling"], "approach_template": "J aime la connexion emotionnelle avant tout, les regards qui disent tout sans un mot..."}'
```
Le message genere doit s'inspirer du template fourni tout en restant personnalise.

**Criteres de validation** :
- [ ] Les logs montrent les desirs detectes dans la bio
- [ ] Le message fait subtilement reference aux centres d'interet detectes
- [ ] Le message n'est pas explicite de maniere inappropriee
- [ ] Le template d'approche influence le ton du message quand il est fourni
- [ ] Sans template, l'IA choisit automatiquement une approche pertinente

**Desirs detectables** (mots-cles dans la bio) :
- Gang bang
- Echangisme
- BDSM
- Exhibition
- Feeling
- Fetichisme
- Hard
- Papouilles
- Pluralite
