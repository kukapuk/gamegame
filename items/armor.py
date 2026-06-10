from items.item import Item, ItemType


class ArmorItem(Item):
    """
    Броня как предмет инвентаря.
    Экипируется в armor-слот подсумка.
    armor_class: 0=нет, 1=лёгкая, 2=средняя, 3=тяжёлая.
    """

    NAMES = {0: "No Armor", 1: "Light Armor", 2: "Medium Armor", 3: "Heavy Armor"}
    COLORS = {0: (80, 80, 80), 1: (100, 160, 100), 2: (60, 120, 180), 3: (140, 80, 60)}

    def __init__(self, armor_class: int) -> None:
        super().__init__(
            name=self.NAMES[armor_class],
            item_type=ItemType.ARMOR,
            icon_color=self.COLORS[armor_class],
            stackable=False,
        )
        self.armor_class = armor_class

    def get_tooltip(self) -> str:
        return f"{self.name}  Class {self.armor_class}"


def make_light_armor()  -> ArmorItem: return ArmorItem(1)
def make_medium_armor() -> ArmorItem: return ArmorItem(2)
def make_heavy_armor()  -> ArmorItem: return ArmorItem(3)
