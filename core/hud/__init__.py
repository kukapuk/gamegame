# Реэкспорт для обратной совместимости — весь код использует `from core.hud import HUD`
from core.hud.hud import HUD
from core.hud.constants import DragState

__all__ = ["HUD", "DragState"]
