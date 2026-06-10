from enum import Enum, auto
from items.item import Item, ItemType


class AmmoType(Enum):
    CARBINE = auto()
    SHOTGUN = auto()
    SNIPER  = auto()


AMMO_NAMES = {
    AmmoType.CARBINE: "5.56 Ammo",
    AmmoType.SHOTGUN: "12ga Shells",
    AmmoType.SNIPER:  ".338 Rounds",
}

AMMO_COLORS = {
    AmmoType.CARBINE: (180, 200, 100),
    AmmoType.SHOTGUN: (200, 150, 80),
    AmmoType.SNIPER:  (120, 160, 220),
}

AMMO_MAX_STACK = {
    AmmoType.CARBINE: 90,
    AmmoType.SHOTGUN: 48,
    AmmoType.SNIPER:  20,
}


class AmmoItem(Item):
    """Патроны. Стакаются, тип привязан к оружию."""

    def __init__(self, ammo_type: AmmoType, count: int = 1) -> None:
        max_s = AMMO_MAX_STACK[ammo_type]
        super().__init__(
            name=AMMO_NAMES[ammo_type],
            item_type=ItemType.AMMO,
            icon_color=AMMO_COLORS[ammo_type],
            stackable=True,
            max_stack=max_s,
        )
        self.ammo_type   = ammo_type
        self.stack_count = min(count, max_s)

    def get_tooltip(self) -> str:
        return f"{self.name}  x{self.stack_count}"


def make_ammo(ammo_type: AmmoType, count: int) -> AmmoItem:
    return AmmoItem(ammo_type=ammo_type, count=count)
