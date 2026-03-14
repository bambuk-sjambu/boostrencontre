"""Profile reading and navigation for Wyylde platform.

Mixin providing profile extraction, full profile reading (bio + Infos tab),
and navigation to member profiles.
"""

import asyncio
import re
import logging

from .selectors import (
    CHAT_PROFILE_BUTTON,
    MEMBER_LINK,
    PROFILE_NAME,
    MAIN_CONTENT_MIN_X,
    MEMBER_LINK_MIN_X,
)

logger = logging.getLogger(__name__)

# --- Shared JS: bio extraction logic ---
# Used by both _get_current_profile and read_full_profile to avoid duplication.
# Expects `mainText` (string) and `mainDivs` (NodeList of divs) in scope,
# plus a `uiWords` array and a `selectors.profileName` selector.

_JS_EXTRACT_BASE_PROFILE = """
function extractBaseProfile(mainText, mainDivs, profileNameSel, uiWords) {
    const result = {name: '', age: '', bio: '', type: '', fullText: '', location: '', preferences: ''};

    // Username
    const nameBtn = document.querySelector(profileNameSel);
    if (nameBtn) result.name = nameBtn.innerText.trim();

    result.fullText = mainText.substring(0, 3000);

    // Type, age, location from header lines
    const lines = mainText.split('\\n').map(l => l.trim()).filter(l => l);
    for (const line of lines.slice(0, 15)) {
        if (line.match(/\\d+(\\/\\d+)?\\s*ans/)) result.age = line;
        if (line.match(/^(Homme|Femme|Couple|Travesti|Transgenre)/i)) result.type = line;
        if (line.match(/kilomètre|France|Paris|\\(\\d{2}\\)/i)) result.location = line;
    }

    // Bio strategy 1: paragraphs in profile area
    let bestBio = '';
    const paragraphs = document.querySelectorAll('p');
    for (const p of paragraphs) {
        const rect = p.getBoundingClientRect();
        if (rect.x < 280 || rect.width < 200) continue;
        const text = p.innerText.trim();
        if (text.length > 30 && text.length < 2000) {
            const isUI = uiWords.some(w => text === w || text.startsWith(w));
            if (!isUI && text.length > bestBio.length) bestBio = text;
        }
    }

    // Bio strategy 2: divs with sentence-like text
    if (!bestBio) {
        for (const div of mainDivs) {
            const rect = div.getBoundingClientRect();
            if (rect.x < 280 || rect.width < 300 || rect.width > 700) continue;
            if (rect.height < 20 || rect.height > 300) continue;
            const text = div.innerText.trim();
            if (text.length < 40 || text.length > 1500) continue;
            if (text.split(/\\s+/).length < 8) continue;
            const isUI = uiWords.some(w => text.includes(w));
            if (isUI) continue;
            if (text.length > bestBio.length) bestBio = text;
        }
    }

    // Bio strategy 3: extract from fullText after known markers
    if (!bestBio || bestBio.length < 30) {
        const markers = ['Témoignages', 'Adhésions', 'Contacts'];
        const endMarkers = ['Préférences', 'Activités', 'EN SAVOIR PLUS', 'LIRE LA SUITE',
            'Votre dernier', 'Chargement', 'Commentaires'];
        for (const start of markers) {
            const idx = mainText.indexOf(start);
            if (idx < 0) continue;
            const after = mainText.substring(idx + start.length).trim();
            const textLines = after.split('\\n').map(l => l.trim()).filter(l => l.length > 20);
            for (const line of textLines) {
                if (endMarkers.some(m => line.includes(m))) break;
                if (line.split(/\\s+/).length >= 5 && !uiWords.some(w => line.startsWith(w))) {
                    bestBio = line;
                    break;
                }
            }
            if (bestBio && bestBio.length > 30) break;
        }
    }

    result.bio = bestBio.substring(0, 800);
    return result;
}
"""

