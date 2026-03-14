# Securite et protection anti-ban

#boostrencontre #securite #anti-ban #anti-detection

---

## Profils navigateur persistants

Chaque plateforme dispose de son propre profil navigateur stocke sur le disque local :

```
~/.boostrencontre/browser_profiles/{platform}/
```

Ce dossier contient toutes les donnees du navigateur Chromium :
- Cookies de session
- localStorage
- Donnees de cache

Avantages :
- Pas besoin de se reconnecter a chaque lancement
- Le site voit le meme navigateur avec le meme historique
- Les sessions persistent entre les redemarrages de BoostRencontre

Le repertoire est cree avec des permissions restrictives (`mode=0o700` : lecture/ecriture/execution uniquement pour l'utilisateur).

---

## Anti-detection du navigateur

Lors du lancement du navigateur, plusieurs mesures empechent la detection de l'automatisation :

### Arguments Chromium

```
--disable-blink-features=AutomationControlled  (desactive le flag automation)
--no-first-run                                   (pas de page de bienvenue)
--no-default-browser-check                       (pas de verification navigateur par defaut)
```

L'argument `--enable-automation` est explicitement exclu des arguments par defaut (`ignore_default_args=["--enable-automation"]`).

### Scripts d'initialisation

Un script d'initialisation est injecte dans chaque page avant son chargement :

| Protection | Description |
|------------|-------------|
| `navigator.webdriver = false` | Masque la propriete webdriver (normalement `true` en mode automation) |
| Suppression des proprietes `cdc_*` | Supprime les traces du ChromeDriver |
| Permission `notifications` | Renvoie l'etat reel des permissions au lieu d'une valeur par defaut |
| `navigator.plugins = [1,2,3,4,5]` | Simule la presence de plugins (un navigateur automatise en a souvent zero) |
| `navigator.languages = ['fr-FR', 'fr', 'en-US', 'en']` | Definit des langues realistes |

### Configuration du viewport

- Resolution : 1920x1080 (standard)
- Locale : fr-FR (coherent avec un utilisateur francophone)
- Mode : headless=false (navigateur visible, pas en mode invisible)

---

## Delais et comportement humain

### Delais entre actions

Les delais entre chaque action ne sont pas fixes : ils suivent une distribution gaussienne pour imiter le comportement imprevisible d'un humain.

```
_human_delay(min_s=1.5, max_s=4.0)
  Moyenne = (min + max) / 2
  Ecart-type = (max - min) / 4
  95% des valeurs tombent entre min et max
```

### Longues pauses aleatoires

Toutes les 5 a 10 actions, une pause longue est inseree :

```
_human_delay_with_pauses(min_s=2.0, max_s=5.0)
  Toutes les 5-10 actions : pause de 8 a 45 secondes
  (simule un utilisateur qui regarde autre chose)
  Sinon : delai normal
```

### Saisie au clavier

Les messages sont tapes caractere par caractere avec un delai de 25 millisecondes entre chaque touche (`keyboard.type(message, delay=25)`), ce qui simule une frappe humaine.

### Variations aleatoires

- 10% des profils sont visites sans aucune action (juste navigation)
- 20% des follows sont aleatoirement ignores
- 30% des crush sont aleatoirement ignores

---

## Limites journalieres

Le module `rate_limiter.py` impose des limites quotidiennes pour eviter de declencher les systemes de detection des sites :

| Action | Limite par jour |
|--------|-----------------|
| Likes | 100 |
| Messages | 20 |
| Reponses | 30 |
| Follows | 80 |
| Crush | 50 |

### Fonctionnement

- Chaque action est comptee dans la table `daily_counters` (cle : date + plateforme + action)
- Avant chaque session de likes, la limite est verifiee : si atteinte, la session est annulee
- Le nombre d'actions par session est plafonne au quota restant
- Les compteurs de plus de 7 jours sont automatiquement purges

### Parametres de session

En complement des limites journalieres, les parametres de session limitent le nombre d'actions par execution :

| Parametre | Defaut | Limites serveur |
|-----------|--------|-----------------|
| likes_per_session | 50 | 1 - 500 |
| messages_per_session | 3 | 1 - 50 |
| delay_min | 3 | 0 - 60 |
| delay_max | 8 | 1 - 120 |

---

## Token d'acces au dashboard

### Generation

Un token d'acces securise est genere automatiquement au demarrage si la variable d'environnement `DASHBOARD_TOKEN` n'est pas definie :

```
DASHBOARD_TOKEN = secrets.token_urlsafe(32)
```

Le token est affiche dans les logs au demarrage pour que l'utilisateur puisse le recuperer.

### Verification

Toutes les routes `/api/*` sont protegees par le middleware d'authentification. Chaque requete doit inclure le header :

```
Authorization: Bearer {DASHBOARD_TOKEN}
```

Si le header est absent ou invalide, la requete recoit une reponse `401 Unauthorized`.

### Limitation de la taille des requetes

Les requetes POST/PUT/PATCH sont limitees a 10 Ko (`MAX_BODY_SIZE = 10_000`) pour prevenir les attaques par envoi de donnees massives. Au-dela, la requete recoit une reponse `413 Body Too Large`.

---

## CORS et headers de securite

### CORS restrictif

Seules les origines locales sont autorisees :
- `http://127.0.0.1:8888`
- `http://localhost:8888`

### Headers de securite

Chaque reponse HTTP inclut les headers suivants :

| Header | Valeur | Protection |
|--------|--------|------------|
| `X-Content-Type-Options` | `nosniff` | Empeche le navigateur de deviner le type MIME |
| `X-Frame-Options` | `DENY` | Empeche l'affichage dans une iframe (clickjacking) |
| `X-XSS-Protection` | `1; mode=block` | Active le filtre XSS du navigateur |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Limite les informations de referer |
| `Content-Security-Policy` | `default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'` | Restreint les sources de contenu |

---

## Whitelist des plateformes

Les noms de plateformes sont valides contre une whitelist :

```python
ALLOWED_PLATFORMS = {"tinder", "meetic", "wyylde"}
```

Toute requete avec un nom de plateforme non reconnu recoit une reponse `400 invalid_platform`.

---

## Routes debug protegees

Les routes de debug (`/api/debug/*`, `/api/test-*`, `/api/explore/*`, `/api/reload`) ne sont disponibles que si la variable d'environnement `DEBUG` est definie a `true` :

```bash
DEBUG=true venv/bin/python main.py
```

En production (sans `DEBUG=true`), ces routes n'existent pas dans l'application.

---

## Filtre de securite IA

Le module `ai_messages.py` inclut un filtre qui empeche l'IA de reveler sa nature :

### Patterns bloques

| Categorie | Exemples |
|-----------|----------|
| Aveux IA | "en tant qu'IA", "je suis un assistant", "en tant que modele" |
| References techniques | "openai", "chatgpt", "gpt-4", "gpt-3", "language model" |
| Confusion de role | "je suis programme", "cette conversation est fictive", "je ne suis pas une vraie personne" |
| Echec de comprehension | "je ne vois pas", "pas de conversation", "je ne trouve pas" |

Si un message contient l'un de ces patterns (insensible a la casse), il est **rejete** et aucun message n'est envoye.

### Troncature

Les messages de plus de 500 caracteres sont tronques a la derniere phrase complete dans la limite.

---

## Sanitisation des donnees profil

Le module `profile_schema.py` nettoie toutes les donnees du profil utilisateur :

- Suppression des caracteres de controle (null bytes, etc.)
- Echappement HTML (`html.escape`) pour prevenir les injections XSS
- Troncature a la longueur maximum definie pour chaque champ
- Validation optionnelle des champs requis

---

## Minimisation de la fenetre

Apres le lancement du navigateur, la fenetre Chromium est automatiquement minimisee (via `xdotool windowminimize` sur Linux) pour ne pas encombrer le bureau. Le navigateur continue de fonctionner en arriere-plan.

---

Voir aussi : [[02-Fonctionnalites/automatisation-likes|Automatisation des likes]], [[02-Fonctionnalites/reponses-automatiques|Reponses automatiques]], [[01-Produit/guide-utilisation|Guide d'utilisation]]
