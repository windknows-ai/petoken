"""Central string catalog for the staged V1.1.0 localization work."""

DEFAULT_LANGUAGE = "zh_CN"
SUPPORTED_LANGUAGES = ("zh_CN", "en")

STRINGS = {
    "zh_CN": {
        "settings_title": "petoken · 设置",
        "save": "保存",
        "cancel": "取消",
        "token_number_format": "Token 数字格式",
        "token_format_full": "完整数字",
        "token_format_compact": "紧凑格式",
    },
    "en": {
        "settings_title": "petoken · Settings",
        "save": "Save",
        "cancel": "Cancel",
        "token_number_format": "Token number format",
        "token_format_full": "Full",
        "token_format_compact": "Compact",
    },
}


def text(key, language=DEFAULT_LANGUAGE):
    catalog = STRINGS.get(language, STRINGS[DEFAULT_LANGUAGE])
    return catalog.get(key, STRINGS[DEFAULT_LANGUAGE][key])
