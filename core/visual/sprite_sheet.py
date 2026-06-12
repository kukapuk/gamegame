import pygame


class SpriteSheet:
    """
    Загружает PNG-лист и вырезает спрайты по координатам.
    Все спрайты кэшируются — повторный get() не делает новый subsurface.
    """

    def __init__(self, path: str) -> None:
        self._sheet = pygame.image.load(path).convert_alpha()
        self._cache: dict[tuple, pygame.Surface] = {}

    def get(self, x: int, y: int, w: int, h: int) -> pygame.Surface:
        key = (x, y, w, h)
        if key not in self._cache:
            self._cache[key] = self._sheet.subsurface(pygame.Rect(x, y, w, h))
        return self._cache[key]

    def get_scaled(self, x: int, y: int, w: int, h: int,
                   target_w: int, target_h: int) -> pygame.Surface:
        """Вырезает и масштабирует до нужного размера."""
        key = (x, y, w, h, target_w, target_h)
        if key not in self._cache:
            surf = self._sheet.subsurface(pygame.Rect(x, y, w, h))
            self._cache[key] = pygame.transform.scale(surf, (target_w, target_h))
        return self._cache[key]
