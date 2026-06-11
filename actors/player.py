import pygame
from actors.actor import Actor
from items.stats import Stats
from items.inventory import Inventory
from items.item import ItemType
from core.settings import Settings
from items.armor import Armor


class Player(Actor):
    """
    Human-controlled actor.
    Движение WASD, dash по Space в направлении движения.
    Характеристики (скорость, dash) берутся из self.stats — меняй Stats при смене брони.
    """

    def __init__(self, pos: tuple[float, float], settings: Settings, groups: list = ()) -> None:
        super().__init__(
            pos=pos,
            size=settings.player_size,
            color=settings.player_color,
            groups=groups,
        )
        self.settings = settings
        self.stats = Stats()
        self.speed = self.stats.speed

        self.facing = pygame.math.Vector2(0, 1)
        self._move_dir = pygame.math.Vector2(0, 0)

        self.stamina: float = self.stats.max_stamina
        self._dash_cooldown: float = 0.0
        self._dash_timer: float = 0.0
        self._dash_velocity = pygame.math.Vector2(0, 0)
        self._is_dashing: bool = False

        self.pouch = Inventory(
            capacity=4,
            typed_slots=[ItemType.WEAPON, ItemType.WEAPON, ItemType.ARMOR],
            owner=self,
        )
        self.backpack = Inventory(capacity=16)

        self.active_weapon_slot: int = 0

    def get_active_weapon(self):
        weapon_slots = [s for s in self.pouch.typed_slots if s.allowed_type == ItemType.WEAPON]
        if self.active_weapon_slot >= len(weapon_slots):
            return None
        slot = weapon_slots[self.active_weapon_slot]
        return slot.item if not slot.empty else None

    def get_armor_class(self) -> int:
        armor_slots = [s for s in self.pouch.typed_slots if s.allowed_type == ItemType.ARMOR]
        if armor_slots and not armor_slots[0].empty:
            item = armor_slots[0].item
            if isinstance(item, Armor):
                return item.tier
        return 0

    def switch_weapon(self, slot_index: int) -> bool:
        weapon_slots = [s for s in self.pouch.typed_slots if s.allowed_type == ItemType.WEAPON]
        if slot_index >= len(weapon_slots):
            return False
        self.active_weapon_slot = slot_index
        return True

    def try_dash(self) -> None:
        if self._is_dashing:
            return
        if self._dash_cooldown > 0:
            return
        if self.stamina < self.stats.dash_stamina_cost:
            return

        direction = self._move_dir if self._move_dir.length() > 0 else self.facing

        self.stamina -= self.stats.dash_stamina_cost
        self._is_dashing = True
        self._dash_timer = self.stats.dash_duration
        self._dash_cooldown = self.stats.dash_cooldown
        dash_speed = self.stats.dash_distance / self.stats.dash_duration
        self._dash_velocity = direction.normalize() * dash_speed

    def _handle_input(self) -> None:
        keys = pygame.key.get_pressed()

        direction = pygame.math.Vector2(0, 0)
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            direction.y -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            direction.y += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            direction.x -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            direction.x += 1

        if direction.length() > 0:
            direction = direction.normalize()

        self._move_dir = direction

        if not self._is_dashing:
            self.velocity = direction * self.speed

    def _update_dash(self, dt: float) -> None:
        self._dash_cooldown = max(0.0, self._dash_cooldown - dt)

        if self._is_dashing:
            self._dash_timer -= dt
            self.velocity = self._dash_velocity
            if self._dash_timer <= 0:
                self._is_dashing = False
                self.velocity = self._move_dir * self.speed

    def _update_stamina(self, dt: float) -> None:
        if not self._is_dashing:
            self.stamina = min(
                self.stats.max_stamina,
                self.stamina + self.stats.stamina_regen * dt,
            )

    def update(self, dt: float, walls: pygame.sprite.Group = None) -> None:
        self._handle_input()
        self._update_dash(dt)
        self._update_stamina(dt)
        super().update(dt, walls)
