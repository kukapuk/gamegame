"""
faction_manager.py — система фракций и матрица отношений.

Фракции:
  PLAYER    — игрок
  MERCENARY — наёмники (фракция игрока)
  BANDIT    — бандиты
  MILITARY  — военные
  ELITE     — спецназ (союзник военных)
  CIVILIAN  — мирные жители
  NEUTRAL   — торговцы, нейтралы

Отношения:
  FRIENDLY — не атакуют друг друга
  NEUTRAL  — игнорируют если не спровоцированы
  HOSTILE  — атакуют при виде
"""
from enum import IntEnum, auto


class Faction(IntEnum):
    PLAYER    = 0
    MERCENARY = 1
    BANDIT    = 2
    MILITARY  = 3
    ELITE     = 4
    CIVILIAN  = 5
    NEUTRAL   = 6


class Relation(IntEnum):
    FRIENDLY = 0
    NEUTRAL  = 1
    HOSTILE  = 2


# Статичная матрица — (a, b) → Relation
# Симметрична: (A,B) == (B,A)
_MATRIX: dict[tuple, Relation] = {
    # Игрок
    (Faction.PLAYER,    Faction.PLAYER):    Relation.FRIENDLY,
    (Faction.PLAYER,    Faction.MERCENARY): Relation.FRIENDLY,
    (Faction.PLAYER,    Faction.BANDIT):    Relation.HOSTILE,
    (Faction.PLAYER,    Faction.MILITARY):  Relation.HOSTILE,
    (Faction.PLAYER,    Faction.ELITE):     Relation.HOSTILE,
    (Faction.PLAYER,    Faction.CIVILIAN):  Relation.NEUTRAL,
    (Faction.PLAYER,    Faction.NEUTRAL):   Relation.NEUTRAL,

    # Наёмники
    (Faction.MERCENARY, Faction.MERCENARY): Relation.FRIENDLY,
    (Faction.MERCENARY, Faction.BANDIT):    Relation.HOSTILE,
    (Faction.MERCENARY, Faction.MILITARY):  Relation.HOSTILE,
    (Faction.MERCENARY, Faction.ELITE):     Relation.HOSTILE,
    (Faction.MERCENARY, Faction.CIVILIAN):  Relation.NEUTRAL,
    (Faction.MERCENARY, Faction.NEUTRAL):   Relation.NEUTRAL,

    # Бандиты
    (Faction.BANDIT,    Faction.BANDIT):    Relation.FRIENDLY,
    (Faction.BANDIT,    Faction.MILITARY):  Relation.HOSTILE,
    (Faction.BANDIT,    Faction.ELITE):     Relation.HOSTILE,
    (Faction.BANDIT,    Faction.CIVILIAN):  Relation.HOSTILE,
    (Faction.BANDIT,    Faction.NEUTRAL):   Relation.HOSTILE,

    # Военные
    (Faction.MILITARY,  Faction.MILITARY):  Relation.FRIENDLY,
    (Faction.MILITARY,  Faction.ELITE):     Relation.FRIENDLY,
    (Faction.MILITARY,  Faction.CIVILIAN):  Relation.NEUTRAL,
    (Faction.MILITARY,  Faction.NEUTRAL):   Relation.NEUTRAL,

    # Элита
    (Faction.ELITE,     Faction.ELITE):     Relation.FRIENDLY,
    (Faction.ELITE,     Faction.CIVILIAN):  Relation.NEUTRAL,
    (Faction.ELITE,     Faction.NEUTRAL):   Relation.NEUTRAL,

    # Мирные и нейтралы
    (Faction.CIVILIAN,  Faction.CIVILIAN):  Relation.FRIENDLY,
    (Faction.CIVILIAN,  Faction.NEUTRAL):   Relation.FRIENDLY,
    (Faction.NEUTRAL,   Faction.NEUTRAL):   Relation.FRIENDLY,
}


class FactionManager:
    """
    Синглтон-менеджер отношений между фракциями.
    Хранит локальные провокации (атаковали конкретную группу → только она hostile).
    """

    def __init__(self) -> None:
        # set of (actor_id, target_faction) — провокации
        self._provoked: set[tuple[int, Faction]] = set()

    def get_relation(self, a_faction: Faction, b_faction: Faction,
                     a_id: int = -1) -> Relation:
        """
        Возвращает отношение фракции a к фракции b.
        a_id — id конкретного актора для проверки локальной провокации.
        """
        base = self._base_relation(a_faction, b_faction)
        # провокация: если b_faction спровоцировала этого конкретного актора
        if a_id >= 0 and (a_id, b_faction) in self._provoked:
            return Relation.HOSTILE
        return base

    def is_hostile(self, a_faction: Faction, b_faction: Faction,
                   a_id: int = -1) -> bool:
        return self.get_relation(a_faction, b_faction, a_id) == Relation.HOSTILE

    def is_friendly(self, a_faction: Faction, b_faction: Faction) -> bool:
        return self._base_relation(a_faction, b_faction) == Relation.FRIENDLY

    def provoke(self, actor_id: int, aggressor_faction: Faction) -> None:
        """Актор actor_id теперь враждебен к aggressor_faction (локально)."""
        self._provoked.add((actor_id, aggressor_faction))

    def clear_provocation(self, actor_id: int) -> None:
        self._provoked = {p for p in self._provoked if p[0] != actor_id}

    @staticmethod
    def _base_relation(a: Faction, b: Faction) -> Relation:
        rel = _MATRIX.get((a, b)) or _MATRIX.get((b, a))
        return rel if rel is not None else Relation.NEUTRAL


# Глобальный экземпляр — используется через весь проект
faction_mgr = FactionManager()
