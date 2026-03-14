# Reponses automatiques

#boostrencontre #reponses #auto-reply #conversations

---

## Principe

Le systeme de reponses automatiques detecte les messages non lus dans le sidebar de Wyylde, lit la conversation, genere une reponse contextuelle par IA et l'envoie. Il peut fonctionner en mode ponctuel (un seul scan) ou en mode veille continue (boucle avec intervalle configurable).

---

## Detection des messages non lus

### Sidebar : section "Discussions non lues"

Le sidebar droit de Wyylde contient deux sections :
1. **"N Discussions non lues"** : bouton jaune-vert (`BG=rgb(236,255,107)`) situe a x~1006, largeur ~259px
2. **"N Discussions en cours"** : section avec fond fonce (`rgb(37,33,30)`)

La section "non lues" est **repliee par defaut**. Le bot doit :
1. Detecter le bouton jaune-vert
2. Cliquer dessus pour deplier la section
3. Attendre que les pseudos non lus apparaissent (petits boutons ~152x22 a x~1022)
4. Chaque pseudo non lu est accompagne d'un tag "NOUVEAUX"

### Detection de l'etat replie/deplie

Le bot mesure l'ecart entre le header "non lues" et le header "en cours" :
- Si l'ecart est inferieur a 60px : la section est repliee, il faut cliquer pour l'ouvrir
- Apres le clic, le header se deplace (par exemple de y=720 a y=605) et les pseudos apparaissent en dessous

### Distinction avec le panneau lateral

Il existe un second element "Discussions non lues" tout a droite (x~1265) avec l'ID `#headerOpenedTalks`. C'est le header du panneau lateral, **pas** la liste interactive. Le bot l'ignore.

---

## Flow technique pas a pas

### reply_to_unread_sidebar()

1. **Navigation** : verification que le bot est sur le dashboard (sinon navigation vers `app.wyylde.com/fr-fr`)

2. **Detection des non-lus** : scan de tous les elements du sidebar entre x=955 et x=1200, hauteur 15-50px. Filtre les elements contenant le tag "NOUVEAUX" adjacents ou parents

3. **Pour chaque pseudo non lu** :
   a. **Verification anti-doublon** : verifie en base si on a deja repondu a ce pseudo dans les 3 dernieres minutes
   b. **Verification de rejet** : verifie si ce pseudo est marque "rejected" en base
   c. **Clic sur le pseudo** : ouvre le chat popup
   d. **Lecture du contenu** : extraction du texte de la conversation depuis le chat popup (div avec le plus de texte contenant le nom du destinataire)
   e. **Detection de blocage** : si le texte contient "filtres des messages de ce membre", le chat est bloque -- on passe au suivant
   f. **Verification du dernier message** : on cherche notre dernier message envoye dans le chat. Si on le trouve et qu'il n'y a pas de nouveau contenu significatif apres (moins de 15 caracteres nouveaux), on considere que c'est nous qui avons parle en dernier et on ne repond pas
   g. **Detection de l'expediteur** : le module `chat_utils.detect_last_sender()` parcourt le chat de bas en haut pour trouver quel pseudo apparait en dernier comme ligne autonome. Si c'est le notre ("me"), on ne repond pas
   h. **Verification de rejet dans le texte** : scan des 500 derniers caracteres pour des patterns de rejet ("non merci", "pas interesse", "arrete", "degage", "spam", etc.)
   i. **Exploration du profil** : ouverture du profil du destinataire dans un nouvel onglet pour extraire le type, l'age, la localisation et la bio (utilise pour le prompt de reponse)
   j. **Generation de la reponse** : appel a `generate_reply_message()` avec le nom, le texte de conversation et les infos du profil
   k. **Saisie et envoi** : localisation de l'editeur TipTap dans le chat popup, clic, frappe au clavier (delay=25ms par caractere), clic sur le bouton d'envoi (icone `paper-plane-top`)
   l. **Log en base** : enregistrement de l'action "sidebar_reply" avec le message envoye
   m. **Fermeture de la discussion** : clic pour reduire le chat popup et eviter les interactions residuelles

4. **Retour** : retour de la liste des reponses envoyees

---

## Anti-doublon

Plusieurs mecanismes empechent de repondre en double :

