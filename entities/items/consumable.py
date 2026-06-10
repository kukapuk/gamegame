from entities.items.item import Item, ItemType


class Consumable(Item):
    """
    Используемый предмет: аптечка, граната, стимулятор.
    use() вызывается при нажатии хоткея подсумка (Z X C V).
    Возвращает True если предмет использован и должен быть удалён из слота.
    """

    def __init__(self, name: str, icon_color: tuple, effect_fn, tooltip: str = "") -> None:
        super().__init__(
            name=name,
            item_type=ItemType.CONSUMABLE,
            icon_color=icon_color,
            stackable=False,
        )
        self._effect_fn = effect_fn
        self._tooltip = tooltip

    def use(self, target) -> bool:
        self._effect_fn(target)
        return True

    def get_tooltip(self) -> str:
        return self._tooltip or self.name


def make_medkit(heal_amount: int = 30) -> Consumable:
    return Consumable(
        name="Medkit",
        icon_color=(60, 200, 90),
        effect_fn=lambda target: target.__setattr__(
            "hp", min(target.max_hp, target.hp + heal_amount)
        ),
        tooltip=f"Medkit  +{heal_amount} HP",
    )
