import json
import os
from items.item_registry import serialize_item, deserialize_item


SAVE_DIR  = "saves"
SAVE_FILE = os.path.join(SAVE_DIR, "save_0.json")


class SaveManager:
    """
    Сохраняет и загружает состояние игры в JSON.
    F5 — сохранить, F9 — загрузить.

    При загрузке: уровень перезагружается через game._load_level(),
    враги респавнятся из tmx, затем восстанавливается HP и state.
    """

    def save(self, game) -> bool:
        os.makedirs(SAVE_DIR, exist_ok=True)
        try:
            data = self._serialize(game)
            with open(SAVE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"[save] saved to {SAVE_FILE}")
            return True
        except Exception as e:
            print(f"[save] error: {e}")
            return False

    def load(self, game) -> bool:
        if not os.path.exists(SAVE_FILE):
            print("[save] no save file found")
            return False
        try:
            with open(SAVE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._deserialize(game, data)
            print(f"[save] loaded from {SAVE_FILE}")
            return True
        except Exception as e:
            print(f"[save] error: {e}")
            return False

    def has_save(self) -> bool:
        return os.path.exists(SAVE_FILE)

    # Serialize

    def _serialize(self, game) -> dict:
        p = game.player
        return {
            "level":      game.world.level.path,
            "player": {
                "pos":               [p.pos.x, p.pos.y],
                "hp":                p.hp,
                "stamina":           p.stamina,
                "active_weapon_slot": p.active_weapon_slot,
            },
            "pouch":       self._serialize_inventory(p.pouch),
            "backpack":    self._serialize_inventory(p.backpack),
            "enemies":     self._serialize_enemies(game),
            "world_items": self._serialize_world_items(game),
        }

    def _serialize_inventory(self, inventory) -> list:
        result = []
        for slot in inventory.all_slots():
            result.append({
                "allowed_type": slot.allowed_type.name if slot.allowed_type else None,
                "item":         serialize_item(slot.item),
            })
        return result

    def _serialize_enemies(self, game) -> list:
        result = []
        for enemy in game.enemies:
            result.append({
                "pos":         [enemy.pos.x, enemy.pos.y],
                "hp":          enemy.hp,
                "armor_class": enemy.armor_class,
                "state":       enemy.state,
                "type":        "shooter" if enemy.can_shoot else "grunt",
            })
        return result

    def _serialize_world_items(self, game) -> list:
        result = []
        for wi in game.world_items:
            data = serialize_item(wi.item)
            if data:
                result.append({
                    "pos":  [wi.world_pos.x, wi.world_pos.y],
                    "item": data,
                })
        return result

    # Deserialize

    def _deserialize(self, game, data: dict) -> None:
        level_path = data.get("level", "levels/level_1.tmx")

        game.player_dead = False
        game.player      = None

        game._load_level(level_path, keep_player=False)

        pd = data["player"]
        game.player.pos.update(pd["pos"][0], pd["pos"][1])
        game.player.rect.center = (round(pd["pos"][0]), round(pd["pos"][1]))
        game.player.hp                 = pd.get("hp", game.player.max_hp)
        game.player.stamina            = pd.get("stamina", game.player.stats.max_stamina)
        game.player.active_weapon_slot = pd.get("active_weapon_slot", 0)

        self._deserialize_inventory(game.player.pouch,    data.get("pouch", []))
        self._deserialize_inventory(game.player.backpack, data.get("backpack", []))

        self._restore_enemies(game, data.get("enemies", []))
        self._restore_world_items(game, data.get("world_items", []))

        game._sync_weapon()

    def _deserialize_inventory(self, inventory, slots_data: list) -> None:
        all_slots = inventory.all_slots()
        for i, slot_data in enumerate(slots_data):
            if i >= len(all_slots):
                break
            item_data = slot_data.get("item")
            if item_data:
                item = deserialize_item(item_data)
                if item:
                    all_slots[i].put(item)

    def _restore_enemies(self, game, enemies_data: list) -> None:
        """
        Враги уже заспавнены из tmx через _load_level.
        Восстанавливаем только HP, позицию и state — без пересоздания.
        Сопоставляем по индексу — порядок спавна детерминирован.
        """
        enemies = list(game.enemies)
        for i, ed in enumerate(enemies_data):
            if i >= len(enemies):
                break
            e = enemies[i]
            e.pos.update(ed["pos"][0], ed["pos"][1])
            e.rect.center = (round(ed["pos"][0]), round(ed["pos"][1]))
            e.hp    = ed.get("hp", e.max_hp)
            e.state = ed.get("state", e.state)

    def _restore_world_items(self, game, items_data: list) -> None:
        game.world_items.empty()
        from items.world_item import WorldItem
        for wd in items_data:
            item = deserialize_item(wd.get("item"))
            if item:
                WorldItem(item=item, pos=tuple(wd["pos"]), groups=[game.world_items])