_JS_GET_MAIN_TEXT = """
function getMainText() {
    const mainDivs = document.querySelectorAll('div');
    let mainText = '';
    for (const div of mainDivs) {
        const rect = div.getBoundingClientRect();
        if (rect.x > 280 && rect.x < 400 && rect.width > 500 && rect.height > 200) {
            const t = div.innerText.trim();
            if (t.length > mainText.length) mainText = t;
        }
    }
    return {mainText, mainDivs};
}
"""

_JS_CLICK_EXPAND = """() => {
    const els = document.querySelectorAll('button, a, span, div');
    for (const el of els) {
        const text = (el.innerText || '').trim().toUpperCase();
        if (text === 'EN SAVOIR PLUS' || text === 'EN SAVOIR +' ||
            text === 'LIRE LA SUITE' || text === 'LIRE LA SUITE...' ||
            text === 'VOIR PLUS') {
            const rect = el.getBoundingClientRect();
            if (rect.x > 280 && rect.width > 0) { el.click(); }
        }
    }
}"""

_JS_CLICK_INFOS_TAB = """() => {
    const tabs = document.querySelectorAll('button, a');
    for (const tab of tabs) {
        const text = (tab.innerText || '').trim();
        if (text === 'Infos') {
            const rect = tab.getBoundingClientRect();
            if (rect.x > 280 && rect.width > 0) { tab.click(); return; }
        }
    }
}"""


def _parse_age(text: str) -> str:
    """Extract age from profile text."""
    match = re.search(r'(\d{2,3}(?:/\d{2,3})?)\s*ans', text)
    return match.group(1) if match else ""


