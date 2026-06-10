from dataclasses import dataclass


@dataclass
class Stats:
    """
    Характеристики актора. Меняются при смене снаряжения (броня, артефакты).
    Хранится на каждом Actor. Броня создаёт новый экземпляр с другими значениями.
    """

    max_hp: int = 100
    speed: float = 250.0
    armor_class: int = 0

    dash_distance: float = 180.0
    dash_duration: float = 0.12
    dash_cooldown: float = 0.8
    max_stamina: float = 100.0
    stamina_regen: float = 20.0
    dash_stamina_cost: float = 25.0
