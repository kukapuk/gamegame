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
        from items.consumable import TimedConsumable
        if isinstance(item, TimedConsumable):
            return target.start_timed_use(item, slot)
        if hasattr(item, "use"):
            used = item.use(target)
            if used:
                slot.take()
            return used
        return False


# ---------------------------------------------------------------------------
# GridInventory — рюкзак в стиле RE4 / Tarkov
# ---------------------------------------------------------------------------

class GridPlacement:
    """Хранит позицию предмета в сетке."""
    __slots__ = ("item", "col", "row")

    def __init__(self, item: Item, col: int, row: int) -> None:
        self.item = item
        self.col  = col
        self.row  = row


class GridInventory:
    """
    Рюкзак на основе 2D-сетки.

    Каждый предмет занимает item.effective_size ячеек.
    Поворот меняет item.grid_rotated — cols и rows меняются местами.
    Если при дропе предмет не влезает — возвращает False, вызывающий
    код должен дропнуть предмет на пол.

    Координаты: col — столбец (x), row — строка (y), оба от 0.
    """

    def __init__(self, cols: int, rows: int) -> None:
        self.cols = cols
        self.rows = rows
        # список активных размещений
        self._placements: list[GridPlacement] = []

    # ------------------------------------------------------------------
    # Публичный API
    # ------------------------------------------------------------------

    def place(self, item: Item, col: int, row: int) -> bool:
        """Разместить предмет в клетке (col, row). False если не влезает."""
        if not self._can_place(item, col, row):
            return False
        self._placements.append(GridPlacement(item, col, row))
        return True

    def remove(self, item: Item) -> bool:
        """Убрать предмет из сетки. False если не найден."""
        for p in self._placements:
            if p.item is item:
                self._placements.remove(p)
                return True
        return False

    def move(self, item: Item, new_col: int, new_row: int) -> bool:
        """
        Переместить уже лежащий предмет в новую позицию.
        Временно убирает его из сетки, чтобы своё старое место не мешало.
        """
        placement = self._find(item)
        if placement is None:
            return False
        self._placements.remove(placement)
        if self._can_place(item, new_col, new_row):
            self._placements.append(GridPlacement(item, new_col, new_row))
            return True
        # не влезло — возвращаем на старое место
        self._placements.append(placement)
        return False

    def rotate(self, item: Item) -> bool:
        """
        Повернуть предмет на 90°.
        Если после поворота он не влезает на текущей позиции — откатываем.
        Возвращает True если поворот применился.
        """
        placement = self._find(item)
        if placement is None:
            return False
        item.grid_rotated = not item.grid_rotated
        if not self._can_place(item, placement.col, placement.row, skip=item):
            # не влезло — откатываем поворот
            item.grid_rotated = not item.grid_rotated
            return False
        return True

    def rotate_free(self, item: Item) -> None:
        """Повернуть предмет который ещё не лежит в сетке (во время drag)."""
        item.grid_rotated = not item.grid_rotated

    def add(self, item: Item) -> bool:
        """Найти первое свободное место и положить. False если нет места."""
        for row in range(self.rows):
            for col in range(self.cols):
                if self._can_place(item, col, row):
                    self._placements.append(GridPlacement(item, col, row))
                    return True
        return False

    def item_at(self, col: int, row: int) -> Optional[Item]:
        """Предмет, занимающий ячейку (col, row), или None."""
        for p in self._placements:
            c, r = p.item.effective_size
            if p.col <= col < p.col + c and p.row <= row < p.row + r:
                return p.item
        return None

    def placement_of(self, item: Item) -> Optional[GridPlacement]:
        return self._find(item)

    def all_items(self) -> list[Item]:
        return [p.item for p in self._placements]

    def is_empty(self) -> bool:
        return len(self._placements) == 0

    def can_place(self, item: Item, col: int, row: int) -> bool:
        """Публичная проверка без исключения текущего предмета."""
        return self._can_place(item, col, row)

    # ------------------------------------------------------------------
    # Сериализация (для save_manager)
    # ------------------------------------------------------------------

    def serialize(self) -> list[dict]:
        from items.item_registry import serialize_item
        result = []
        for p in self._placements:
            data = serialize_item(p.item)
            if data:
                data["grid_col"]     = p.col
                data["grid_row"]     = p.row
                data["grid_rotated"] = p.item.grid_rotated
                result.append(data)
        return result

    def deserialize(self, slots_data: list[dict]) -> None:
        from items.item_registry import deserialize_item
        self._placements.clear()
        for d in slots_data:
            item = deserialize_item(d)
            if item is None:
                continue
            item.grid_rotated = d.get("grid_rotated", False)
            col = d.get("grid_col", 0)
            row = d.get("grid_row", 0)
            # кладём напрямую — при загрузке доверяем сохранённым координатам
            self._placements.append(GridPlacement(item, col, row))

    # ------------------------------------------------------------------
    # Внутренние методы
    # ------------------------------------------------------------------

    def _find(self, item: Item) -> Optional[GridPlacement]:
        for p in self._placements:
            if p.item is item:
                return p
        return None

    def _can_place(self, item: Item, col: int, row: int,
                   skip: Optional[Item] = None) -> bool:
        """
        Проверяет, влезает ли предмет начиная с (col, row).
        skip — предмет который временно игнорируется (используется в move/rotate).
        """
        w, h = item.effective_size
        # выход за границы сетки
        if col < 0 or row < 0 or col + w > self.cols or row + h > self.rows:
            return False
        # пересечение с другими предметами
        for p in self._placements:
            if p.item is item or p.item is skip:
                continue
            pw, ph = p.item.effective_size
            # AABB пересечение
            if (col < p.col + pw and col + w > p.col and
                    row < p.row + ph and row + h > p.row):
                return False
        return True
