# FAQ -- Questions frequentes

#boostrencontre #faq #communication

---

## 1. C'est legal d'utiliser un bot sur un site de rencontre ?

Les conditions d'utilisation de la plupart des sites de rencontre interdisent l'utilisation de bots et d'outils d'automatisation. BoostRencontre est un outil technique dont l'utilisation releve de la responsabilite de chaque utilisateur. Nous recommandons de lire les conditions d'utilisation de votre site avant de l'utiliser.

## 2. Est-ce que je risque de me faire bannir ?

Le risque existe sur tous les sites de rencontre. BoostRencontre integre plusieurs protections anti-ban (delais naturels, variations aleatoires, limites journalieres) pour minimiser ce risque, mais aucune garantie ne peut etre donnee. Nous recommandons de commencer avec des parametres prudents et d'augmenter progressivement.

## 3. Combien ca coute ?

BoostRencontre est un outil auto-heberge. Le seul cout variable est l'utilisation de l'API OpenAI pour la generation de messages. Avec le modele gpt-4o-mini, le cout est d'environ 0.01 EUR par message genere, soit quelques centimes par jour pour une utilisation normale.

## 4. Quelles plateformes sont supportees ?

Actuellement : Wyylde (toutes les fonctionnalites), Tinder et Meetic (fonctionnalites de base : likes et messages). D'autres plateformes peuvent etre ajoutees en implementant l'interface `BasePlatform`.

## 5. Les messages sont-ils vraiment personnalises ?

Oui. Chaque message est genere individuellement par l'IA en fonction de la bio du destinataire, de son type de profil, de ses envies et de votre propre profil. Deux personnes differentes recevront deux messages completement differents. L'IA ne fait jamais de copier-coller.

## 6. Est-ce que les gens se rendent compte que c'est un bot ?

Le filtre de securite bloque tout message qui revelerait la nature IA du systeme. Les messages sont courts (2-3 phrases), naturels et font reference a des elements concrets du profil du destinataire. Cependant, aucun systeme n'est parfait et un destinataire attentif pourrait avoir des doutes, surtout si les reponses sont trop rapides ou trop coherentes.

## 7. Est-ce que je peux voir les messages avant qu'ils soient envoyes ?

Dans la version actuelle, les messages sont envoyes automatiquement apres generation. Cependant, vous pouvez suivre tous les messages envoyes dans le log d'activite du dashboard et dans l'historique de la page profil. Une fonctionnalite de validation manuelle avant envoi est envisagee.

## 8. Comment fonctionne le scoring de profils ?

Chaque profil est evalue sur 5 criteres : desirs communs (30 points), completude du profil (20 points), activite recente (15 points), compatibilite de type (20 points) et geographie (15 points). Le score total sur 100 determine un grade (A, B, C ou D) qui oriente l'action recommandee.

## 9. Mes donnees sont-elles en securite ?

Toutes les donnees sont stockees localement sur votre machine dans une base SQLite. Rien n'est envoye a un serveur distant, a l'exception des appels a l'API OpenAI pour generer les messages (les prompts contiennent votre profil et celui du destinataire). Le dashboard n'est accessible que depuis votre machine locale.

## 10. Est-ce que ca fonctionne sur Windows ou Mac ?

BoostRencontre est developpe et teste sur Linux. Il devrait fonctionner sur Mac avec quelques adaptations mineures. Le support Windows n'est pas garanti en raison de certaines dependances Linux (wmctrl, xdotool pour la gestion de la fenetre du navigateur).

## 11. Combien de messages puis-je envoyer par jour ?

Les limites journalieres par defaut sont : 20 messages, 30 reponses, 100 likes, 80 follows et 50 crush. Ces limites sont configurables mais nous deconseillons de les augmenter significativement pour ne pas declencher les systemes de detection des sites.

## 12. Quelle est la difference entre les 8 styles de communication ?

Chaque style produit un type de message different : "romantique" est doux et attentionne, "direct_sexe" est franc et assume, "humoristique" utilise l'humour pour briser la glace, "intellectuel" engage sur la culture et les idees, "aventurier" propose des experiences, "mysterieux" intrigue et suggere, "complice" cree une familiarite immediate, et "auto" laisse l'IA choisir le style le plus adapte au profil du destinataire.

## 13. Est-ce que je dois rester devant l'ecran pendant que le bot fonctionne ?

Non. Une fois les actions lancees, le bot travaille en autonomie. Le navigateur Chromium doit rester ouvert (meme minimise) mais vous n'avez pas besoin de le surveiller. Le mode veille auto-reply fonctionne en continu.

## 14. Comment installer BoostRencontre ?

L'installation necessite Python 3.12, un environnement virtuel, les dependances pip et l'installation du navigateur Playwright. Le processus complet est decrit dans le [[01-Produit/guide-utilisation|guide d'utilisation]].

## 15. Puis-je utiliser mon propre modele IA ?

Le code est configure pour utiliser l'API OpenAI avec le modele gpt-4o-mini. Passer a un autre modele OpenAI (GPT-4o, GPT-4) necessite uniquement de changer le nom du modele dans la configuration. L'utilisation d'autres fournisseurs (Anthropic, Mistral, etc.) necessite des adaptations du code.

---

Voir aussi : [[06-Communication/pitch|Pitch commercial]], [[06-Communication/fonctionnalites-cles|Fonctionnalites cles]], [[01-Produit/guide-utilisation|Guide d'utilisation]]

#faq #communication
