from items.item import Item, ItemType

TIER_NAMES             = ["No Armor", "Light", "Medium", "Heavy"]
TIER_COLORS            = [(120, 120, 130), (80, 160, 100), (60, 100, 180), (140, 60, 60)]
DASH_STAMINA_MULT      = [1.0,  1.25, 1.75, 2.5]
SPRINT_SPEED_MULT      = [1.6,  1.45, 1.3,  1.15]
SPRINT_STAMINA_DRAIN   = [15.0, 20.0, 30.0, 45.0]


class Armor(Item):
    """
    Броня. При экипировке вызывает equip(player), при снятии — unequip(player).
    Tier влияет на стоимость dash и параметры бега.
    """

    def __init__(self, tier: int) -> None:
        tier = max(0, min(3, tier))
        super().__init__(
            name=f"{TIER_NAMES[tier]} Armor",
            item_type=ItemType.ARMOR,
            icon_color=TIER_COLORS[tier],
        )
        self.tier = tier
        self.dash_stamina_mult    = DASH_STAMINA_MULT[tier]
        self.sprint_speed_mult    = SPRINT_SPEED_MULT[tier]
        self.sprint_stamina_drain = SPRINT_STAMINA_DRAIN[tier]

    def equip(self, player) -> None:
        from items.stats import Stats
        base = Stats()
        player.stats.dash_stamina_cost    = base.dash_stamina_cost * self.dash_stamina_mult
        player.stats.sprint_multiplier    = self.sprint_speed_mult
        player.stats.sprint_stamina_drain = self.sprint_stamina_drain

    def unequip(self, player) -> None:
        from items.stats import Stats
        base = Stats()
        player.stats.dash_stamina_cost    = base.dash_stamina_cost
        player.stats.sprint_multiplier    = base.sprint_multiplier
        player.stats.sprint_stamina_drain = base.sprint_stamina_drain

    def get_tooltip(self) -> str:
        dash_pct = int(self.dash_stamina_mult * 100)
        return f"{self.name}  dash: {dash_pct}%  sprint drain: {self.sprint_stamina_drain}/s"


def make_light_armor()  -> "Armor": return Armor(tier=1)
def make_medium_armor() -> "Armor": return Armor(tier=2)
def make_heavy_armor()  -> "Armor": return Armor(tier=3)
