import pygame
import math
from core.settings import Settings
from entities.combat.bullet import Bullet


class Weapon(pygame.sprite.Sprite):
    """
    Оружие прикреплено к владельцу (owner — Actor или Player).
    Вращается в сторону курсора мыши.
    При выстреле создаёт Bullet в переданную группу.

    Почему Sprite, а не просто атрибут?
      — Позже можно дропнуть на пол (просто убрать owner)
      — Можно дать врагу без изменений в классе врага
      — Рендерится отдельно, можно управлять слоями (поверх / под игроком)
    """

    def __init__(
        self,
        owner,
        settings: Settings,
        bullet_group: pygame.sprite.Group,
        all_sprites: pygame.sprite.Group,
    ) -> None:
        super().__init__(all_sprites)   # weapon сам добавляется в all_sprites

        self.owner = owner
        self.settings = settings
        self.bullet_group = bullet_group
        self.all_sprites = all_sprites
        
        self._fire_cooldown: float = 0.0
        
        w = settings.weapon_width
        h = settings.weapon_height
        self._base_image = pygame.Surface((w, h), pygame.SRCALPHA)
        self._base_image.fill(settings.weapon_color)

        self.image = self._base_image.copy()
        self.rect = self.image.get_rect()

        self.aim_dir = pygame.math.Vector2(1, 0)

    def update(self, dt: float, camera_offset: pygame.math.Vector2) -> None:
        """
        dt             — секунды с прошлого кадра
        camera_offset  — нужен чтобы перевести экранные координаты мыши
                         в мировые координаты
        """
        self._fire_cooldown = max(0.0, self._fire_cooldown - dt)
        self._update_aim(camera_offset)
        self._update_transform()

    def try_shoot(self) -> None:
        if self._fire_cooldown > 0:
            return

        self._fire_cooldown = self.settings.fire_rate

        offset = self.aim_dir * (
            self.settings.weapon_offset + self.settings.weapon_width
        )
        spawn = self.owner.pos + offset

        Bullet(
            pos=(spawn.x, spawn.y),
            direction=self.aim_dir,
            settings=self.settings,
            groups=[self.bullet_group, self.all_sprites],  # ← вот здесь
        )

    def _update_aim(self, camera_offset: pygame.math.Vector2) -> None:
        """Вычисляем направление от игрока к курсору в мировых координатах."""
        mouse_screen = pygame.math.Vector2(pygame.mouse.get_pos())
        mouse_world = mouse_screen + camera_offset

        delta = mouse_world - self.owner.pos
        if delta.length() > 0:
            self.aim_dir = delta.normalize()
            self.owner.facing = self.aim_dir.copy()

    def _update_transform(self) -> None:
        """Поворачиваем спрайт и позиционируем рядом с владельцем."""
        angle = -math.degrees(math.atan2(self.aim_dir.y, self.aim_dir.x))

        self.image = pygame.transform.rotate(self._base_image, angle)
        self.rect = self.image.get_rect()

        offset = self.aim_dir * self.settings.weapon_offset
        self.rect.center = (
            round(self.owner.pos.x + offset.x),
            round(self.owner.pos.y + offset.y),
        )
