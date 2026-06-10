import pygame
import math
import random
from core.settings import Settings
from combat.bullet import Bullet
from items.weapon_item import WeaponItem


class Weapon(pygame.sprite.Sprite):
    """
    Визуальный спрайт оружия, прикреплённый к владельцу.
    Читает характеристики стрельбы из WeaponItem.
    Смена оружия — просто weapon.equip(new_weapon_item).
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

        self._fire_cooldown: float = 0.0
        self.aim_dir = pygame.math.Vector2(1, 0)

        self._weapon_item: WeaponItem = None
        self._base_image: pygame.Surface = None

        if weapon_item:
            self.equip(weapon_item)
        else:
            self._build_visual(settings.weapon_width, settings.weapon_height, settings.weapon_color)

        self.image = self._base_image.copy()
        self.rect  = self.image.get_rect()

    def equip(self, weapon_item) -> None:
        self._weapon_item = weapon_item
        if weapon_item:
            s = weapon_item.stats
            self._build_visual(s.width, s.height, s.color)
        self._fire_cooldown = 0.0

    @property
    def has_weapon(self) -> bool:
        return self._weapon_item is not None

    def _build_visual(self, w: int, h: int, color: tuple) -> None:
        self._base_image = pygame.Surface((w, h), pygame.SRCALPHA)
        self._base_image.fill(color)

    def update(self, dt: float, camera_offset: pygame.math.Vector2) -> None:
        self._fire_cooldown = max(0.0, self._fire_cooldown - dt)
        self._update_aim(camera_offset)
        self._update_transform()

    def try_shoot(self) -> None:
        if self._fire_cooldown > 0:
            return
        if not self._weapon_item:
            self._shoot_default()
            return

        s = self._weapon_item.stats
        self._fire_cooldown = s.fire_rate

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

    def _shoot_default(self) -> None:
        self._fire_cooldown = self.settings.fire_rate
        offset = self.aim_dir * (self.settings.weapon_offset + self.settings.weapon_width)
        spawn  = self.owner.pos + offset
        Bullet(
            pos=(spawn.x, spawn.y),
            direction=self.aim_dir,
            speed=self.settings.bullet_speed,
            lifetime=self.settings.bullet_lifetime,
            damage=self.settings.bullet_damage,
            size=self.settings.bullet_size,
            color=self.settings.bullet_color,
            armor_penetration=0.0,
            stopping_effect=0.0,
            groups=[self.bullet_group, self.all_sprites],
        )

    def _apply_spread(self, direction: pygame.math.Vector2, spread_deg: float) -> pygame.math.Vector2:
        if spread_deg == 0:
            return direction.copy()
        angle = math.radians(random.uniform(-spread_deg / 2, spread_deg / 2))
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
            self.aim_dir        = delta.normalize()
            self.owner.facing   = self.aim_dir.copy()

    def _update_transform(self) -> None:
        angle = -math.degrees(math.atan2(self.aim_dir.y, self.aim_dir.x))
        self.image = pygame.transform.rotate(self._base_image, angle)
        self.rect  = self.image.get_rect()
        offset = self.aim_dir * self.settings.weapon_offset
        self.rect.center = (
            round(self.owner.pos.x + offset.x),
            round(self.owner.pos.y + offset.y),
        )
