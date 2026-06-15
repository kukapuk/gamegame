"""
enemy_weapon.py — оружие врага с магазином, перезарядкой и режимами стрельбы.

Режимы (FireMode):
  SINGLE  — один выстрел за нажатие
  BURST   — очередь из N пуль с коротким интервалом
  AUTO    — автомат, стреляет пока cooldown позволяет

Звук перезарядки эмитится через callback on_sound(pos, radius) —
game_scene передаёт его врагам через hear_sound.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
import random


class FireMode(Enum):
    SINGLE = auto()
    BURST  = auto()
    AUTO   = auto()


@dataclass
class EnemyWeaponStats:
    # урон и пуля
    damage:        int   = 15
    armor_pen:     int   = 0
    bullet_speed:  float = 380.0
    bullet_color:  tuple = (255, 200, 50)
    spread_deg:    float = 4.0       # разброс в градусах

    # магазин
    mag_size:      int   = 20
    reload_time:   float = 2.5

    # стрельба
    fire_mode:     FireMode = FireMode.SINGLE
    fire_rate:     float    = 1.2    # секунд между выстрелами (SINGLE/AUTO)
    burst_count:   int      = 3      # пуль в очереди (BURST)
    burst_interval: float   = 0.09  # секунд между пулями в очереди

    # звук
    shot_sound_radius:   float = 380.0
    reload_sound_radius: float = 80.0   # тихий — слышно только вблизи


class EnemyWeapon:
    """
    Состояние оружия конкретного врага.
    Вызывай update(dt) каждый кадр, try_fire() когда хочешь выстрелить.
    """

    def __init__(self, stats: EnemyWeaponStats) -> None:
        self.stats        = stats
        self.mag_current  = stats.mag_size
        self.reloading    = False
        self._reload_timer = 0.0
        self._fire_cooldown = 0.0

        self._burst_left:    int   = 0
        self._burst_timer:   float = 0.0
        self._burst_dir            = None   # сохранённое направление для burst

        self.on_fire:  callable = None
        self.on_sound: callable = None

    def update(self, dt: float, owner_pos) -> None:
        self._fire_cooldown = max(0.0, self._fire_cooldown - dt)

        if self.reloading:
            self._reload_timer -= dt
            if self._reload_timer <= 0:
                self.reloading   = False
                self.mag_current = self.stats.mag_size
            return

        # burst continuation — используем сохранённое направление
        if self._burst_left > 0:
            self._burst_timer -= dt
            if self._burst_timer <= 0:
                self._shoot_one(owner_pos, self._burst_dir)
                self._burst_left -= 1
                self._burst_timer = self.stats.burst_interval
                if self.mag_current <= 0:
                    self._start_reload(owner_pos)
                    self._burst_left = 0

    def try_fire(self, owner_pos, direction) -> bool:
        """
        Попытка выстрелить. Возвращает True если выстрел начат.
        direction — нормализованный Vector2 к цели.
        """
        if self.reloading:
            return False
        if self._fire_cooldown > 0:
            return False
        if self.mag_current <= 0:
            self._start_reload(owner_pos)
            return False

        mode = self.stats.fire_mode

        if mode == FireMode.SINGLE or mode == FireMode.AUTO:
            self._shoot_one(owner_pos, direction)
            self._fire_cooldown = self.stats.fire_rate

        elif mode == FireMode.BURST:
            if self._burst_left > 0:
                return False
            self._burst_dir = direction   # сохраняем направление
            self._shoot_one(owner_pos, direction)
            self._burst_left  = self.stats.burst_count - 1
            self._burst_timer = self.stats.burst_interval
            self._fire_cooldown = self.stats.fire_rate

        # автоперезарядка когда магазин пуст
        if self.mag_current <= 0:
            self._start_reload(owner_pos)

        return True

    def try_fire_suppress(self, owner_pos, direction, extra_spread: float = 25.0) -> bool:
        """Подавляющий огонь — с большим разбросом, не ждёт cooldown так строго."""
        if self.reloading:
            return False
        if self._fire_cooldown > 0:
            return False
        if self.mag_current <= 0:
            self._start_reload(owner_pos)
            return False
        import math, random, pygame
        # применяем увеличенный разброс вручную
        angle = math.atan2(direction.y, direction.x)
        angle += math.radians(random.uniform(-extra_spread, extra_spread))
        spread_dir = pygame.math.Vector2(math.cos(angle), math.sin(angle))
        self._shoot_one(owner_pos, spread_dir)
        self._fire_cooldown = self.stats.fire_rate * 0.7   # чуть быстрее обычного
        if self.mag_current <= 0:
            self._start_reload(owner_pos)
        return True

    @property
    def can_fire(self) -> bool:
        return (not self.reloading
                and self._fire_cooldown <= 0
                and (self.mag_current > 0 or self._burst_left > 0))

    # ── Private ───────────────────────────────────────────────────────

    def _shoot_one(self, owner_pos, direction=None) -> None:
        """Выпускает одну пулю (с разбросом)."""
        self.mag_current = max(0, self.mag_current - 1)

        if self.on_fire and direction is not None:
            spread = self._apply_spread(direction)
            self.on_fire(owner_pos, spread)
        elif self.on_fire and direction is None:
            # burst — используем сохранённое направление
            pass

        if self.on_sound:
            self.on_sound(owner_pos, self.stats.shot_sound_radius)

    def _apply_spread(self, direction):
        import math, pygame
        if self.stats.spread_deg <= 0:
            return direction
        angle = math.atan2(direction.y, direction.x)
        angle += math.radians(
            random.uniform(-self.stats.spread_deg, self.stats.spread_deg)
        )
        return pygame.math.Vector2(math.cos(angle), math.sin(angle))

    def _start_reload(self, owner_pos) -> None:
        if self.reloading:
            return
        self.reloading     = True
        self._reload_timer = self.stats.reload_time
        if self.on_sound:
            self.on_sound(owner_pos, self.stats.reload_sound_radius)


# ── Готовые конфигурации для фабрик ───────────────────────────────────

def pistol_stats() -> EnemyWeaponStats:
    """Пистолет — одиночный, небольшой магазин."""
    return EnemyWeaponStats(
        damage=12, armor_pen=0, bullet_speed=340.0,
        bullet_color=(255, 220, 80),
        spread_deg=5.0, mag_size=12, reload_time=2.0,
        fire_mode=FireMode.SINGLE, fire_rate=1.0,
        shot_sound_radius=300.0, reload_sound_radius=70.0,
    )


def smg_stats() -> EnemyWeaponStats:
    """Пистолет-пулемёт — автомат, большой магазин, низкий урон."""
    return EnemyWeaponStats(
        damage=8, armor_pen=0, bullet_speed=360.0,
        bullet_color=(200, 220, 100),
        spread_deg=7.0, mag_size=30, reload_time=2.2,
        fire_mode=FireMode.AUTO, fire_rate=0.12,
        shot_sound_radius=360.0, reload_sound_radius=80.0,
    )


def assault_rifle_stats() -> EnemyWeaponStats:
    """Автомат — очередь 3 пули, средний урон."""
    return EnemyWeaponStats(
        damage=15, armor_pen=1, bullet_speed=420.0,
        bullet_color=(180, 200, 255),
        spread_deg=3.5, mag_size=25, reload_time=2.4,
        fire_mode=FireMode.BURST, fire_rate=0.7,
        burst_count=3, burst_interval=0.08,
        shot_sound_radius=420.0, reload_sound_radius=90.0,
    )


def shotgun_stats() -> EnemyWeaponStats:
    """Дробовик — одиночный, большой разброс, высокий урон."""
    return EnemyWeaponStats(
        damage=25, armor_pen=0, bullet_speed=300.0,
        bullet_color=(255, 160, 60),
        spread_deg=14.0, mag_size=6, reload_time=3.0,
        fire_mode=FireMode.SINGLE, fire_rate=1.4,
        shot_sound_radius=450.0, reload_sound_radius=100.0,
    )


def sniper_stats() -> EnemyWeaponStats:
    """Снайперская винтовка — одиночный, точный, высокий урон и пробитие."""
    return EnemyWeaponStats(
        damage=55, armor_pen=3, bullet_speed=700.0,
        bullet_color=(100, 220, 255),
        spread_deg=0.5, mag_size=5, reload_time=3.5,
        fire_mode=FireMode.SINGLE, fire_rate=2.5,
        shot_sound_radius=500.0, reload_sound_radius=90.0,
    )
