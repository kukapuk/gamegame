from dataclasses import dataclass
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
    sound_radius: float = 400.0
    recoil_distance: float = 6.0 # пикселей смещения назад при выстреле
    recoil_recovery: float = 12.0 # скорость возврата - множитель lerp


class WeaponItem(Item):
    """
    Оружие как предмет инвентаря.
    Хранит все характеристики стрельбы — Weapon-спрайт читает их отсюда.
    """

    def __init__(self, name: str, stats: WeaponStats, icon_color: tuple) -> None:
        super().__init__(
            name=name,
            item_type=ItemType.WEAPON,
            icon_color=icon_color,
            stackable=False,
        )
        self.stats = stats
        self.mag_current: int = -1

    def get_tooltip(self) -> str:
        return f"{self.name}  DMG:{self.stats.damage}  AP:{self.stats.armor_pen}  SE:{int(self.stats.stopping_effect * 100)}%"


def make_carbine() -> WeaponItem:
    return WeaponItem(
        name="Carbine",
        icon_color=(100, 160, 100),
        stats=WeaponStats(
            damage=12,
            fire_rate=0.12,
            bullet_speed=620.0,
            bullet_lifetime=1.8,
            armor_pen=2,
            stopping_effect=0.3,
            auto_fire=True,
            spread=6.0, # ощутимый разброс при автоогне
            pellets=1,
            width=22,
            height=8,
            color=(120, 180, 100),
            bullet_size=5,
            bullet_color=(220, 240, 120),
            ammo_type=AmmoType.CARBINE,
            mag_size=30,
            reload_time=2.0,
            recoil_distance=8.0, # лёгкая отдача, быстрый возврат
            recoil_recovery=14.0,
        ),
    )


def make_shotgun() -> WeaponItem:
    return WeaponItem(
        name="Shotgun",
        icon_color=(180, 120, 60),
        stats=WeaponStats(
            damage=18,
            fire_rate=0.75,
            bullet_speed=480.0,
            bullet_lifetime=0.5,
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
            recoil_distance=18.0,  # сильный толчок
            recoil_recovery=8.0,   # медленнее возвращается
        ),
    )


def make_sniper() -> WeaponItem:
    return WeaponItem(
        name="Sniper Rifle",
        icon_color=(80, 120, 200),
        stats=WeaponStats(
            damage=85,
            fire_rate=1.4,
            bullet_speed=1100.0,
            bullet_lifetime=2.5,
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
            recoil_distance=24.0,  # резкий сильный откат
            recoil_recovery=6.0,
        ),
    )
