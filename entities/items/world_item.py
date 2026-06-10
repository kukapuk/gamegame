import pygame
from entities.items.item import Item
from entities.items.weapon_item import WeaponItem


class WorldItem(pygame.sprite.Sprite):
    """
    Предмет лежащий в игровом мире.
    Отображается как силуэт предмета на полу.
    Игрок может подобрать через E или drag & drop из открытого рюкзака.
    """

    PICKUP_RADIUS  = 64
    BOB_SPEED      = 2.0
    BOB_AMPLITUDE  = 3.0
    SHADOW_COLOR   = (0, 0, 0, 60)

    def __init__(self, item: Item, pos: tuple[float, float], groups: list = ()) -> None:
        super().__init__(*groups)

        self.item        = item
        self.world_pos   = pygame.math.Vector2(pos)
        self._bob_timer  = 0.0

        self.image = self._build_image()
        self.rect  = self.image.get_rect(center=(round(pos[0]), round(pos[1])))

    def _build_image(self) -> pygame.Surface:
        if isinstance(self.item, WeaponItem):
            s   = self.item.stats
            w   = max(s.width, 16)
            h   = max(s.height, 6)
            surf = pygame.Surface((w, h), pygame.SRCALPHA)
            surf.fill(self.item.stats.color)
            return surf

        sz   = 20
        surf = pygame.Surface((sz, sz), pygame.SRCALPHA)
        surf.fill(self.item.icon.get_at((0, 0)))
        return surf

    def is_in_pickup_range(self, player_pos: pygame.math.Vector2) -> bool:
        return (self.world_pos - player_pos).length() <= self.PICKUP_RADIUS

    def update(self, dt: float) -> None:
        self._bob_timer += dt
        offset_y = self.BOB_AMPLITUDE * pygame.math.Vector2(0, 1).rotate(
            self._bob_timer * self.BOB_SPEED * 57.3
        ).y
        self.rect.center = (
            round(self.world_pos.x),
            round(self.world_pos.y + offset_y),
        )
