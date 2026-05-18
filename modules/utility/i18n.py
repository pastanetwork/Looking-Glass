from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

import orjson
from markupsafe import Markup

if TYPE_CHECKING:
    import logging


I18N_DIR = Path(__file__).resolve().parent.parent.parent / "i18n"


def load_translations(logger: logging.Logger) -> dict[str, dict[str, str]]:
    """
    Charge tous les fichiers de traduction JSON du dossier i18n en mémoire.

    Parameters:
        logger (logging.Logger): logger applicatif pour les avertissements et erreurs.

    Returns:
        dict[str, dict[str, str]]: dictionnaire code_langue -> paires clé/valeur.
    """
    translations: dict[str, dict[str, str]] = {}

    if not I18N_DIR.is_dir():
        logger.warning("Dossier i18n introuvable : %s", I18N_DIR)
        return translations

    for path in sorted(I18N_DIR.glob("*.json")):
        try:
            translations[path.stem] = orjson.loads(path.read_bytes())
        except Exception as e:
            logger.error("Traduction %s illisible : %s", path.name, e)

    return translations


def negotiate_language(
    translations: dict[str, dict[str, str]],
    default: str,
    cookie_value: Optional[str],
    accept_language: Optional[str],
) -> str:
    """
    Détermine la langue de la requête par ordre de priorité décroissant.

    Parameters:
        translations (dict[str, dict[str, str]]): traductions chargées en mémoire.
        default (str): code de langue par défaut (ex. "fr").
        cookie_value (Optional[str]): valeur du cookie de langue, ou None.
        accept_language (Optional[str]): valeur de l'en-tête Accept-Language, ou None.

    Returns:
        str: code de langue retenu (ex. "fr" ou "en").
    """
    if cookie_value and cookie_value in translations:
        return cookie_value

    if accept_language:
        for part in accept_language.split(","):
            code = part.split(";")[0].strip().lower().split("-")[0]
            if code in translations:
                return code

    if default in translations:
        return default

    return next(iter(translations), "en")


def make_translator(
    translations: dict[str, dict[str, str]], lang: str, default: str
) -> Callable[..., str]:
    """
    Construit et retourne une fonction de traduction pour la langue donnée.

    Parameters:
        translations (dict[str, dict[str, str]]): toutes les traductions chargées en mémoire.
        lang (str): code de langue principal (ex. "fr").
        default (str): code de langue de repli (ex. "en").

    Returns:
        Callable[..., str]: fonction t(key, **params) prête à l'emploi.
    """
    primary = translations.get(lang, {})
    fallback = translations.get(default, {})

    def t(key: str, **params: object) -> str:
        """
        Traduit une clé dans la langue courante avec remplacement de paramètres.

        Parameters:
            key (str): clé de traduction à rechercher.

        Returns:
            str: chaîne traduite avec les marqueurs %nom% remplacés.
        """
        text = primary.get(key) or fallback.get(key) or key
        for name, value in params.items():
            text = text.replace(f"%{name}%", str(value))
        return text

    return t


def make_i18n_tag(translator: Callable[..., str]) -> Callable[[str], Markup]:
    """
    Construit le helper Jinja `i18n`, qui rend un texte traduit et balisé.

    Parameters:
        translator (Callable[..., str]): fonction de traduction de la requête courante.

    Returns:
        Callable[[str], Markup]: le helper i18n(clé) renvoyant un fragment HTML sûr.
    """
    def i18n(key: str) -> Markup:
        return Markup('<span data-i18n="{}">{}</span>').format(key, translator(key))

    return i18n
