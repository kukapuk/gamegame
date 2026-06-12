from items.item import Item, ItemType


class CleaningKit(Item):
    """
    Набор для чистки оружия.
    Применяется drag & drop на оружие в подсумке или рюкзаке.
    Восстанавливает cleanliness на heal_amount (до 1.0), снимает jam.
    """

    def __init__(self, heal_amount: float = 0.5) -> None:
        super().__init__(
            name="Cleaning Kit",
            item_type=ItemType.CONSUMABLE,
            icon_color=(180, 160, 100),
            stackable=False,
        )
        self.heal_amount = heal_amount

    def apply_to_weapon(self, weapon_item) -> None:
        """Чистит оружие. weapon_item — WeaponItem."""
        weapon_item.cleanliness = min(1.0, weapon_item.cleanliness + self.heal_amount)
        weapon_item.jammed      = False

    def get_tooltip(self) -> str:
        return f"Cleaning Kit  +{int(self.heal_amount * 100)}% clean"


def make_cleaning_kit(heal_amount: float = 0.5) -> CleaningKit:
    return CleaningKit(heal_amount=heal_amount)
