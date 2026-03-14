# Messages IA -- Generation de premiers messages personnalises

#boostrencontre #messages #ia #openai #styles

---

## Principe

BoostRencontre genere des premiers messages uniques et personnalises pour chaque destinataire en utilisant l'API OpenAI (modele `gpt-4o-mini`). Chaque message est construit a partir de :

1. Le **profil du destinataire** (pseudo, bio, type, age, localisation, preferences, envies)
2. Le **profil de l'utilisateur** (MY_PROFILE + 10 categories de connaissance)
3. Le **style de communication** choisi (8 styles)
4. Un **template d'approche** optionnel (13 templates)

Le resultat est un message court (2-3 phrases, 50 mots max) qui fait reference a un element concret du profil du destinataire.

---

## Analyse du profil destinataire

Avant de generer un message, le bot extrait les informations suivantes du profil du destinataire :

| Information | Source | Utilisation |
|-------------|--------|-------------|
| Pseudo | Bouton de nom sur la page profil | Personnalisation du message |
| Type | En-tete du profil (Homme/Femme/Couple + orientation) | Tu/vous + contexte adapte |
| Age | En-tete du profil | Contexte |
| Bio / Presentation | Zone de texte principale du profil | Reference a un element concret |
| Localisation | En-tete du profil | Points communs geographiques |
| Preferences | Onglet "Infos" du profil | Orientation, pratiques, situation |
| Envies / Desirs | Tags sur l'onglet "Infos" (BDSM, Echangisme, etc.) | Adaptation du ton |

### Detection des envies dans la bio

Le systeme scanne automatiquement la bio du destinataire pour detecter des mots-cles lies aux categories de desirs :

| Categorie | Mots-cles detectes |
|-----------|-------------------|
| Gang bang | gang, gb, gangbang, multi |
| Echangisme | echange, echangisme, swap, couple echangiste |
| BDSM | bdsm, domination, soumission, dom, sub, maitre, bondage |
| Exhibition | exhibition, exhib, voyeur, voyeurisme |
| Feeling | feeling, connexion, complicite, affinite |
| Fetichisme | fetich, pieds, latex, cuir, nylon, talons |
| Hard | hard, extreme, fist, double |
| Papouilles | papouille, tendresse, caresse, douceur, sensuel, massage |
| Pluralite | trio, trouple, plan a trois, melangisme |

Les envies detectees sont integrees subtilement dans le prompt de generation.

### Personnalisation tu/vous

Le systeme adapte automatiquement le tutoiement ou le vouvoiement selon le type de destinataire :

- **Couple** (tout type) : vouvoiement systematique ("vous", "votre", "vos")
- **Homme ou Femme seul(e)** : tutoiement ("tu", "ton", "ta")

### Contexte adapte par type de destinataire

Un paragraphe de contexte supplementaire est ajoute au prompt selon le type :

- **Femme** : respect de l'espace, interet pour la personnalite, pas de compliments physiques directs
- **Homme** : ton direct et naturel, franchise et humour
- **Couple** : vouvoiement, respect de la dynamique a deux, energie complementaire
- **Couple F Bi** : idem couple, avec reference possible a la complicite feminine

---

## Les 8 styles de communication

Chaque style produit un type de message different. Le style est choisi dans le dashboard via un menu deroulant.

### auto
L'IA analyse le profil du destinataire et choisit automatiquement le ton le plus adapte parmi tous les styles disponibles. Si le profil est explicite, le ton sera plus direct ; si le profil est poetique ou discret, le ton sera plus subtil.

### romantique
Messages doux et attentionnes. Interet sincere pour la personne, compliments subtils sur la personnalite ou ce qu'elle degage. Atmosphere intime et bienveillante, recherche de connexion emotionnelle. Evite les cliches type "tu es la plus belle".

### direct_sexe
Messages directs et assumes sur le desir, sans detour ni fausse pudeur. Dans le contexte d'un site libertin entre adultes consentants. Evoque le plaisir et l'attirance de maniere franche mais jamais vulgaire. Pas de vocabulaire porno, mais un langage sensuel et affirme.

### humoristique
Messages droles, decales et surprenants. Humour pour briser la glace et creer une connivence immediate. Autoderision, jeux de mots malins, references inattendues. Evite l'humour lourd ou les vannes sur le physique. Ton leger qui donne envie de repondre.

