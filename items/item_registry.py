from items.consumable import make_medkit, make_bandage, make_surgical_kit
from items.armor import make_light_armor, make_medium_armor, make_heavy_armor, Armor
from items.ammo import make_ammo, AmmoType
from items.cleaning_kit import make_cleaning_kit


REGISTRY: dict = {
    "medkit_30":       lambda: make_medkit(30),
    "medkit_50":       lambda: make_medkit(50),
    "bandage":         lambda: make_bandage(),
    "surgical_kit":    lambda: make_surgical_kit(),
    "armor_0":         lambda: Armor(tier=0),
    "armor_1":         lambda: make_light_armor(),
    "armor_2":         lambda: make_medium_armor(),
    "armor_3":         lambda: make_heavy_armor(),
    "ammo_carbine":    lambda count=1: make_ammo(AmmoType.CARBINE, count),
    "ammo_shotgun":    lambda count=1: make_ammo(AmmoType.SHOTGUN, count),
    "ammo_sniper":     lambda count=1: make_ammo(AmmoType.SNIPER,  count),
    "cleaning_kit":    lambda: make_cleaning_kit(0.5),
}

WEAPON_REGISTRY: dict = {}


def register_weapons() -> None:
    from items.weapon_item import make_carbine, make_shotgun, make_sniper
    WEAPON_REGISTRY["carbine"] = make_carbine
    WEAPON_REGISTRY["shotgun"] = make_shotgun
    WEAPON_REGISTRY["sniper"]  = make_sniper


def serialize_item(item) -> dict | None:
    if item is None:
        return None
    from items.consumable import Consumable
    from items.armor import Armor
    from items.ammo import AmmoItem
    from items.weapon_item import WeaponItem

    if isinstance(item, Consumable):
        from items.consumable import TimedConsumable
        if isinstance(item, TimedConsumable):
            return {"type": "bandage"}
        name = item.name.lower().replace(" ", "_")
        if name == "surgical_kit":
            return {"type": "surgical_kit"}
        return {"type": "medkit", "heal": 30}
    from items.cleaning_kit import CleaningKit
    if isinstance(item, CleaningKit):
        return {"type": "cleaning_kit", "heal": item.heal_amount}
    if isinstance(item, Armor):
        return {"type": "armor", "tier": item.tier}
    if isinstance(item, AmmoItem):
        return {"type": "ammo", "ammo_type": item.ammo_type.name, "count": item.stack_count}
    if isinstance(item, WeaponItem):
        return {"type": "weapon", "name": item.name.lower().replace(" ", "_"), "mag_current": item.mag_current}
    return None


def deserialize_item(data: dict):
    if data is None:
        return None
    t = data.get("type")
    if t == "medkit":
        return make_medkit(data.get("heal", 30))
    if t == "bandage":
        return make_bandage()
    if t == "surgical_kit":
        return make_surgical_kit()
    if t == "cleaning_kit":
        return make_cleaning_kit(data.get("heal", 0.5))
    if t == "armor":
        return Armor(tier=data.get("tier", 0))
    if t == "ammo":
        ammo_type = AmmoType[data["ammo_type"]]
        return make_ammo(ammo_type, data.get("count", 1))
    if t == "weapon":
        register_weapons()
        name = data.get("name", "")
        factory = WEAPON_REGISTRY.get(name)
        if factory:
            item = factory()
            item.mag_current = data.get("mag_current", -1)
            return item
    return None
