from items.item import Item, ItemType


class Consumable(Item):
    """
    Мгновенный расходник: аптечка, стимулятор.
    use() вызывается при нажатии хоткея подсумка.
    Возвращает True если предмет использован и должен быть удалён из слота.
    """

    def __init__(self, name: str, icon_color: tuple, effect_fn,
                 tooltip: str = "", stackable: bool = False,
                 max_stack: int = 1, grid_size: tuple = (1, 1)) -> None:
        super().__init__(
            name=name,
            item_type=ItemType.CONSUMABLE,
            icon_color=icon_color,
            stackable=stackable,
            max_stack=max_stack,
            grid_size=grid_size,
        )
        self._effect_fn = effect_fn
        self._tooltip   = tooltip

    def use(self, target) -> bool:
        self._effect_fn(target)
        return True

    def get_tooltip(self) -> str:
        return self._tooltip or self.name


class TimedConsumable(Item):
    """
    Расходник с анимацией применения.
    Не применяется мгновенно — возвращает use_time.
    Player держит таймер, вызывает apply() по истечении.
    """

    def __init__(self, name: str, icon_color: tuple, effect_fn,
                 use_time: float = 1.0, tooltip: str = "",
                 stackable: bool = False, max_stack: int = 1,
                 grid_size: tuple = (1, 1)) -> None:
        super().__init__(
            name=name,
            item_type=ItemType.CONSUMABLE,
            icon_color=icon_color,
            stackable=stackable,
            max_stack=max_stack,
            grid_size=grid_size,
        )
        self._effect_fn = effect_fn
        self._tooltip   = tooltip
        self.use_time   = use_time

    def apply(self, target) -> None:
        self._effect_fn(target)

    def get_tooltip(self) -> str:
        return self._tooltip or self.name


def make_bandage() -> TimedConsumable:
    return TimedConsumable(
        name="Bandage",
        icon_color=(220, 200, 180),
        effect_fn=lambda t: t.stop_bleeding(),
        use_time=0.8,
        tooltip="Bandage  stops bleeding",
        stackable=True,
        max_stack=3,
        grid_size=(1, 1),
    )


def make_surgical_kit() -> Consumable:
    return TimedConsumable(
        name="Surgical Kit",
        icon_color=(100, 180, 220),
        effect_fn=lambda t: t.heal_limbs(),
        use_time=2.0,
        tooltip="Surgical Kit  heals limbs",
        grid_size=(2, 1),
    )


def make_medkit(heal_amount: int = 30) -> TimedConsumable:
    return TimedConsumable(
        name="Medkit",
        icon_color=(60, 200, 90),
        effect_fn=lambda t: setattr(t, "hp", min(t.max_hp, t.hp + heal_amount)),
        use_time=0.5,
        tooltip=f"Medkit  +{heal_amount} HP",
        grid_size=(1, 2),
    )
