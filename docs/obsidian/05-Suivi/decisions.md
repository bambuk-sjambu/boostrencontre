# Decisions techniques

#boostrencontre #decisions #architecture #suivi

---

## Pattern mixin pour Wyylde

**Contexte** : le fichier `wyylde.py` monolithique depassait 1500 lignes et devenait difficile a maintenir.

**Decision** : eclater la classe `WyyldePlatform` en 4 mixins (ProfileMixin, MessagingMixin, SearchMixin, SidebarMixin) dans un package `wyylde/`.

**Justification** :
- Chaque mixin a une responsabilite unique (lecture profil, envoi messages, recherche, sidebar)
- Les selecteurs CSS sont centralises dans `selectors.py`
- La classe principale compose les mixins par heritage multiple
- Chaque fichier reste sous 500 lignes

**Alternatives envisagees** :
- Composition par delegation : plus verbeux, necessite de passer `self` partout
- Fichier unique avec sections : ne resout pas le probleme de taille

---

## bot_engine.py comme facade de re-exports

**Contexte** : `bot_engine.py` contenait toute la logique metier (2363 lignes). Beaucoup de code externe l'importait directement.

**Decision** : extraire la logique dans `actions/` et garder `bot_engine.py` comme facade de re-exports (63 lignes).

**Justification** :
- Zero changement necessaire dans le code qui importe depuis `bot_engine`
- La logique est dans des modules dedies faciles a tester
- Le fichier facade ne fait que des `from ... import ...`

---

## Delais gaussiens

**Contexte** : les delais fixes entre actions sont facilement detectables par les systemes anti-bot.

**Decision** : utiliser une distribution gaussienne pour les delais (`_human_delay`), avec pauses longues aleatoires toutes les 5-10 actions.

**Justification** :
- Un humain ne clique pas avec un timing regulier
- La distribution gaussienne produit des valeurs concentrees autour de la moyenne mais avec de la variance
- Les pauses longues simulent un utilisateur qui regarde autre chose
- 95% des valeurs tombent entre min et max

**Parametres** :
- Delai court : moyenne = `(min+max)/2`, ecart-type = `(max-min)/4`
- Pause longue : 8 a 45 secondes, toutes les 5 a 10 actions

---

## gpt-4o-mini comme modele IA

**Contexte** : choix du modele OpenAI pour la generation de messages.

**Decision** : utiliser `gpt-4o-mini` pour tous les appels (premiers messages, reponses, enrichissement profil).

**Justification** :
- Cout 10x inferieur a GPT-4o pour des messages courts
- Vitesse de reponse rapide (< 2 secondes)
- Qualite suffisante pour des messages de 2-3 phrases
- Le prompt est suffisamment structure pour compenser la puissance moindre
- Possibilite de passer a GPT-4o plus tard si necessaire

**Max tokens** : 300 pour les messages, 500 pour l'enrichissement profil.

---

## Scoring sur 5 criteres

**Contexte** : besoin de prioriser les profils a contacter.

**Decision** : score sur 100 points repartis en 5 criteres : desirs communs (30), completude profil (20), activite recente (15), compatibilite type (20), geographie (15).

**Justification** :
- Les desirs communs sont le critere le plus important pour la compatibilite sur un site libertin
- La completude du profil indique un utilisateur serieux et facilite la generation de messages
- L'activite recente evite de contacter des profils inactifs
- La compatibilite de type filtre les incompatibilites de base
- La geographie est un facteur pratique pour les rencontres reelles

**Grades** : A (>= 80), B (>= 60), C (>= 40), D (< 40). Les profils D sont ignores.

---

## Conversation multi-tour en 4 etapes

**Contexte** : les reponses automatiques generaient des messages sans strategie conversationnelle.

**Decision** : structurer les conversations en 4 etapes progressives (accroche, interet, approfondissement, proposition) avec detection de signaux.

**Justification** :
- Un humain fait naturellement evoluer le ton d'une conversation
- Chaque etape a un objectif precis et un prompt adapte
- La detection de signaux evite de forcer une progression si le destinataire n'est pas receptif
- Le resume de conversation injecte dans le prompt evite les repetitions

---

## SQLite plutot que PostgreSQL

**Contexte** : choix de la base de donnees.

**Decision** : SQLite via aiosqlite.

**Justification** :
- Zero configuration, zero processus serveur
- Un seul utilisateur, pas de concurrence
- Le fichier `boostrencontre.db` est facilement sauvegardable et portable
- Les volumes de donnees sont faibles (quelques milliers de lignes max)
- aiosqlite permet l'async sans bloquer l'event loop

---

## Playwright plutot que Selenium

**Contexte** : choix de l'outil d'automatisation navigateur.

**Decision** : Playwright avec Chromium en mode `headless=false`.

**Justification** :
- API async native (compatible avec asyncio et FastAPI)
- Profils navigateur persistants (cookies, localStorage)
- Meilleure gestion de l'anti-detection que Selenium
- Support natif de l'interception reseau et des screenshots
- `headless=false` pour voir ce que fait le bot et deboguer

---

## Authentification par token auto-genere

**Contexte** : securiser l'acces au dashboard sans systeme de comptes utilisateurs.

**Decision** : generer un token aleatoire au demarrage avec `secrets.token_urlsafe(32)`, affiche dans les logs.

**Justification** :
- Simple et adapte a un usage local mono-utilisateur
- Pas de mot de passe a retenir
- Le token peut etre fixe via la variable d'environnement `DASHBOARD_TOKEN`
- Suffit pour empecher un acces accidentel depuis le reseau local

---

Voir aussi : [[03-Technique/architecture|Architecture]], [[05-Suivi/roadmap|Roadmap]], [[05-Suivi/changelog|Changelog]]

#decisions #architecture #suivi
