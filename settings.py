import os
import json
from typing import Any, Dict, Tuple

os.makedirs('images', exist_ok=True)
os.makedirs('sounds', exist_ok=True)
os.makedirs('score', exist_ok=True)

SETTINGS_PATH = os.path.join('score', 'settings.json')
HIGHSCORE_PATH = os.path.join('score', 'highscore.save')

DEFAULT_SETTINGS: Dict[str, Any] = {
    "volume": 0.6,
    "muted": False,
    "sensitivity": 0.6,
    "mic_threshold": 0.07
}

WHITE: Tuple[int, int, int] = (255, 255, 255)
BLUE: Tuple[int, int, int] = (64, 224, 208)
GREEN: Tuple[int, int, int] = (34, 139, 34)
YELLOW: Tuple[int, int, int] = (255, 215, 0)
RED: Tuple[int, int, int] = (220, 20, 60)
GREY: Tuple[int, int, int] = (180, 180, 180)

def load_settings() -> Dict[str, Any]:
    try:
        with open(SETTINGS_PATH, 'r') as f:
            s = json.load(f)
            if not isinstance(s, dict):
                s = {}
    except Exception:
        s = {}
    for k, v in DEFAULT_SETTINGS.items():
        s.setdefault(k, v)
    try:
        s['volume'] = float(s.get('volume', DEFAULT_SETTINGS['volume']))
        s['sensitivity'] = float(s.get('sensitivity', DEFAULT_SETTINGS['sensitivity']))
        s['mic_threshold'] = float(s.get('mic_threshold', DEFAULT_SETTINGS['mic_threshold']))
        s['muted'] = bool(s.get('muted', DEFAULT_SETTINGS['muted']))
    except Exception:
        for k, v in DEFAULT_SETTINGS.items():
            s.setdefault(k, v)
    return s

def save_settings(s: Dict[str, Any]) -> None:
    try:
        with open(SETTINGS_PATH, 'w') as f:
            json.dump(s, f)
    except Exception:
        pass

def load_highscore() -> int:
    try:
        with open(HIGHSCORE_PATH, 'r') as f:
            return int(f.read())
    except Exception:
        return 0

def save_highscore(value: int) -> None:
    try:
        with open(HIGHSCORE_PATH, 'w') as f:
            f.write(str(int(value)))
    except Exception:
        pass

def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))

def draw_text(surf, text: str, size: int, x: int, y: int, color: Tuple[int, int, int] = WHITE) -> None:
    try:
        import pygame
        font = pygame.font.Font('freesansbold.ttf', size)
        surf.blit(font.render(text, True, color), (x, y))
    except Exception:
        pass

def load_sound_safe(path: str):
    try:
        import pygame
        return pygame.mixer.Sound(path)
    except Exception:
        return None
#santhosh reddy