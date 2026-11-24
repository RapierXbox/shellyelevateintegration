"""The wake word catalog built from the GitHub repo trees."""

from __future__ import annotations

from custom_components.shellyelevateintegration import wake_words


def _blobs(*paths: str) -> list[dict[str, str]]:
    return [{"path": p, "type": "blob"} for p in paths]


def test_phrase_drops_repo_folders() -> None:
    """Model ids named after their folder read as the spoken phrase."""
    assert wake_words.phrase_of("hey_glados_microWakeWordsV6") == "Hey Glados"
    assert wake_words.phrase_of("okay_nabu_models_v2") == "Okay Nabu"
    assert wake_words.phrase_of("alexa") == "Alexa"


def test_newest_version_per_word() -> None:
    """Only the highest numbered folder of a word is offered; the vad is never offered."""
    tree = _blobs(
        "microWakeWordsV1/hey_glados.tflite",
        "microWakeWordsV6/hey_glados.tflite",
        "microWakeWordsV6/hey_glados.json",
        "microWakeWordsV3/hey_glados.tflite",
        "microWakeWordsV2/alexa.tflite",
        "models/v2/vad.tflite",
    )
    models = {m.stem: m for m in wake_words.parse_tree("community", tree)}
    assert set(models) == {"hey_glados", "alexa"}
    assert models["hey_glados"].path == "microWakeWordsV6/hey_glados.tflite"
    assert models["hey_glados"].has_json is True
    assert models["alexa"].has_json is False


def test_installed_by_phrase() -> None:
    """A model counts as installed when the display has one with the same phrase, whatever its file name."""
    models = wake_words.parse_tree("community", _blobs("microWakeWordsV6/hey_glados.tflite", "x/alexa.tflite"))
    listed = wake_words.catalog_as_list(models, [{"id": "hey_glados_microWakeWordsV6"}])
    assert {m["stem"]: m["installed"] for m in listed} == {"hey_glados": True, "alexa": False}