### intellectuel
Messages curieux, cultives et stimulants. Questions qui font reflechir, reflexions originales en lien avec le profil. Culture sans pedanterie. Liens entre centres d'interet et sujets plus larges (philosophie, art, voyages, societe).

### aventurier
Messages spontanes, energiques, tournes vers l'action. Propose une idee, une experience, un plan concret. Evoque des experiences passees ou des envies futures qui donnent envie de suivre. Enchainement de moments forts et de decouvertes.

### mysterieux
Messages intrigants et enigmatiques. Ne devoile pas tout, laisse planer un mystere. Phrases suggestives, sous-entendus elegants, formulations qui ouvrent l'imagination. Le mystere doit etre attirant, pas frustrant.

### complice
Messages chaleureux et familiers, comme si vous vous connaissiez deja. Complicite immediate par un terrain commun ou une reaction a un detail du profil. Ton decontracte, bienveillant et inclusif. Confiance sans distance formelle.

---

## Les 13 templates d'approche

Les templates d'approche definissent un angle ou une intention pour le premier message. L'IA s'en inspire pour construire son message en l'adaptant au profil du destinataire.

| Template | Description | Exemple de ton |
|----------|-------------|----------------|
| **Complicite intellectuelle** | Engage sur les centres d'interet, la culture, les idees | "Ta passion pour [X] m'interpelle..." |
| **Aventure sensuelle** | Evoque le desir et l'attirance de maniere assumee mais elegante | "Ton profil degage quelque chose de magnetique..." |
| **Humour decale** | Accroche avec une touche d'humour inattendu ou d'autoderision | "Je vais etre honnete : j'ai passe 5 minutes..." |
| **Connexion emotionnelle** | Cherche un lien intime et authentique des le premier message | "Ce que tu ecris sur [X] resonne vraiment avec moi..." |
| **Proposition directe** | Va droit au but avec clarte et respect | "Pas fan des longs echanges... je propose un verre" |
| **Mystere attirant** | Intrigue sans tout devoiler, sous-entendus elegants | "J'ai une theorie sur toi... mais je la garde" |
| **Terrain commun** | Identifie un point commun concret et construit le message autour | "[Lieu/activite] aussi ? On a deja un point commun" |
| **Compliment precis** | Compliment specifique et original sur la bio, jamais sur le physique | "J'aime la facon dont tu parles de [X]..." |
| **Taquin seducteur** | Leger, joueur, legerement provocateur avec bienveillance | "Ton profil est presque parfait... il manque un detail" |
| **Experience partagee** | Propose ou evoque une experience a vivre ensemble | "J'imagine deja la scene : un bar a cocktails..." |
| **Curiosite sincere** | Pose une vraie question motivee par une curiosite authentique | "Tu mentionnes [X]... c'est quoi le declic pour toi ?" |
| **Confiance assumee** | Assurance sans arrogance, calme et pose | "Je ne suis pas du genre a envoyer 50 messages..." |
| **Douceur sensuelle** | Allie tendresse et sensualite, ton chaleureux et enveloppant | "Il y a quelque chose de doux et d'intense..." |

### Selection automatique du template

Quand des envies sont detectees dans la bio du destinataire, le systeme selectionne automatiquement le template le plus adapte :

| Envie detectee | Template selectionne |
|----------------|---------------------|
| Gang bang | Proposition directe |
| Echangisme | Experience partagee |
| BDSM | Confiance assumee |
| Exhibition | Mystere attirant |
| Feeling | Connexion emotionnelle |
| Fetichisme | Taquin seducteur |
| Hard | Proposition directe |
| Papouilles | Douceur sensuelle |
| Pluralite | Aventure sensuelle |

---

## Templates personnalisables par l'utilisateur

En plus des 13 templates d'approche integres, l'utilisateur peut creer ses propres templates de message via le dashboard. Ces templates sont organises par categorie de desir :

