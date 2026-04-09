"""Enum label maps: locale -> en -> raw code fallback."""

import app.i18n.enum_labels as enum_labels


def test_get_label_uses_spanish_when_present():
    assert enum_labels.get_label("street_type", "st", "es") == "Calle"


def test_get_label_falls_back_to_english_when_locale_map_missing_code():
    backup = enum_labels.ENUM_LABELS
    try:
        enum_labels.ENUM_LABELS = {
            "en": {"t": {"x": "English X"}},
            "pt": {"t": {}},
        }
        assert enum_labels.get_label("t", "x", "pt") == "English X"
    finally:
        enum_labels.ENUM_LABELS = backup


def test_get_label_last_resort_is_code():
    backup = enum_labels.ENUM_LABELS
    try:
        enum_labels.ENUM_LABELS = {"en": {}, "es": {}}
        assert enum_labels.get_label("t", "RAW", "es") == "RAW"
    finally:
        enum_labels.ENUM_LABELS = backup
