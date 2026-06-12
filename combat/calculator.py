import random
from dataclasses import dataclass
from enum import Enum, auto
from core.settings import Settings


class HitZone(Enum):
    HEAD  = auto()
    TORSO = auto()
    ARMS  = auto()
    LEGS  = auto()


@dataclass
class HitResult:
    damage:          int
    stopping_effect: float
    zone:            HitZone
    penetrated:      bool


def randomize_zone(hit_head_hitbox: bool) -> HitZone:
    r = random.random()
    if hit_head_hitbox:
        return HitZone.HEAD if r < 0.75 else HitZone.TORSO
    else:
        if r < 0.05:   return HitZone.HEAD
        elif r < 0.60: return HitZone.TORSO
        elif r < 0.80: return HitZone.ARMS
        else:          return HitZone.LEGS


def resolve_hit(
    base_damage: int,
    base_se: float,
    armor_pen: int,
    armor_class: int,
    hit_head_hitbox: bool,
    settings: Settings,
) -> HitResult:
    zone       = randomize_zone(hit_head_hitbox)
    gap        = armor_class - armor_pen
    penetrated = False

    # шанс пробития зависит от gap (armor_class - armor_pen):
    # gap <= 0  → 100%  (пробивает всегда)
    # gap == 1  → 50%
    # gap == 2  → 25%
    # gap >= 3  → 15%
    # равенство (gap == 0 при ap == ac) → 75%
    if armor_pen == armor_class:
        pen_chance = 0.75
    elif gap <= 0:
        pen_chance = 1.0
    elif gap == 1:
        pen_chance = 0.50
    elif gap == 2:
        pen_chance = 0.25
    else:
        pen_chance = 0.15

    if random.random() < pen_chance:
        final_damage = base_damage
        final_se     = base_se * settings.armor_pen_se_mult
        penetrated   = True
    else:
        # не пробил — урон снижается пропорционально gap
        dmg_mult = max(0.1, 1.0 - gap * 0.2)
        final_damage = int(base_damage * dmg_mult)
        final_se     = base_se

    if zone == HitZone.HEAD:
        final_damage = int(final_damage * 2.5)

    return HitResult(
        damage          = final_damage,
        stopping_effect = final_se,
        zone            = zone,
        penetrated      = penetrated,
    )