- Chaque template a un nom (label), un contenu (texte d'inspiration) et une categorie de desir associee
- 13 templates par defaut sont fournis a l'installation (couvrant Gang bang, Echangisme, BDSM, Exhibition, Feeling, Fetichisme, Hard, Papouilles, Pluralite)
- L'utilisateur peut ajouter, modifier ou supprimer des templates depuis le dashboard
- Le contenu du template est transmis a l'IA comme guide d'inspiration : l'IA le reformule et l'adapte au profil du destinataire

---

## Le profil utilisateur dans les prompts

Le profil de l'utilisateur (MY_PROFILE) est injecte dans chaque prompt de generation. Il comprend :

- **Identite** : pseudo, type, age, localisation
- **Description** : presentation libre
- **10 categories de connaissance** : passions, pratiques, personnalite, physique, etudes/metier, voyages, musique/culture, sport, humour, valeurs

Ces informations permettent a l'IA de :
- Se presenter comme l'utilisateur ("Tu es [pseudo], [type], [age], [localisation]")
- Trouver des points communs avec le destinataire
- Creer des rebonds naturels dans la conversation
- Personnaliser le ton et le contenu selon la personnalite de l'utilisateur

Voir [[02-Fonctionnalites/profil-ia|Profil IA]] pour le detail du systeme de profil.

---

## Modele IA

| Parametre | Valeur |
|-----------|--------|
| Modele | `gpt-4o-mini` |
| Max tokens (message) | 300 |
| Max tokens (enrichissement profil) | 500 |
| Retry | 3 tentatives avec backoff exponentiel (2s, 4.5s) |
| API | OpenAI AsyncOpenAI (client singleton) |

Le choix de `gpt-4o-mini` est motive par :
- Cout reduit par rapport a GPT-4o
- Vitesse de reponse rapide
- Qualite suffisante pour des messages courts et personnalises

---

## Filtre de securite

Chaque message genere par l'IA passe par un filtre de securite avant d'etre envoye. Ce filtre :

1. **Rejette les messages vides** ou ne contenant que des espaces/guillemets
2. **Tronque a 500 caracteres** max (coupe a la derniere phrase complete si possible)
3. **Bloque les patterns interdits** -- le message est rejete si il contient :

| Type de pattern | Exemples |
|-----------------|----------|
| IA qui brise le personnage | "je ne vois pas", "pas de conversation", "en tant qu'IA" |
| References au modele IA | "openai", "chatgpt", "gpt-4", "language model" |
| Aveux d'etre un programme | "je suis programme", "cette conversation est fictive" |
| Messages en anglais non souhaites | "as an AI", "I cannot", "I can't" |

Si un message est rejete, l'action est annulee pour ce destinataire (pas d'envoi de message vide ou suspect).

---

## Regles strictes du prompt

Chaque prompt contient des regles que l'IA doit respecter :

### A faire
- Message court : 2-3 phrases, 50 mots max
- Personnalise : reference a un element concret du profil
- Une seule question ouverte OU un commentaire engageant
- 1 emoji maximum (optionnel)
- Vouvoiement pour les couples, tutoiement pour les personnes seules

### A ne pas faire
- Accroches generiques ("Hey", "Salut ca va ?", "Coucou")
- "J'ai vu ton profil et..." (trop banal)
- Complimenter le physique ("tu es belle/beau")
- Ecrire un pave (plus de 3 phrases)
- Enchainer les questions
- Formules toutes faites ("on a plein de choses en commun")
- Smileys excessifs ou points de suspension partout

---

## Les 3 modes d'envoi de messages

### 1. Messages aux profils en ligne (`run_messages`)
- Source : profils du chat sidebar (utilisateurs en ligne)
- Navigue vers le profil, extrait les infos, genere le message, envoie via "Lui ecrire"
- Verifie en base qu'on n'a pas deja envoye de message a ce profil (anti-doublon)
- Limite : `messages_per_session` (par defaut 3)

### 2. Messages aux discussions (`message_discussions`)
- Source : discussions existantes dans le sidebar
- Clic sur chaque pseudo dans la liste des discussions en cours
- Navigue vers le profil, genere un premier message personnalise
- Anti-doublon : verifie les actions "message" et "sidebar_msg" en base

### 3. Messages depuis la recherche (`message_from_search`)
- Source : resultats de recherche filtrables par type de profil et envies
- Applique les filtres de recherche sur la page de recherche Wyylde
- Visite chaque profil des resultats, lit le profil complet (bio + onglet Infos)
- Genere un message avec les informations enrichies (bio, preferences, envies detectees)
- Supporte le template d'approche : l'IA s'inspire du template selectionne
- Anti-doublon : verifie les actions "message", "sidebar_msg" et "search_msg" en base

---

Voir aussi : [[02-Fonctionnalites/reponses-automatiques|Reponses automatiques]], [[02-Fonctionnalites/profil-ia|Profil IA]], [[01-Produit/plateformes|Plateformes]]
