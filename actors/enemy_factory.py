"""
enemy_factory.py — фабричные функции для создания врагов.
"""
from actors.enemy import Enemy


def make_grunt(pos, target, armor_class: int = 0, groups: list = ()) -> Enemy:
    return Enemy(pos=pos, target=target, armor_class=armor_class, groups=groups)


def make_shooter(
    pos,
    target,
    armor_class:    int  = 0,
    groups:         list = (),
    bullet_group         = None,
    all_sprites          = None,
    helmet_class:   int  = 0,
    bullet_armor_pen: int = 0,
) -> Enemy:
    e = Enemy(pos=pos, target=target, armor_class=armor_class, groups=groups)
    e.image.fill((180, 80, 220))
    e.helmet_class  = helmet_class
    e.stats.max_hp  = 40
    e.hp            = 40
    e.max_hp        = 40
    e.speed         = 90.0

    e.can_shoot         = True
    e._shoot_rate       = 1.2
    e._shoot_cooldown   = 1.2
    e._preferred_dist   = 220.0
    e._bullet_speed     = 380.0
    e._bullet_damage    = 15
    e._bullet_armor_pen = bullet_armor_pen
    e._bullet_color     = (220, 100, 255)
    e._bullet_group     = bullet_group
    e._all_sprites      = all_sprites
    e._ai_update        = e._ai_shooter

    e._weapon_w     = 22
    e._weapon_h     = 7
    e._weapon_color = (180, 100, 220)

    return e
