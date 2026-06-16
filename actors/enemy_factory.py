"""
enemy_factory.py — фабричные функции для создания врагов.
"""
from actors.enemy import Enemy
from core.managers.faction_manager import Faction
from combat.enemy_weapon import (
    EnemyWeapon,
    pistol_stats, smg_stats, assault_rifle_stats,
    shotgun_stats, sniper_stats,
)


def _attach_weapon(e: Enemy, stats) -> None:
    """Привязывает EnemyWeapon к врагу — устанавливает callbacks."""
    w = EnemyWeapon(stats)
    w.on_fire  = e._fire_bullet
    w.on_sound = e._sound_callback   # задаётся снаружи из game_scene
    e.enemy_weapon = w


def make_grunt(pos, target, armor_class: int = 0, groups: list = ()) -> Enemy:
    """Грант — ближний бой, без стрельбы."""
    e = Enemy(pos=pos, target=target, armor_class=armor_class, groups=groups)
    e.faction        = Faction.BANDIT
    e.vision_range   = 200.0
    e.reaction_delay = 1.2
    return e


def make_shooter(
    pos,
    target,
    armor_class:     int  = 0,
    groups:          list = (),
    bullet_group          = None,
    all_sprites           = None,
    helmet_class:    int  = 0,
    bullet_armor_pen: int = 0,
) -> Enemy:
    """Shooter с пистолетом (одиночный огонь)."""
    e = Enemy(pos=pos, target=target, armor_class=armor_class, groups=groups)
    e.image.fill((180, 80, 220))
    e.helmet_class  = helmet_class
    e.stats.max_hp  = 40
    e.hp = e.max_hp = 40
    e.speed         = 90.0
    e.can_shoot     = True
    e._preferred_dist = 220.0
    e._bullet_group   = bullet_group
    e._all_sprites    = all_sprites
    e._ai_update      = e._ai_shooter
    e._weapon_w, e._weapon_h = 22, 7
    e._weapon_color = (180, 100, 220)
    e.faction        = Faction.BANDIT
    e.vision_range   = 240.0
    e.reaction_delay = 0.9

    stats = pistol_stats()
    stats.armor_pen = bullet_armor_pen
    _attach_weapon(e, stats)
    return e


def make_smg_shooter(
    pos, target,
    armor_class: int = 0,
    groups: list = (),
    bullet_group=None,
    all_sprites=None,
    helmet_class: int = 0,
) -> Enemy:
    """Враг с ПП — автоматический огонь, много пуль."""
    e = Enemy(pos=pos, target=target, armor_class=armor_class, groups=groups)
    e.image.fill((180, 120, 60))
    e.helmet_class  = helmet_class
    e.hp = e.max_hp = 35
    e.speed         = 100.0
    e.can_shoot     = True
    e._preferred_dist = 180.0
    e._bullet_group   = bullet_group
    e._all_sprites    = all_sprites
    e._ai_update      = e._ai_shooter
    e._weapon_w, e._weapon_h = 20, 6
    e._weapon_color = (180, 120, 60)
    e.faction        = Faction.BANDIT
    e.vision_range   = 260.0
    e.reaction_delay = 0.8
    _attach_weapon(e, smg_stats())
    return e


def make_rifle_shooter(
    pos, target,
    armor_class: int = 1,
    groups: list = (),
    bullet_group=None,
    all_sprites=None,
    helmet_class: int = 1,
) -> Enemy:
    """Военный с автоматом — очередь из 3 пуль."""
    e = Enemy(pos=pos, target=target, armor_class=armor_class, groups=groups)
    e.image.fill((60, 100, 60))
    e.helmet_class  = helmet_class
    e.stats.max_hp  = 55
    e.hp = e.max_hp = 55
    e.speed         = 85.0
    e.can_shoot     = True
    e._preferred_dist = 250.0
    e._bullet_group   = bullet_group
    e._all_sprites    = all_sprites
    e._ai_update      = e._ai_shooter
    e._weapon_w, e._weapon_h = 26, 7
    e._weapon_color = (60, 100, 60)
    e.faction        = Faction.MILITARY
    e.use_cover      = True
    e.vision_range   = 420.0
    e.reaction_delay = 0.35
    _attach_weapon(e, assault_rifle_stats())
    return e


def make_shotgun_shooter(
    pos, target,
    armor_class: int = 0,
    groups: list = (),
    bullet_group=None,
    all_sprites=None,
    helmet_class: int = 0,
) -> Enemy:
    """Бандит с дробовиком — мощный вблизи."""
    e = Enemy(pos=pos, target=target, armor_class=armor_class, groups=groups)
    e.image.fill((150, 80, 40))
    e.helmet_class  = helmet_class
    e.hp = e.max_hp = 45
    e.speed         = 95.0
    e.can_shoot     = True
    e._preferred_dist = 130.0
    e._bullet_group   = bullet_group
    e._all_sprites    = all_sprites
    e._ai_update      = e._ai_shooter
    e._weapon_w, e._weapon_h = 24, 8
    e._weapon_color = (150, 80, 40)
    e.faction        = Faction.BANDIT
    e.vision_range   = 220.0
    e.reaction_delay = 1.0
    _attach_weapon(e, shotgun_stats())
    return e


def make_sniper(
    pos, target,
    armor_class: int = 1,
    groups: list = (),
    bullet_group=None,
    all_sprites=None,
    helmet_class: int = 2,
) -> Enemy:
    """Снайпер — высокий урон, большая дистанция."""
    e = Enemy(pos=pos, target=target, armor_class=armor_class, groups=groups)
    e.image.fill((40, 60, 90))
    e.helmet_class  = helmet_class
    e.stats.max_hp  = 50
    e.hp = e.max_hp = 50
    e.speed         = 70.0
    e.can_shoot     = True
    e._preferred_dist = 400.0
    e.vision_range    = 560.0
    e.reaction_delay  = 0.1
    e._bullet_group   = bullet_group
    e._all_sprites    = all_sprites
    e._ai_update      = e._ai_shooter
    e._weapon_w, e._weapon_h = 32, 6
    e._weapon_color = (40, 60, 90)
    e.faction    = Faction.ELITE
    e.use_cover  = True
    _attach_weapon(e, sniper_stats())
    return e
