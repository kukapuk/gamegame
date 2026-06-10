from __future__ import annotations
from typing import Optional
from items.item import Item, ItemType


class Slot:
    """Одна ячейка инвентаря. Может быть пустой или содержать Item."""

    def __init__(self, allowed_type: Optional[ItemType] = None) -> None:
        self.item: Optional[Item] = None
        self.allowed_type = allowed_type

    @property
    def empty(self) -> bool:
        return self.item is None

    def accepts(self, item: Item) -> bool:
        if self.allowed_type is not None:
            return item.item_type == self.allowed_type
        return True

    def put(self, item: Item) -> bool:
        if not self.empty:
            return False
        if not self.accepts(item):
            return False
        self.item = item
        return True

    def take(self) -> Optional[Item]:
        item = self.item
        self.item = None
        return item


class Inventory:
    """
    Универсальный контейнер предметов.
    Поддерживает обычные слоты и фиксированные слоты с типом (оружие, броня).
    """

    def __init__(self, capacity: int, typed_slots: list[ItemType] = None) -> None:
        self.slots: list[Slot] = [Slot() for _ in range(capacity)]
        self.typed_slots: list[Slot] = []
        if typed_slots:
            self.typed_slots = [Slot(allowed_type=t) for t in typed_slots]

    def all_slots(self) -> list[Slot]:
        return self.typed_slots + self.slots

    def add(self, item: Item) -> bool:
        for slot in self.all_slots():
            if slot.empty and slot.accepts(item):
                slot.item = item
                return True
        return False

    def remove(self, item: Item) -> bool:
        for slot in self.all_slots():
            if slot.item is item:
                slot.take()
                return True
        return False

    def get_slot(self, index: int) -> Optional[Slot]:
        all_s = self.all_slots()
        if 0 <= index < len(all_s):
            return all_s[index]
        return None

    def swap(self, index_a: int, index_b: int) -> bool:
        a = self.get_slot(index_a)
        b = self.get_slot(index_b)
        if a is None or b is None:
            return False
        if a.item and not b.accepts(a.item):
            return False
        if b.item and not a.accepts(b.item):
            return False
        a.item, b.item = b.item, a.item
        return True

    def transfer(self, item: Item, target: Inventory) -> bool:
        if not self.remove(item):
            return False
        if not target.add(item):
            self.add(item)
            return False
        return True

    def use_slot(self, index: int, target) -> bool:
        slot = self.get_slot(index)
        if slot is None or slot.empty:
            return False
        item = slot.item
        if hasattr(item, "use"):
            used = item.use(target)
            if used:
                slot.take()
            return used
        return False
