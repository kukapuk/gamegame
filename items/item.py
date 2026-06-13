import pygame
from enum import Enum, auto


class ItemType(Enum):
    CONSUMABLE = auto()
    AMMO       = auto()
    WEAPON     = auto()
    ARMOR      = auto()
    HELMET     = auto()


class Item:
    """
    Базовый класс для всех предметов в игре.
    Не является спрайтом — предмет это данные, не визуальный объект.
    Визуал (иконка) рисуется через HUD.
    """

    def __init__(
        self,
        name: str,
        item_type: ItemType,
        icon_color: tuple[int, int, int],
        icon_size: int = 40,
        stackable: bool = False,
        max_stack: int = 1,
        grid_size: tuple[int, int] = (1, 1),
    ) -> None:
        self.name = name
        self.item_type = item_type
        self.stackable = stackable
        self.max_stack = max_stack
        self.stack_count: int = 1

        # Размер в сетке рюкзака: (cols, rows) в горизонтальном положении.
        # При повороте на 90° cols и rows меняются местами.
        self.grid_size: tuple[int, int] = grid_size
        self.grid_rotated: bool = False  # повёрнут ли предмет сейчас

        self.icon = pygame.Surface((icon_size, icon_size), pygame.SRCALPHA)
        self.icon.fill(icon_color)

    @property
    def effective_size(self) -> tuple[int, int]:
        """Актуальный размер с учётом поворота: (cols, rows)."""
        cols, rows = self.grid_size
        if self.grid_rotated:
            return (rows, cols)
        return (cols, rows)

    def get_tooltip(self) -> str:
        return self.name