class WyyldeProfileMixin:
    """Profile reading and navigation methods for Wyylde."""

    async def _get_current_profile(self) -> dict:
        """Extract detailed profile info from the current member page."""
        info = {"name": "", "age": "", "bio": "", "type": "", "interests": []}
        try:
            # Expand description
            await self.page.evaluate(_JS_CLICK_EXPAND)
            await asyncio.sleep(1)

            # Click Infos tab
            await self.page.evaluate(_JS_CLICK_INFOS_TAB)
            await asyncio.sleep(1)

            # Extract profile data using shared JS logic
            data = await self.page.evaluate("""(params) => {
                """ + _JS_EXTRACT_BASE_PROFILE + """
                """ + _JS_GET_MAIN_TEXT + """

                const uiWords = params.uiWords;
                const {mainText, mainDivs} = getMainText();
                const result = extractBaseProfile(mainText, mainDivs, params.profileName, uiWords);

                // Extract preferences if visible
                const prefIdx = mainText.indexOf('Préférences partagées');
                if (prefIdx > 0) {
                    result.preferences = mainText.substring(prefIdx, prefIdx + 300).trim();
                }

                // Extract "envies" / desires keywords
                const envieKeywords = ['recherche', 'envie', 'cherche', 'souhaite', 'aime',
                    'On aime', 'Nous aimons', 'Nos envies', 'Notre recherche'];
                for (const kw of envieKeywords) {
                    const idx = mainText.toLowerCase().indexOf(kw.toLowerCase());
                    if (idx >= 0) {
                        const start = Math.max(0, mainText.lastIndexOf('\\n', idx));
                        const end = Math.min(mainText.length, idx + 300);
                        const envieText = mainText.substring(start, end).trim();
                        if (envieText.length > result.bio.length) {
                            result.bio = envieText.substring(0, 500);
                        }
                        break;
                    }
                }

                // Extract info from "Infos" tab
                const infosArea = document.querySelectorAll('div, section');
                for (const div of infosArea) {
                    const rect = div.getBoundingClientRect();
                    if (rect.x < 280 || rect.width < 300) continue;
                    const text = div.innerText.trim();
                    if (text.match(/(Orientation|Pratiques|À propos|Situation|Silhouette)/i) &&
                        text.length > 50 && text.length < 800) {
                        result.preferences = (result.preferences + '\\n' + text).substring(0, 500);
                        break;
                    }
                }

                return result;
            }""", {
                "profileName": PROFILE_NAME,
                "uiWords": [
                    'Suivre', 'Déconnexion', 'Adeptes', 'Adhésions', 'Témoignages',
                    'Activités', 'Infos', 'Médias', 'Agenda', 'Communauté', 'Commentaires',
                    'EN SAVOIR PLUS', 'Libre cette semaine', 'Préférences partagées',
                    'DEMANDER À VOIR', 'CAMERA', 'Certifié',
                ],
            })

            info["name"] = data.get("name", "")
            info["bio"] = data.get("bio", "")
            info["type"] = data.get("type", "")
            info["location"] = data.get("location", "")
            info["preferences"] = data.get("preferences", "")

            age_text = data.get("age", "") or data.get("fullText", "")
            info["age"] = _parse_age(age_text)

            logger.info(
                f"Profile: {info['name']} | {info['type']} | {info['age']} ans | "
                f"bio={info['bio'][:80]}... | prefs={info['preferences'][:60]}..."
            )

        except Exception as e:
            logger.debug(f"Error extracting profile: {e}")

        return info

    async def read_full_profile(self) -> dict:
        """Read a profile completely: expand bio + click Infos tab + extract everything."""
        if "/member/" not in self.page.url:
            return {}

        # Step 1: Expand description (click twice for multiple expand buttons)
        await self.page.evaluate(_JS_CLICK_EXPAND)
        await asyncio.sleep(1)
        await self.page.evaluate(_JS_CLICK_EXPAND)
        await asyncio.sleep(1)

        # Step 2: Read bio from the Activites tab (default tab)
        bio_data = await self.page.evaluate("""(params) => {
            """ + _JS_EXTRACT_BASE_PROFILE + """
            """ + _JS_GET_MAIN_TEXT + """

            const {mainText, mainDivs} = getMainText();
            return extractBaseProfile(mainText, mainDivs, params.profileName, params.uiWords);
        }""", {
            "profileName": PROFILE_NAME,
            "uiWords": [
                'Suivre', 'Déconnexion', 'Adeptes', 'Adhésions', 'Témoignages',
                'Activités', 'Infos', 'Médias', 'Agenda', 'Communauté', 'Commentaires',
                'EN SAVOIR PLUS', 'Libre cette semaine', 'Préférences partagées',
                'DEMANDER À VOIR', 'Certifié', 'Lui écrire', 'Envoyer',
                'Votre dernier coup de coeur', 'Chargement en cours', 'Participer',
                'coup de coeur envoyé', 'Compléter mon profil',
            ],
        })

        # Step 3: Click Infos tab to read desires/preferences
        await self.page.evaluate(_JS_CLICK_INFOS_TAB)
        await asyncio.sleep(2)

        # Step 4: Extract desires/preferences from Infos tab
        infos_data = await self.page.evaluate("""(knownDesires) => {
            const result = {preferences: '', desires: ''};
            const mainDivs = document.querySelectorAll('div');

            let infosText = '';
            for (const div of mainDivs) {
                const rect = div.getBoundingClientRect();
                if (rect.x > 280 && rect.x < 500 && rect.width > 400 && rect.height > 100) {
                    const t = div.innerText.trim();
                    if (t.length > infosText.length) infosText = t;
                }
            }

            // Extract desire tags
            const desireTags = [];
            for (const tag of knownDesires) {
                if (infosText.includes(tag)) desireTags.push(tag);
            }
            result.desires = desireTags.join(', ');

            // Extract other info (orientation, situation, etc.)
            const infoLines = infosText.split('\\n').map(l => l.trim()).filter(l => l.length > 2);
            const prefLines = [];
            for (const line of infoLines) {
                if (line.match(/(Orientation|Pratiques|Situation|Silhouette|Taille|Yeux|Cheveux|Fumeur|Alcool|Tatouage|Piercing)/i)) {
                    prefLines.push(line);
                }
            }
            result.preferences = prefLines.join(' | ');
            result.fullInfos = infosText.substring(0, 1500);
            return result;
        }""", [
            'BDSM', 'Échangisme', 'Exhibition', 'Extreme', 'Feeling',
            'Fétichisme', 'Gang bang', 'Hard', 'Papouilles', 'Pluralité', 'Vidéos',
            'Voyeurisme', 'Massage', 'Tantra', 'Domination', 'Soumission',
            'Candaulisme', 'Triolisme', 'Libertinage', 'Mélanisme',
        ])

        # Step 5: Go back to Activites tab
        await self.page.evaluate("""() => {
            const tabs = document.querySelectorAll('button, a');
            for (const tab of tabs) {
                const text = (tab.innerText || '').trim();
                if (text === 'Activités') {
                    const rect = tab.getBoundingClientRect();
                    if (rect.x > 280 && rect.width > 0) { tab.click(); return; }
                }
            }
        }""")

        age_text = bio_data.get("age", "") or bio_data.get("fullText", "")

        profile = {
            "name": bio_data.get("name", ""),
            "age": _parse_age(age_text),
            "type": bio_data.get("type", ""),
            "location": bio_data.get("location", ""),
            "bio": bio_data.get("bio", ""),
            "interests": [],
            "preferences": infos_data.get("preferences", ""),
            "desires": infos_data.get("desires", ""),
        }

        # Combine desires into preferences for AI prompt
        if profile["desires"]:
            profile["preferences"] = (
                profile["preferences"] + " | Envies: " + profile["desires"]
            ).strip(" | ")

        logger.info(
            f"Full profile: {profile['name']} | {profile['type']} | {profile['age']} ans | "
            f"bio={profile['bio'][:80]}... | prefs={profile['preferences'][:80]}..."
        )
        return profile

    async def get_profile_info(self, profile_element) -> dict:
        """Extract profile information from a profile element."""
        return await self._get_current_profile()

    async def navigate_to_profile(self, match_id: str) -> dict:
        """Navigate to a profile from chat sidebar. Returns profile info or None."""
        try:
            if "/dashboard" not in self.page.url:
                await self.page.goto(self.LOGIN_URL, timeout=30000, wait_until="domcontentloaded")
                await asyncio.sleep(5)

            idx = int(match_id)

            # Click the chat profile button
            clicked_name = await self.page.evaluate(f"""() => {{
                const buttons = document.querySelectorAll('{CHAT_PROFILE_BUTTON}');
                if (buttons[{idx}]) {{
                    const text = buttons[{idx}].innerText.trim();
                    buttons[{idx}].click();
                    return text.split('\\n')[0];
                }}
                return null;
            }}""")

            if not clicked_name:
                logger.error(f"Chat profile at index {idx} not found")
                return None

            logger.info(f"Opened chat with: {clicked_name}")
            await asyncio.sleep(2)

            # Navigate to member profile page
            await self.page.evaluate(f"""() => {{
                const links = [...document.querySelectorAll('{MEMBER_LINK}')];
                let best = null, bestX = 0;
                for (const link of links) {{
                    const rect = link.getBoundingClientRect();
                    if (rect.x > {MEMBER_LINK_MIN_X} && rect.width > 0 && rect.x > bestX) {{
                        bestX = rect.x; best = link;
                    }}
                }}
                if (best) best.click();
            }}""")

            for _ in range(10):
                await asyncio.sleep(1)
                if "/member/" in self.page.url:
                    break
            await asyncio.sleep(2)

            if "/member/" not in self.page.url:
                logger.error(f"Failed to navigate to profile for {clicked_name}")
                return None

            logger.info(f"On profile page: {self.page.url}")

            profile_info = await self._get_current_profile()
            if not profile_info.get("name"):
                profile_info["name"] = clicked_name
            return profile_info

        except Exception as e:
            logger.error(f"Error navigating to profile {match_id}: {e}")
            return None
