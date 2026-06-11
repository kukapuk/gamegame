from items.item import Item, ItemType

TIER_NAMES        = ["No Armor", "Light", "Medium", "Heavy"]
TIER_COLORS       = [(120, 120, 130), (80, 160, 100), (60, 100, 180), (140, 60, 60)]
STAMINA_MULTIPLIERS = [1.0, 1.25, 1.75, 2.5]


class Armor(Item):
    """
    Броня. При экипировке в typed слот вызывает equip(player),
    при снятии — unequip(player). Tier определяет штраф к выносливости рывка.
    """

    def __init__(self, tier: int) -> None:
        tier = max(0, min(3, tier))
        super().__init__(
            name=f"{TIER_NAMES[tier]} Armor",
            item_type=ItemType.ARMOR,
            icon_color=TIER_COLORS[tier],
        )
        self.tier = tier
        self.stamina_multiplier = STAMINA_MULTIPLIERS[tier]

    def equip(self, player) -> None:
        from items.stats import Stats
        base_cost = Stats().dash_stamina_cost
        player.stats.dash_stamina_cost = base_cost * self.stamina_multiplier

    def unequip(self, player) -> None:
        from items.stats import Stats
        player.stats.dash_stamina_cost = Stats().dash_stamina_cost

    def get_tooltip(self) -> str:
        pct = int(self.stamina_multiplier * 100)
        return f"{self.name}  dash cost: {pct}%"

def make_light_armor()  -> Armor: return Armor(tier=1)
def make_medium_armor() -> Armor: return Armor(tier=2)
def make_heavy_armor()  -> Armor: return Armor(tier=3)
