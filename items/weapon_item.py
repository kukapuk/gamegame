import pygame
from dataclasses import dataclass, field
from items.item import Item, ItemType
from items.ammo import AmmoType


@dataclass
class WeaponStats:
    damage: int
    fire_rate: float
    bullet_speed: float
    bullet_lifetime: float
    armor_pen: int
    stopping_effect: float
    auto_fire: bool
    spread: float
    pellets: int
    width: int
    height: int
    color: tuple[int, int, int]
    bullet_size: int
    bullet_color: tuple[int, int, int]
    ammo_type: AmmoType
    mag_size: int
    reload_time: float
    sound_radius: float        = 400.0
    reload_sound_radius: float = 80.0   # тихий щелчок — слышно только вблизи
    screen_shake:       float  = 2.5    # амплитуда тряски камеры при выстреле
    recoil_distance: float = 6.0
    recoil_recovery: float = 12.0
    aim_radius: float      = 160.0

    # Размер в сетке рюкзака (cols, rows) в горизонтальном положении
    grid_size: tuple = (2, 1)

    # --- загрязнение ---
    dirt_per_shot:     float = 0.008  # деградация за выстрел
    first_shot_spread: float = 3.0    # доп. разброс первого выстрела (градусы)
    jam_chance_low:    float = 0.03   # шанс клина при cleanliness 0.25–0.5
    jam_chance_high:   float = 0.10   # шанс клина при cleanliness < 0.25

    # рикошет
    ricochet:             bool  = False
    ricochet_spread:      float = 8.0
    ricochet_damage_mult: float = 0.7

    # вспышка выстрела
    flash_color:    tuple = (255, 120, 30)  # оранжево-красный
    flash_radius:   float = 55.0
    flash_duration: float = 0.07

    # стелс
    suppressed:              bool  = False
    insta_kill_unaware:      bool  = False
    suppressed_sound_radius: float = 40.0


# Пороги cleanliness
CLEAN_THRESHOLD  = 0.75   # выше — всё нормально
DIRTY_THRESHOLD  = 0.50   # ниже — spread × 1.5, first_shot активен
FILTHY_THRESHOLD = 0.25   # ниже — spread × 2.5, шанс клина low
                           # ниже 0.0 — spread × 4,  шанс клина high


class WeaponItem(Item):
    """
    Оружие как предмет инвентаря.
    stats       — константы оружия (урон, скорострельность и т.д.)
    cleanliness — runtime состояние: 1.0 чистое → 0.0 засранное
    jammed      — заклинено, не стреляет
    """

    def __init__(self, name: str, stats: WeaponStats, icon_color: tuple) -> None:
        super().__init__(
            name=name,
            item_type=ItemType.WEAPON,
            icon_color=icon_color,
            stackable=False,
            grid_size=stats.grid_size,
        )
        self.stats       = stats
        self.mag_current: int   = -1
        self.cleanliness: float = 1.0
        self.jammed:      bool  = False
        self._rebuild_icon()

    def _rebuild_icon(self) -> None:
        """Строит иконку из спрайт-листа, fallback — цветной квадрат."""
        try:
            from combat.weapon_sprites import get_weapon_sprite
            sprite = get_weapon_sprite(self.name)
            if sprite:
                self.icon = pygame.transform.scale(sprite, (40, 40))
                return
        except Exception:
            pass
        # fallback уже задан в Item.__init__

    def effective_spread(self) -> float:
        """Итоговый разброс с учётом загрязнения."""
        base = self.stats.spread
        if self.cleanliness >= DIRTY_THRESHOLD:
            return base
        if self.cleanliness >= FILTHY_THRESHOLD:
            return base * 2.5
        return base * 4.0

    def jam_chance(self) -> float:
        if self.cleanliness >= DIRTY_THRESHOLD:
            return 0.0
        if self.cleanliness >= FILTHY_THRESHOLD:
            return self.stats.jam_chance_low
        return self.stats.jam_chance_high

    def get_tooltip(self) -> str:
        clean_pct = int(self.cleanliness * 100)
        jam_str   = "  [JAMMED]" if self.jammed else ""
        return (
            f"{self.name}  DMG:{self.stats.damage}  "
            f"AP:{self.stats.armor_pen}  "
            f"clean:{clean_pct}%{jam_str}"
        )


