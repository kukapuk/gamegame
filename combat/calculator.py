import random
from core.settings import Settings


def resolve_hit(
    base_damage: int,
    base_se: float,
    armor_pen: int,
    armor_class: int,
    settings: Settings,
) -> tuple[int, float]:
    """
    Рассчитывает итоговый урон и stopping effect с учётом брони.
    Возвращает (final_damage, final_se).
    """
    gap = armor_class - armor_pen

    if gap <= 0:
        return base_damage, base_se * settings.armor_pen_se_mult

    if gap == 1:
        if random.random() < settings.armor_partial_chance:
            return base_damage, base_se * settings.armor_pen_se_mult
        else:
            return int(base_damage * settings.armor_damage_gap1), base_se

    if gap == 2:
        return int(base_damage * settings.armor_damage_gap2), base_se

    return int(base_damage * settings.armor_damage_gap3), base_se
