import pygame
from core.visual.sprite_sheet import SpriteSheet

# Путь к листу
WEAPONS_SHEET_PATH = "assets/combat/weapons.png"

# Координаты на листе: name → (x, y, w, h)
# Ячейка 80×16 пикселей, три оружия в ряд
WEAPON_SPRITES: dict[str, tuple] = {
    "Carbine":      (0,   0, 80, 16),
    "Shotgun":      (80,  0, 80, 16),
    "Sniper Rifle": (160, 0, 80, 16),
}

_sheet: SpriteSheet = None


def _get_sheet() -> SpriteSheet:
    global _sheet
    if _sheet is None:
        _sheet = SpriteSheet(WEAPONS_SHEET_PATH)
    return _sheet


def get_weapon_sprite(name: str) -> pygame.Surface | None:
    """
    Возвращает спрайт оружия по имени WeaponItem.name.
    Возвращает None если оружие не найдено в реестре.
    """
    entry = WEAPON_SPRITES.get(name)
    if entry is None:
        return None
    return _get_sheet().get(*entry)
