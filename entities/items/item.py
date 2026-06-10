import pygame
from enum import Enum, auto


class ItemType(Enum):
    CONSUMABLE = auto()
    AMMO       = auto()
    WEAPON     = auto()
    ARMOR      = auto()


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
    ) -> None:
        self.name = name
        self.item_type = item_type
        self.stackable = stackable
        self.max_stack = max_stack
        self.stack_count: int = 1

        self.icon = pygame.Surface((icon_size, icon_size), pygame.SRCALPHA)
        self.icon.fill(icon_color)

    def get_tooltip(self) -> str:
        return self.name
