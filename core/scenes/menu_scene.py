import pygame
from core.settings import Settings


class MenuScene:
    """
    Главное меню. Две кнопки: Начать игру и Выход.
    Escape — выход из игры.
    update() возвращает:
        "running"    — продолжаем
        "start_game" — запустить игру
        "quit"       — выйти
    """

    BG_COLOR     = (12, 14, 20)
    TITLE_COLOR  = (220, 220, 230)
    BTN_COLOR    = (30, 33, 48)
    BTN_HOVER    = (45, 50, 72)
    BTN_BORDER   = (70, 75, 110)
    BTN_TEXT     = (190, 195, 215)
    BTN_W        = 220
    BTN_H        = 52
    BTN_RADIUS   = 8

    def __init__(self, settings: Settings, screen: pygame.Surface) -> None:
        self.s      = settings
        self.screen = screen

        self._font_title = pygame.font.SysFont("monospace", 48, bold=True)
        self._font_btn   = pygame.font.SysFont("monospace", 18)
        self._font_hint  = pygame.font.SysFont("monospace", 12)

        cx = settings.screen_width  // 2
        cy = settings.screen_height // 2

        self._buttons = [
            {"label": "1. Start Game", "action": "start_game",
             "rect": pygame.Rect(cx - self.BTN_W // 2, cy - 10, self.BTN_W, self.BTN_H)},
            {"label": "2. Exit",       "action": "quit",
             "rect": pygame.Rect(cx - self.BTN_W // 2, cy + 62, self.BTN_W, self.BTN_H)},
        ]
        self._hovered: int = -1

    def update(self, dt: float) -> str:
        mouse_pos = pygame.mouse.get_pos()
        self._hovered = -1
        for i, btn in enumerate(self._buttons):
            if btn["rect"].collidepoint(mouse_pos):
                self._hovered = i

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return "quit"
                for i, btn in enumerate(self._buttons):
                    if event.key == pygame.K_1 + i:
                        return btn["action"]
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for btn in self._buttons:
                    if btn["rect"].collidepoint(event.pos):
                        return btn["action"]

        self._draw()
        return "running"

    def _draw(self) -> None:
        self.screen.fill(self.BG_COLOR)

        cx = self.s.screen_width  // 2
        cy = self.s.screen_height // 2

        # заголовок
        title = self._font_title.render(self.s.title, True, self.TITLE_COLOR)
        self.screen.blit(title, title.get_rect(center=(cx, cy - 100)))

        # кнопки
        for i, btn in enumerate(self._buttons):
            color = self.BTN_HOVER if i == self._hovered else self.BTN_COLOR
            pygame.draw.rect(self.screen, color,           btn["rect"], border_radius=self.BTN_RADIUS)
            pygame.draw.rect(self.screen, self.BTN_BORDER, btn["rect"], 1, border_radius=self.BTN_RADIUS)
            lbl = self._font_btn.render(btn["label"], True, self.BTN_TEXT)
            self.screen.blit(lbl, lbl.get_rect(center=btn["rect"].center))

        pygame.display.flip()
