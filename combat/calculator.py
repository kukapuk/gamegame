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
    penetrated:      bool   # True если броня пробита (нужно для кровотечения)


def randomize_zone(hit_head_hitbox: bool) -> HitZone:
    """
    hit_head_hitbox=True  -- пуля задела head_rect:
        75% HEAD, 25% TORSO

    hit_head_hitbox=False -- пуля задела body_rect:
        5% HEAD, 55% TORSO, 20% ARMS, 20% LEGS
    """
    r = random.random()
    if hit_head_hitbox:
        return HitZone.HEAD if r < 0.75 else HitZone.TORSO
    else:
        if r < 0.60: return HitZone.TORSO
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
    """
    Рассчитывает зону, урон и пробитие брони.

    hit_head_hitbox -- попала ли пуля в head_rect актора.
    """
    zone      = randomize_zone(hit_head_hitbox)
    gap       = armor_class - armor_pen
    penetrated = False

    if gap <= 0:
        final_damage = base_damage
        final_se     = base_se * settings.armor_pen_se_mult
        penetrated   = True
    elif gap == 1:
        if random.random() < settings.armor_partial_chance:
            final_damage = base_damage
            final_se     = base_se * settings.armor_pen_se_mult
            penetrated   = True
        else:
            final_damage = int(base_damage * settings.armor_damage_gap1)
            final_se     = base_se
    elif gap == 2:
        final_damage = int(base_damage * settings.armor_damage_gap2)
        final_se     = base_se
    else:
        final_damage = int(base_damage * settings.armor_damage_gap3)
        final_se     = base_se

    # голова -- урон x2.5
    if zone == HitZone.HEAD:
        final_damage = int(final_damage * 2.5)

    return HitResult(
        damage          = final_damage,
        stopping_effect = final_se,
        zone            = zone,
        penetrated      = penetrated,
    )
