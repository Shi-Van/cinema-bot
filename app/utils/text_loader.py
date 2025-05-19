import os
from typing import Dict

_text_cache: Dict[str, str] = {}

def get_text(text_key: str, texts_dir: str = "app/utils/texts") -> str:
    """Загрузка текста из файла"""
    if text_key in _text_cache:
        return _text_cache[text_key]

    try:
        with open(os.path.join(texts_dir, f"{text_key}.txt"), "r", encoding="utf-8") as f:
            text = f.read().strip()
            _text_cache[text_key] = text
            return text
    except FileNotFoundError:
        return f"Текст не найден: {text_key}"