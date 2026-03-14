# Changelog

#boostrencontre #changelog #suivi

---

## 2026-03-10 -- Refactoring majeur et nouvelles fonctionnalites

### Refactoring architecture

- **bot_engine.py** : passe de 2363 lignes a 63 lignes (re-exports uniquement)
- **app.py** : passe de 1477 lignes a 203 lignes (routes extraites dans `routes/`)
- **wyylde.py** : eclate en package avec 6 fichiers (pattern mixin)
- **Logique metier** : extraite dans `actions/` (likes, messages, replies, auto_reply)
- **Routes** : extraites dans `routes/` (browser, likes, messages, replies, profile, settings, stats, debug, etc.)

### Nouvelles fonctionnalites

- **Scoring de profils** : score de compatibilite sur 100 points, 5 criteres (desirs communs, completude, activite, type, geographie), grades A-D, suggestion automatique du style de message
- **Conversation multi-tour** : 4 etapes (accroche, interet, approfondissement, proposition), historique en DB, prompt adaptatif par etape, detection de signaux d'interet et de desinteret
- **Mode campagne** : creation de campagnes avec criteres de ciblage, funnel de contacts (pending, contacted, replied, conversation, met, rejected, skipped), statistiques de conversion
- **Templates d'approche personnalisables** : creation, edition et suppression de templates par categorie de desir depuis le dashboard
- **Statistiques avancees** : stats par style, par jour, taux de reponse, conversations recentes

### Securite

- **Authentification** : token auto-genere au demarrage (`secrets.token_urlsafe(32)`), header `Authorization: Bearer`
- **Routes debug protegees** : accessibles uniquement avec `DEBUG=true`
- **Headers de securite** : CSP, X-Frame-Options, X-Content-Type-Options, X-XSS-Protection
- **CORS restrictif** : uniquement localhost:8888
- **Limitation taille requetes** : 10 Ko max
- **Sanitisation profil** : echappement HTML, troncature, validation longueur
- **Donnees personnelles** : retirees du code source (plus de pseudo ni de bio en dur)

### Tests

- Passage de 44 a 366 tests automatises
- Couverture des nouvelles fonctionnalites (scoring, conversations, campagnes)
- Tests de securite (auth, headers, limites)

### Documentation

- Reorganisation complete du vault Obsidian en 6 sections
- Creation de la documentation scoring, conversation multi-tour, mode campagne
- Mise a jour de tous les liens internes

---

## 2026-03-07 -- Reponses automatiques sidebar

- Implementation de `reply_to_unread_sidebar()` dans bot_engine.py
- Detection des discussions non lues via le bouton jaune-vert du sidebar
- Gestion de l'etat replie/deplie de la section non lues
- Anti-doublon sur les reponses (verification 3 minutes, dernier expediteur, base de donnees)
- Detection de rejet automatique (15+ patterns de rejet)
- Detection de blocage ("filtres des messages")
- Exploration du profil dans un nouvel onglet pour enrichir le prompt de reponse

---

## 2026-03-05 -- Messages IA et profil

- 8 styles de communication implementes
- 13 templates d'approche integres
- Detection automatique des desirs dans la bio
- Personnalisation tu/vous selon le type de destinataire
- Contexte adapte par type (Femme, Homme, Couple, Couple F Bi)
- Profil IA avec 10 categories de connaissance
- Enrichissement IA automatique des categories vides
- Extraction du profil depuis le site (Wyylde)

---

## 2026-03-03 -- Fondations

- Serveur FastAPI sur port 8888
- Dashboard web avec cartes des plateformes
- Ouverture navigateur Playwright avec profils persistants
- Detection de connexion automatique
- Automatisation likes (follow + crush) sur Wyylde
- Base SQLite async (aiosqlite)
- Anti-detection navigateur (webdriver, plugins, langues)

---

Voir aussi : [[05-Suivi/roadmap|Roadmap]], [[05-Suivi/decisions|Decisions techniques]]

#changelog #suivi
