import logging
import os

import aiosqlite

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "boostrencontre.db")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                session_data TEXT,
                status TEXT DEFAULT 'disconnected',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                action TEXT NOT NULL,
                target_name TEXT,
                message_sent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY,
                likes_per_session INTEGER DEFAULT 50,
                messages_per_session INTEGER DEFAULT 3,
                delay_min INTEGER DEFAULT 3,
                delay_max INTEGER DEFAULT 8
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_profile (
                id INTEGER PRIMARY KEY,
                data TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS daily_counters (
                date TEXT NOT NULL,
                platform TEXT NOT NULL,
                action TEXT NOT NULL,
                count INTEGER DEFAULT 0,
                PRIMARY KEY (date, platform, action)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS conversation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                contact_name TEXT NOT NULL,
                direction TEXT NOT NULL,
                message_text TEXT,
                stage TEXT DEFAULT 'accroche',
                turn_number INTEGER DEFAULT 1,
                style_used TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_conv_contact "
            "ON conversation_history(platform, contact_name)"
        )
        await db.execute("""
            CREATE TABLE IF NOT EXISTS message_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                desire TEXT NOT NULL,
                label TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            INSERT OR IGNORE INTO settings (id, likes_per_session, messages_per_session, delay_min, delay_max)
            VALUES (1, 50, 3, 3, 8)
        """)
        # Add style column if it doesn't exist (migration)
        try:
            await db.execute("ALTER TABLE activity_log ADD COLUMN style TEXT DEFAULT 'auto'")
        except Exception:
            pass  # Column already exists

        # Indexes for faster activity_log lookups
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_activity_platform_action ON activity_log(platform, action, target_name)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_activity_platform_target ON activity_log(platform, target_name, created_at)"
        )
        await db.execute("""
            CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                platform TEXT NOT NULL,
                status TEXT DEFAULT 'draft',
                target_type TEXT,
                target_age_min INTEGER,
                target_age_max INTEGER,
                target_location TEXT,
                target_desires TEXT,
                style TEXT DEFAULT 'auto',
                max_contacts INTEGER DEFAULT 20,
                contacts_done INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS campaign_contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER NOT NULL,
                contact_name TEXT NOT NULL,
                contact_type TEXT,
                contact_age TEXT,
                status TEXT DEFAULT 'pending',
                score INTEGER,
                message_sent TEXT,
                contacted_at TIMESTAMP,
                replied_at TIMESTAMP,
                notes TEXT,
                FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
                UNIQUE(campaign_id, contact_name)
            )
        """)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_campaign_contacts_campaign "
            "ON campaign_contacts(campaign_id, status)"
        )
        await db.execute("""
            CREATE TABLE IF NOT EXISTS profile_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                target_name TEXT NOT NULL,
                target_type TEXT,
                score INTEGER,
                grade TEXT,
                recommendation TEXT,
                suggested_style TEXT,
                details TEXT,
                scored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(platform, target_name)
            )
        """)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_profile_scores_platform "
            "ON profile_scores(platform, score DESC)"
        )
        await db.execute("""
            CREATE TABLE IF NOT EXISTS email_settings (
                id INTEGER PRIMARY KEY,
                data TEXT NOT NULL
            )
        """)
        # Default message templates per desire
        cursor = await db.execute("SELECT COUNT(*) FROM message_templates")
        count = (await cursor.fetchone())[0]
        if count == 0:
            defaults = [
                ("Gang bang", "Organisateur", "On organise regulierement des soirees gang bang dans un cadre respectueux et bienveillant. On selectionne les participants avec soin pour que tout le monde passe un bon moment. Votre profil nous a tapes dans l'oeil."),
                ("Gang bang", "Participant motive", "On adore les experiences gang bang et on cherche des couples/personnes avec qui partager ca dans le respect et la bonne humeur. On a deja quelques experiences et on aimerait en savoir plus sur vos envies."),
                ("Gang bang", "Curieux qui propose", "L'idee du gang bang nous excite beaucoup et on aimerait organiser ou participer a ce genre de soiree. On cherche des gens cool et ouverts pour en discuter sans prise de tete."),
                ("Échangisme", "Couple experimente", "On est un couple libertin qui adore les echanges. On cherche des gens complices et respectueux pour partager des moments intenses."),
                ("Échangisme", "Nouveaux curieux", "On est assez nouveaux dans l'echangisme mais tres curieux et motives. On cherche un couple bienveillant pour une premiere experience."),
                ("BDSM", "Dominant soft", "On aime explorer le BDSM dans un cadre safe et consenti. Domination douce, jeux de pouvoir, on cherche des partenaires qui partagent cette passion."),
                ("BDSM", "Curieux BDSM", "Le BDSM nous intrigue et on aimerait explorer ca avec des personnes experimentees et bienveillantes."),
                ("Exhibition", "Exhib assumee", "L'exhibition est notre kiff. On adore se montrer et regarder. On cherche des gens qui partagent cette excitation."),
                ("Feeling", "Connexion d'abord", "Pour nous le feeling c'est la base. On cherche d'abord une vraie connexion avant d'aller plus loin. Prenons le temps de se connaitre."),
                ("Fétichisme", "Fetichiste ouvert", "On a des fetishes assumes et on cherche des personnes ouvertes d'esprit pour les partager."),
                ("Hard", "Hard consenti", "On aime les pratiques hard dans un cadre consenti et respectueux. On cherche des partenaires qui partagent cette intensite."),
                ("Papouilles", "Doux et sensuel", "On adore la tendresse, les caresses, la sensualite. On cherche des rencontres douces et complices avant tout."),
                ("Pluralité", "Plans a plusieurs", "Les plans a plusieurs c'est notre truc. On aime la convivialite et le partage dans une ambiance detendue."),
            ]
            for desire, label, content in defaults:
                await db.execute(
                    "INSERT INTO message_templates (desire, label, content) VALUES (?, ?, ?)",
                    (desire, label, content)
                )
        await db.commit()


async def get_db():
    return aiosqlite.connect(DB_PATH)


def dict_factory(cursor, row):
    """Row factory that returns dicts instead of tuples.

    Usage:
        async with await get_db() as db:
            db.row_factory = dict_factory
            cursor = await db.execute("SELECT ...")
            rows = await cursor.fetchall()  # list of dicts
    """
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}