| Mecanisme | Description |
|-----------|-------------|
| Verification recente (3 min) | Si une reponse a ete envoyee au meme pseudo dans les 3 dernieres minutes, on passe |
| Verification du dernier expediteur | Si le dernier message visible dans le chat est le notre, on ne repond pas |
| Detection du message envoye | On cherche notre dernier message envoye (en base) dans le texte du chat. Si on le trouve et qu'il n'y a pas de nouveau contenu apres, on ne repond pas |
| Verification en base | Les actions "auto_reply", "sidebar_reply" et "reply" sont toutes verifiees |

---

## Detection de rejet

Le systeme detecte automatiquement les signaux de rejet dans la conversation. Si un pattern de rejet est trouve dans les 500 derniers caracteres, le contact est marque comme "rejected" en base et ne sera plus jamais contacte.

### Patterns de rejet detectes

```
non merci, pas interesse(e), arrete, stop, fichez la paix,
casse-couilles, degage, bloque, on t'a dit non, lache, spam,
harcelement, ne m'interesse(e)/convient, laissez-moi/nous,
plus la peine, tranquille
```

Ces patterns sont insensibles a la casse et supportent les variations d'accentuation.

---

## Generation de la reponse

Le prompt de reponse est construit pour :

1. **Analyser la conversation entiere** : contexte, ton, sujets deja abordes
2. **Comprendre ce que le destinataire cherche** : envies explicites ou implicites
3. **Identifier le dernier message** auquel il faut repondre
4. **Repondre directement** : si c'est une question, y repondre d'abord ; si c'est un commentaire, rebondir
5. **Respecter le niveau d'intensite** : si la conversation est explicite, rester au meme niveau

### Regles specifiques aux reponses

- Pas de "Salut", "Bonjour", "Hey" -- c'est une conversation en cours
- Coherence avec ce qui a deja ete dit
- Ne pas terminer systematiquement par une question
- Maximum 1-3 phrases, 50 mots
- Si le texte est confus, rebondir sur n'importe quel element (jamais dire "je ne vois pas de message")

---

## Mode veille auto-reply

Le mode veille lance une boucle continue qui scanne les messages non lus a intervalle regulier.

### Fonctionnement

1. L'utilisateur active la veille depuis le dashboard (bouton "Veille Auto-Reply")
2. Une tache asyncio (`asyncio.create_task`) est creee pour la plateforme
3. La boucle execute `reply_to_unread_sidebar()` toutes les N secondes (60 par defaut)
4. La boucle continue tant que la session navigateur est active
5. L'utilisateur peut arreter la veille a tout moment (bouton "STOP Veille")

### Parametres

| Parametre | Valeur par defaut | Description |
|-----------|-------------------|-------------|
| `interval` | 60 | Secondes entre chaque scan |
| `style` | "auto" | Style de communication pour les reponses |

### Arret automatique

La veille s'arrete automatiquement dans les cas suivants :
- Fermeture du navigateur (`close_browser` appelle `stop_auto_reply`)
- Deconnexion de la plateforme
- Arret du serveur

---

## Reponse via la mailbox (inbox)

En plus du sidebar, le bot peut aussi repondre aux conversations de la boite de reception :

### reply_to_inbox()

1. Navigation vers `app.wyylde.com/fr-fr/mailbox/inbox`
2. Clic sur l'onglet "Tous" pour voir toutes les conversations
3. Pour chaque conversation :
   - Navigation vers la conversation
   - Lecture du contenu des messages (zone de texte a x > 580, largeur 280-400px)
   - Filtrage du texte UI (timestamps, labels)
   - Verification de rejet et anti-doublon
   - Generation de la reponse IA
   - Saisie et envoi via l'editeur

### reply_to_sidebar()

Variante qui utilise le sidebar "Discussions en cours" au lieu de la mailbox :
1. Ouvre la liste des discussions via `_open_discussions_list()`
2. Pour chaque discussion : clic, lecture du chat popup, generation et envoi de la reponse

---

## check_and_reply_unread()

Fonction combinee qui execute dans l'ordre :
1. `reply_to_unread_sidebar()` -- reponse aux discussions non lues du sidebar
2. `reply_to_inbox()` -- reponse aux conversations de la mailbox

Cette fonction est utilisee par l'endpoint `POST /api/check-replies/{platform}` (mode synchrone, sans job async).

---

Voir aussi : [[02-Fonctionnalites/messages-ia|Messages IA]], [[03-Technique/securite-anti-ban|Securite et anti-ban]], [[01-Produit/plateformes|Plateformes]]
