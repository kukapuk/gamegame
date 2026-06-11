from __future__ import annotations
from typing import Optional, Callable
from items.item import Item, ItemType


class Slot:
    """Одна ячейка инвентаря. Может быть пустой или содержать Item."""

    def __init__(
        self,
        allowed_type: Optional[ItemType] = None,
        on_put: Optional[Callable] = None,
        on_take: Optional[Callable] = None,
    ) -> None:
        self.item: Optional[Item] = None
        self.allowed_type = allowed_type
        self._on_put  = on_put
        self._on_take = on_take

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
        if self._on_put:
            self._on_put(item)
        return True

    def take(self) -> Optional[Item]:
        item = self.item
        self.item = None
        if item and self._on_take:
            self._on_take(item)
        return item


class Inventory:
    """
    Универсальный контейнер предметов.
    owner — актор, которому принадлежит инвентарь (нужен для equip/unequip эффектов).
    """

    def __init__(
        self,
        capacity: int,
        typed_slots: list[ItemType] = None,
        owner=None,
    ) -> None:
        self.owner = owner
        self.slots: list[Slot] = [Slot() for _ in range(capacity)]
        self.typed_slots: list[Slot] = []
        if typed_slots:
            for t in typed_slots:
                self.typed_slots.append(Slot(
                    allowed_type=t,
                    on_put =self._on_equip,
                    on_take=self._on_unequip,
                ))

    def _on_equip(self, item: Item) -> None:
        if self.owner and hasattr(item, "equip"):
            item.equip(self.owner)

    def _on_unequip(self, item: Item) -> None:
        if self.owner and hasattr(item, "unequip"):
            item.unequip(self.owner)

    def all_slots(self) -> list[Slot]:
        return self.typed_slots + self.slots

    def add(self, item: Item) -> bool:
        for slot in self.all_slots():
            if slot.empty and slot.accepts(item):
                return slot.put(item)
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
        item_a = a.take()
        item_b = b.take()
        if item_a:
            b.put(item_a)
        if item_b:
            a.put(item_b)
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
