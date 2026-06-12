import pygame
import math
import random


class Bullet(pygame.sprite.Sprite):
    """
    Снаряд. Летит по прямой, живёт ограниченное время.
    Если can_ricochet=True — при ударе о стену отражается один раз.
    """

    def __init__(
        self,
        pos: tuple[float, float],
        direction: pygame.math.Vector2,
        speed: float,
        lifetime: float,
        damage: int,
        size: int,
        color: tuple[int, int, int],
        stopping_effect: float,
        groups: list = (),
        armor_pen: int = 0,
        can_ricochet: bool = False,
        ricochet_spread: float = 8.0,
        ricochet_damage_mult: float = 0.7,
    ) -> None:
        super().__init__(*groups)

        self.damage          = damage
        self.stopping_effect = stopping_effect
        self.armor_pen       = armor_pen
        self.lifetime        = lifetime
        self.color           = color
        self.size            = size

        self.image = pygame.Surface((size, size), pygame.SRCALPHA)
        self.image.fill(color)
        self.rect  = self.image.get_rect(center=pos)

        self.pos      = pygame.math.Vector2(pos)
        self.velocity = direction.normalize() * speed

        self.can_ricochet         = can_ricochet
        self.ricochet_spread      = ricochet_spread
        self.ricochet_damage_mult = ricochet_damage_mult
        self.ricocheted           = False   # можно только один раз

    def update(self, dt: float) -> None:
        self.lifetime -= dt
        if self.lifetime <= 0:
            self.kill()
            return
        self.pos += self.velocity * dt
        self.rect.center = (round(self.pos.x), round(self.pos.y))

    def do_ricochet(self, wall_rect: pygame.Rect) -> bool:
        """
        Вычисляет нормаль стены по стороне перекрытия и отражает velocity.
        Возвращает True если рикошет произошёл, False если угол слишком крутой.
        Вызывается из CombatManager — только для can_ricochet пуль.
        """
        if self.ricocheted:
            return False

        normal = self._wall_normal(wall_rect)
        if normal is None:
            return False

        vel_norm = self.velocity.normalize()
        raw_dot  = vel_norm.dot(normal)
        if raw_dot >= 0:
            return False   # пуля уже улетает от стены

        # angle_from_surface: угол между пулей и поверхностью стены
        # 0°  = пуля летит точно вдоль стены (идеальный скользящий)
        # 90° = пуля летит точно в лоб (перпендикулярно)
        angle_from_surface = 90.0 - math.degrees(math.acos(max(0.0, min(1.0, -raw_dot))))

        # рикошет невозможен при угле > 70° (почти в лоб)
        if angle_from_surface > 70:
            return False

        # шанс убывает с ростом угла
        # 0–20°→90%   20–45°→50%   45–70°→15%
        if angle_from_surface <= 20:
            chance = 0.90
        elif angle_from_surface <= 45:
            chance = 0.90 - (angle_from_surface - 20) / 25 * 0.40
        else:
            chance = 0.50 - (angle_from_surface - 45) / 25 * 0.35

        if random.random() > chance:
            return False

        # отражение: v' = v - 2(v·n)n  (нормаль смотрит от стены к пуле)
        reflected = vel_norm - 2 * vel_norm.dot(normal) * normal

        # случайное отклонение
        if self.ricochet_spread > 0:
            angle_rad    = math.radians(
                random.uniform(-self.ricochet_spread / 2, self.ricochet_spread / 2)
            )
            cos_a, sin_a = math.cos(angle_rad), math.sin(angle_rad)
            reflected    = pygame.math.Vector2(
                reflected.x * cos_a - reflected.y * sin_a,
                reflected.x * sin_a + reflected.y * cos_a,
            )

        self.velocity       = reflected.normalize() * self.velocity.length()
        self.damage         = int(self.damage * self.ricochet_damage_mult)
        self.ricocheted     = True

        # немного сдвигаем пулю от стены чтобы не застряла
        self.pos += self.velocity.normalize() * (self.size + 2)
        self.rect.center = (round(self.pos.x), round(self.pos.y))
        return True

    def _wall_normal(self, wall_rect: pygame.Rect) -> pygame.math.Vector2 | None:
        """Определяет нормаль стены по стороне с наименьшим перекрытием.
        Нормаль всегда направлена навстречу летящей пуле."""
        overlap_x = min(self.rect.right,  wall_rect.right)  - max(self.rect.left, wall_rect.left)
        overlap_y = min(self.rect.bottom, wall_rect.bottom) - max(self.rect.top,  wall_rect.top)

        if overlap_x <= 0 or overlap_y <= 0:
            return None

        if overlap_x < overlap_y:
            # удар по левой или правой стороне стены
            # нормаль смотрит от стены к пуле
            nx = -1.0 if self.rect.centerx < wall_rect.centerx else 1.0
            return pygame.math.Vector2(nx, 0)
        else:
            ny = -1.0 if self.rect.centery < wall_rect.centery else 1.0
            return pygame.math.Vector2(0, ny)
