import pygame
import math
import random
from core.settings import Settings
from combat.bullet import Bullet
from items.weapon_item import WeaponItem
from items.ammo import AmmoItem


class Weapon(pygame.sprite.Sprite):
    """
    Визуальный спрайт оружия, прикреплённый к владельцу.
    Управляет магазином, перезарядкой, поиском патронов в инвентаре владельца.
    """

    def __init__(
        self,
        owner,
        settings: Settings,
        bullet_group: pygame.sprite.Group,
        all_sprites: pygame.sprite.Group,
        weapon_item: WeaponItem = None,
    ) -> None:
        super().__init__(all_sprites)

        self.owner        = owner
        self.settings     = settings
        self.bullet_group = bullet_group
        self.all_sprites  = all_sprites

        self._fire_cooldown: float  = 0.0
        self._reload_timer: float   = 0.0
        self.reloading: bool        = False
        self.mag_current: int       = 0
        self.aim_dir = pygame.math.Vector2(1, 0)

        self._weapon_item: WeaponItem = None
        self._base_image = pygame.Surface((
            settings.weapon_width, settings.weapon_height
        ), pygame.SRCALPHA)
        self._base_image.fill(settings.weapon_color)
        self.image = self._base_image.copy()
        self.rect  = self.image.get_rect()

        if weapon_item:
            self.equip(weapon_item)

    @property
    def has_weapon(self) -> bool:
        return self._weapon_item is not None

    @property
    def mag_size(self) -> int:
        return self._weapon_item.stats.mag_size if self._weapon_item else 0

    def equip(self, weapon_item) -> None:
        self._weapon_item   = weapon_item
        self._fire_cooldown = 0.0
        self.reloading      = False
        self._reload_timer  = 0.0
        if weapon_item:
            s = weapon_item.stats
            self._build_visual(s.width, s.height, s.color)
            if weapon_item.mag_current < 0:
                weapon_item.mag_current = self._take_ammo(s.mag_size)
            self.mag_current = weapon_item.mag_current
        else:
            self.mag_current = 0

    def try_reload(self) -> None:
        if not self._weapon_item or self.reloading:
            return
        if self.mag_current == self._weapon_item.stats.mag_size:
            return
        if self._find_ammo_count() == 0:
            return
        self.reloading     = True
        self._reload_timer = self._weapon_item.stats.reload_time

    def try_shoot(self) -> None:
        if not self._weapon_item or self.reloading:
            return
        if self._fire_cooldown > 0:
            return
        if self.mag_current <= 0:
            self.try_reload()
            return

        s = self._weapon_item.stats
        self._fire_cooldown = s.fire_rate
        self.mag_current -= 1

        self._weapon_item.mag_current = self.mag_current

        w      = self._base_image.get_width()
        offset = self.aim_dir * (self.settings.weapon_offset + w)
        spawn  = self.owner.pos + offset

        for _ in range(s.pellets):
            direction = self._apply_spread(self.aim_dir, s.spread)
            Bullet(
                pos=(spawn.x, spawn.y),
                direction=direction,
                speed=s.bullet_speed,
                lifetime=s.bullet_lifetime,
                damage=s.damage,
                size=s.bullet_size,
                color=s.bullet_color,
                armor_penetration=s.armor_penetration,
                stopping_effect=s.stopping_effect,
                groups=[self.bullet_group, self.all_sprites],
            )

        if self.mag_current == 0:
            self.try_reload()

    def update(self, dt: float, camera_offset: pygame.math.Vector2) -> None:
        self._fire_cooldown = max(0.0, self._fire_cooldown - dt)
        self._update_reload(dt)
        self._update_aim(camera_offset)
        self._update_transform()

    def _update_reload(self, dt: float) -> None:
        if not self.reloading:
            return
        self._reload_timer -= dt
        if self._reload_timer <= 0:
            self.reloading = False
            needed = self._weapon_item.stats.mag_size
            self.mag_current = self._take_ammo(needed)
            self._weapon_item.mag_current = self.mag_current

    def _find_ammo_count(self) -> int:
        if not self._weapon_item:
            return 0
        ammo_type = self._weapon_item.stats.ammo_type
        total = 0
        for inv in [self.owner.pouch, self.owner.backpack]:
            for slot in inv.all_slots():
                if slot.item and isinstance(slot.item, AmmoItem):
                    if slot.item.ammo_type == ammo_type:
                        total += slot.item.stack_count
        return total

    def _take_ammo(self, needed: int) -> int:
        if not self._weapon_item:
            return 0
        if not hasattr(self.owner, 'pouch') or not hasattr(self.owner, 'backpack'):
            return 0
        ammo_type = self._weapon_item.stats.ammo_type
        taken = 0
        for inv in [self.owner.pouch, self.owner.backpack]:
            for slot in inv.all_slots():
                if needed <= 0:
                    break
                if slot.item and isinstance(slot.item, AmmoItem):
                    if slot.item.ammo_type == ammo_type:
                        available = slot.item.stack_count
                        take      = min(available, needed)
                        slot.item.stack_count -= take
                        taken  += take
                        needed -= take
                        if slot.item.stack_count <= 0:
                            slot.item = None
        return taken

    def _build_visual(self, w: int, h: int, color: tuple) -> None:
        self._base_image = pygame.Surface((w, h), pygame.SRCALPHA)
        self._base_image.fill(color)

    def _apply_spread(self, direction: pygame.math.Vector2, spread_deg: float) -> pygame.math.Vector2:
        if spread_deg == 0:
            return direction.copy()
        angle    = math.radians(random.uniform(-spread_deg / 2, spread_deg / 2))
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        return pygame.math.Vector2(
            direction.x * cos_a - direction.y * sin_a,
            direction.x * sin_a + direction.y * cos_a,
        )

    def _update_aim(self, camera_offset: pygame.math.Vector2) -> None:
        mouse_screen = pygame.math.Vector2(pygame.mouse.get_pos())
        mouse_world  = mouse_screen + camera_offset
        delta = mouse_world - self.owner.pos
        if delta.length() > 0:
            self.aim_dir      = delta.normalize()
            self.owner.facing = self.aim_dir.copy()

    def _update_transform(self) -> None:
        angle = -math.degrees(math.atan2(self.aim_dir.y, self.aim_dir.x))
        self.image = pygame.transform.rotate(self._base_image, angle)
        self.rect  = self.image.get_rect()
        offset = self.aim_dir * self.settings.weapon_offset
        self.rect.center = (
            round(self.owner.pos.x + offset.x),
            round(self.owner.pos.y + offset.y),
        )
