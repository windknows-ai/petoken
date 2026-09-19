"""Central string catalog for the staged V1.1.0 localization work."""

DEFAULT_LANGUAGE = "zh_CN"
SUPPORTED_LANGUAGES = ("zh_CN", "en")

STRINGS = {
    "zh_CN": {
        "settings_title": "petoken · 设置",
        "save": "保存",
        "cancel": "取消",
    },
    "en": {
        "settings_title": "petoken · Settings",
        "save": "Save",
        "cancel": "Cancel",
    },
}


def text(key, language=DEFAULT_LANGUAGE):
    catalog = STRINGS.get(language, STRINGS[DEFAULT_LANGUAGE])
    return catalog.get(key, STRINGS[DEFAULT_LANGUAGE][key])
