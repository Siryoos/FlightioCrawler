import json
import pytest

from multilingual_processor import LocalizationManager


@pytest.mark.asyncio
async def test_translation_management(tmp_path):
    translations_dir = tmp_path / "translations"
    translations_dir.mkdir()

    (translations_dir / "en.json").write_text(
        json.dumps({"greeting": "Hello", "farewell": "Goodbye"}), encoding="utf-8"
    )
    (translations_dir / "fa.json").write_text(
        json.dumps({"greeting": "سلام"}), encoding="utf-8"
    )

    manager = LocalizationManager(str(translations_dir))

    en_trans = await manager.load_translations("en")
    assert en_trans["greeting"] == "Hello"

    greeting_fa = await manager.get_localized_string("greeting", "fa")
    assert greeting_fa == "سلام"

    missing = await manager.validate_translations("fa")
    assert missing == ["farewell"]

    await manager.update_translation_files({"fa": {"farewell": "خداحافظ"}})

    fa_trans = await manager.load_translations("fa")
    assert fa_trans["farewell"] == "خداحافظ"

    missing_after = await manager.validate_translations("fa")
    assert missing_after == []
