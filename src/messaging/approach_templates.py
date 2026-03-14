"""
Approach templates for first messages on Wyylde.

Each template represents an intention/desire that guides the tone and angle
of the opening message. Used by generate_first_message() via the
approach_template parameter.

Context: site libertin entre adultes consentants — les templates assument
ce cadre sans vulgarite gratuite.
"""

APPROACH_TEMPLATES = {
    "complicite_intellectuelle": {
        "name": "Complicite intellectuelle",
        "description": (
            "Engage sur les centres d'interet, la culture, les idees. "
            "Montre que tu es quelqu'un avec qui on peut echanger en profondeur "
            "avant (et pendant) tout le reste."
        ),
        "example": (
            "Ta passion pour [X] m'interpelle — c'est rare de croiser quelqu'un "
            "qui s'y interesse vraiment. Tu as un auteur / artiste prefere sur le sujet ?"
        ),
    },
    "aventure_sensuelle": {
        "name": "Aventure sensuelle",
        "description": (
            "Evoque le desir et l'attirance de maniere assumee mais elegante. "
            "Pas de vulgarite, mais un langage qui laisse entendre que tu sais "
            "ce que tu cherches et que l'alchimie physique compte."
        ),
        "example": (
            "Ton profil degage quelque chose de magnetique... "
            "J'ai l'impression qu'on pourrait avoir une belle energie ensemble. "
            "Ca te parle ?"
        ),
    },
    "humour_decale": {
        "name": "Humour decale",
        "description": (
            "Accroche avec une touche d'humour inattendu, de l'autoderision "
            "ou un angle absurde. L'objectif est de surprendre et de faire sourire "
            "des la premiere seconde."
        ),
        "example": (
            "Je vais etre honnete : j'ai passe 5 minutes a chercher une accroche "
            "originale avant de realiser que la meilleure approche c'est d'etre "
            "sincere. Donc voila, ton profil me plait et je suis curieux."
        ),
    },
    "connexion_emotionnelle": {
        "name": "Connexion emotionnelle",
        "description": (
            "Cherche a creer un lien intime et authentique des le premier message. "
            "Montre de l'empathie, de la sensibilite, et un interet reel pour "
            "qui est la personne au-dela des apparences."
        ),
        "example": (
            "Ce que tu ecris sur [X] resonne vraiment avec moi... "
            "C'est le genre de detail qui fait qu'on a envie de connaitre "
            "la personne derriere le profil."
        ),
    },
    "proposition_directe": {
        "name": "Proposition directe",
        "description": (
            "Va droit au but avec clarte et respect. Exprime ce que tu cherches "
            "sans tourner autour du pot, tout en laissant la porte ouverte. "
            "Ideal quand le profil est lui-meme explicite sur ses envies."
        ),
        "example": (
            "Pas fan des longs echanges qui ne menent nulle part — "
            "je te propose qu'on se retrouve autour d'un verre pour voir "
            "si le feeling passe aussi bien en vrai qu'a l'ecran."
        ),
    },
    "mystere_attirant": {
        "name": "Mystere attirant",
        "description": (
            "Intrigue sans tout devoiler. Laisse planer un mystere qui donne "
            "envie de repondre pour en savoir plus. Des sous-entendus elegants, "
            "une aura enigmatique."
        ),
        "example": (
            "J'ai une theorie sur toi... mais je la garde pour le deuxieme message. "
            "A moins que tu sois du genre impatient ?"
        ),
    },
    "terrain_commun": {
        "name": "Terrain commun",
        "description": (
            "Identifie un point commun concret (lieu, passion, experience, style de vie) "
            "et construis le message autour. Cree un sentiment de 'on est du meme monde'."
        ),
        "example": (
            "[Paris/quartier/activite] aussi ? On a deja un point commun. "
            "Raconte-moi ta meilleure decouverte recente dans le coin."
        ),
    },
    "compliment_precis": {
        "name": "Compliment precis",
        "description": (
            "Fait un compliment specifique et original — sur une phrase de la bio, "
            "un choix de mot, un centre d'interet — jamais sur le physique. "
            "Montre que tu as lu et que quelque chose t'a marque."
        ),
        "example": (
            "J'aime la facon dont tu parles de [X] dans ta bio — "
            "ca se sent que c'est quelque chose qui te tient vraiment a coeur."
        ),
    },
    "taquin_seducteur": {
        "name": "Taquin seducteur",
        "description": (
            "Leger, joueur, legerement provocateur. Le but est de creer une "
            "dynamique de jeu seducteur des le premier echange, sans etre lourd. "
            "Taquine avec bienveillance."
        ),
        "example": (
            "Ton profil est presque parfait... il manque juste un detail. "
            "Mais je te dirai lequel seulement si tu me reponds."
        ),
    },
    "experience_partagee": {
        "name": "Experience partagee",
        "description": (
            "Propose ou evoque une experience qu'on pourrait vivre ensemble. "
            "Projette-toi dans un moment partage (sortie, voyage, soiree, decouverte) "
            "pour que la personne se visualise aussi."
        ),
        "example": (
            "J'imagine deja la scene : un bar a cocktails, une conversation "
            "qui deborde sur tout et n'importe quoi, et cette sensation "
            "qu'on ne voit pas le temps passer... Ca te tente ?"
        ),
    },
    "curiosite_sincere": {
        "name": "Curiosite sincere",
        "description": (
            "Pose une vraie question, motivee par une curiosite authentique "
            "sur un element du profil. Pas une question generique — une question "
            "qui montre que tu as reflechi."
        ),
        "example": (
            "Tu mentionnes [X] dans ta bio — j'ai toujours voulu comprendre "
            "ce qui attire les gens la-dedans. C'est quoi le declic pour toi ?"
        ),
    },
    "confiance_assumee": {
        "name": "Confiance assumee",
        "description": (
            "Degage de l'assurance sans arrogance. Montre que tu sais qui tu es, "
            "ce que tu veux, et que tu es a l'aise avec ca. Le ton est calme, "
            "pose, seduisant par la maitrise."
        ),
        "example": (
            "Je ne suis pas du genre a envoyer 50 messages — "
            "quand un profil me parle, je prefere etre direct. "
            "Le tien m'a arrete. Envie d'en discuter ?"
        ),
    },
    "douceur_sensuelle": {
        "name": "Douceur sensuelle",
        "description": (
            "Allie tendresse et sensualite. Le ton est chaleureux, enveloppant, "
            "avec une touche d'intimite qui laisse deviner que le desir est "
            "la mais exprime avec delicatesse. Ideal pour les profils qui "
            "cherchent complicite ET sensualite."
        ),
        "example": (
            "Il y a quelque chose de doux et d'intense a la fois dans ta facon "
            "de te decrire... J'aime ce melange. Ca me donne envie de te decouvrir "
            "un peu plus pres."
        ),
    },
}