def make_carbine() -> WeaponItem:
    return WeaponItem(
        name="Carbine",
        icon_color=(100, 160, 100),
        stats=WeaponStats(
            damage=12,
            fire_rate=0.12,
            bullet_speed=1180.0,
            bullet_lifetime=1.0,
            armor_pen=2,
            stopping_effect=0.3,
            auto_fire=True,
            spread=6.0,
            pellets=1,
            width=22,
            height=8,
            color=(120, 180, 100),
            bullet_size=5,
            bullet_color=(220, 240, 120),
            ammo_type=AmmoType.CARBINE,
            mag_size=30,
            reload_time=2.0,
            recoil_distance=8.0,
            recoil_recovery=14.0,
            aim_radius=200.0,
            dirt_per_shot=0.008,      # ~125 выстрелов до нуля
            first_shot_spread=4.0,
            jam_chance_low=0.03,
            jam_chance_high=0.10,
            ricochet=True,
            ricochet_spread=6.0,
            ricochet_damage_mult=0.7,
            grid_size=(2, 1),
            flash_color=(255, 160, 40),
            flash_radius=45.0,
            flash_duration=0.06,
            screen_shake=2.0,
        ),
    )


def make_shotgun() -> WeaponItem:
    return WeaponItem(
        name="Shotgun",
        icon_color=(180, 120, 60),
        stats=WeaponStats(
            damage=18,
            fire_rate=0.75,
            bullet_speed=900.0,
            bullet_lifetime=0.28,
            armor_pen=0,
            stopping_effect=0.85,
            auto_fire=False,
            spread=18.0,
            pellets=7,
            width=26,
            height=10,
            color=(200, 140, 70),
            bullet_size=4,
            bullet_color=(255, 200, 80),
            ammo_type=AmmoType.SHOTGUN,
            mag_size=8,
            reload_time=2.5,
            recoil_distance=18.0,
            recoil_recovery=8.0,
            aim_radius=130.0,
            dirt_per_shot=0.015,      # ~65 выстрелов, грязнится быстрее
            first_shot_spread=6.0,
            jam_chance_low=0.04,
            jam_chance_high=0.12,
            grid_size=(2, 1),
            flash_color=(255, 80, 20),   # ярко-красная большая вспышка
            flash_radius=90.0,
            flash_duration=0.10,
            screen_shake=5.5,
        ),
    )


def make_sniper() -> WeaponItem:
    return WeaponItem(
        name="Sniper Rifle",
        icon_color=(80, 120, 200),
        stats=WeaponStats(
            damage=85,
            fire_rate=1.4,
            bullet_speed=1900.0,
            bullet_lifetime=1.4,
            armor_pen=3,
            stopping_effect=0.1,
            auto_fire=False,
            spread=0.0,
            pellets=1,
            width=34,
            height=6,
            color=(100, 140, 220),
            bullet_size=5,
            bullet_color=(180, 220, 255),
            ammo_type=AmmoType.SNIPER,
            mag_size=1,
            reload_time=3.0,
            recoil_distance=24.0,
            recoil_recovery=6.0,
            aim_radius=300.0,
            dirt_per_shot=0.004,      # ~250 выстрелов, грязнится медленно
            first_shot_spread=2.0,
            jam_chance_low=0.02,
            jam_chance_high=0.07,
            ricochet=True,
            ricochet_spread=6.0,
            ricochet_damage_mult=0.7,
            grid_size=(3, 1),
            flash_color=(200, 230, 255),   # холодная белая вспышка
            flash_radius=65.0,
            flash_duration=0.05,
            screen_shake=7.0,
        ),
    )


def make_suppressed_pistol() -> WeaponItem:
    """Пистолет с глушителем — тихий, ваншот врагов не в агре."""
    return WeaponItem(
        name="Suppressed Pistol",
        icon_color=(80, 80, 90),
        stats=WeaponStats(
            damage=5,
            fire_rate=0.4,
            bullet_speed=620.0,
            bullet_lifetime=0.7,
            armor_pen=1,
            stopping_effect=0.1,
            auto_fire=False,
            spread=1.5,
            pellets=1,
            width=20,
            height=8,
            color=(60, 60, 70),
            bullet_size=4,
            bullet_color=(180, 220, 180),
            ammo_type=AmmoType.PISTOL,
            mag_size=10,
            reload_time=1.8,
            sound_radius=400.0,
            aim_radius=140.0,
            dirt_per_shot=0.006,
            first_shot_spread=1.0,
            jam_chance_low=0.02,
            jam_chance_high=0.06,
            grid_size=(2, 1),
            flash_color=(180, 220, 180),
            flash_radius=25.0,
            flash_duration=0.04,
            suppressed=True,
            insta_kill_unaware=True,
            suppressed_sound_radius=40.0,
            screen_shake=0.5,
        ),
    )
