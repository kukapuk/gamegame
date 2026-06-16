import pygame
from dataclasses import dataclass, field
from core.settings import Settings


@dataclass
class InputResult:
    """
    Команды, которые InputHandler возвращает в Game за один кадр.
    Game читает флаги и реагирует — InputHandler сам ничего не вызывает.
    """
    quit:           bool = False
    restart:        bool = False
    toggle_debug:   bool = False
    toggle_flashlight: bool = False
    switch_weapon:  int  = -1          # 0 / 1, или -1 = нет переключения
    dash:           bool = False
    reload:         bool = False
    interact:       bool = False       # E
    drop_weapon:    bool = False       # G
    toggle_pouch:   bool = False       # TAB
    save:           bool = False       # F5
    load:           bool = False       # F9
    use_pouch_slot: int  = -1          # индекс слота Z/X/C/V, или -1
    dialog_key:     int  = -1          # pygame.K_*, или -1 если нет диалога

    # mouse — заполняются независимо от режима
    lmb_down: bool = False
    lmb_up:   bool = False
    rmb_down: bool = False
    mouse_motion: bool = False

    # hold-прогресс рюкзака (0.0 → 1.0)
    i_hold_progress: float = 0.0

    # actions
    unjam: bool = False
    use_item: bool = False
    hud_key: int = -1    # любая клавиша при открытом рюкзаке (для grid_ui Ctrl-поворота)
    scroll_zoom: int = 0  # +1 приблизить, -1 отдалить, 0 без изменений


class InputHandler:
    """
    Читает pygame-события и pressed-состояние клавиш.
    Возвращает InputResult — набор команд за кадр.
    Ничего не знает об игровых объектах: ни о player, ни о hud, ни об уровнях.
    """

    def __init__(self, settings: Settings) -> None:
        self.s = settings
        self._i_held_time: float = 0.0
        self._i_triggered: bool  = False

    def process(
        self,
        dt: float,
        *,
        player_dead: bool,
        dialog_active: bool,
        hud_open: bool,
    ) -> InputResult:
        result = InputResult()

        self._update_i_hold(dt, dialog_active, result)

        if player_dead:
            self._process_dead(result)
        else:
            self._process_alive(result, dialog_active, hud_open)

        return result

    # Hold-таймер рюкзака

    def _update_i_hold(
        self, dt: float, dialog_active: bool, result: InputResult,
    ) -> None:
        if dialog_active:
            self._i_held_time = 0.0
            self._i_triggered = False
            return

        keys = pygame.key.get_pressed()
        if keys[pygame.K_i]:
            self._i_held_time += dt
            if (self._i_held_time >= self.s.backpack_hold_time
                    and not self._i_triggered):
                self._i_triggered = True
                result.toggle_backpack = True   # Game сам разберётся open/close
        else:
            self._i_held_time = 0.0
            self._i_triggered = False

        result.i_hold_progress = min(
            self._i_held_time / self.s.backpack_hold_time, 1.0
        )

    # Dead-screen: любая клавиша / клик → рестарт

    def _process_dead(self, result: InputResult) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                result.quit = True
            elif event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                result.restart = True

    # Normal play

    def _process_alive(
        self, result: InputResult, dialog_active: bool, hud_open: bool,
    ) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                result.quit = True

            elif event.type == pygame.KEYDOWN:
                self._on_keydown(event.key, result, dialog_active, hud_open)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    result.lmb_down = True
                elif event.button == 3:
                    result.rmb_down = True

            elif event.type == pygame.MOUSEWHEEL:
                result.scroll_zoom = 1 if event.y > 0 else -1

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    result.lmb_up = True

            elif event.type == pygame.MOUSEMOTION:
                result.mouse_motion = True

    def _on_keydown(
        self, key: int, result: InputResult,
        dialog_active: bool, hud_open: bool,
    ) -> None:
        # Диалог перехватывает все клавиши
        if dialog_active:
            result.dialog_key = key
            return

        if key == pygame.K_ESCAPE:
            result.quit = True
        elif key == pygame.K_e:
            result.interact = True
        elif key == pygame.K_f:
            result.use_item = True
        elif key == pygame.K_TAB:
            result.toggle_pouch = True
        elif key in self.s.pouch_hotkeys:
            # Z/X/C/V работают всегда, даже при открытом рюкзаке
            for i, hk in enumerate(self.s.pouch_hotkeys):
                if key == hk:
                    result.use_pouch_slot = i
                    break
        elif hud_open:
            result.hud_key = key
        elif key == pygame.K_1:
            result.switch_weapon = 0
        elif key == pygame.K_2:
            result.switch_weapon = 1
        elif key == pygame.K_TAB:
            result.toggle_pouch = True
        elif key == pygame.K_F1:
            result.toggle_debug = True
        elif key == pygame.K_l:
            result.toggle_flashlight = True
        elif key == pygame.K_SPACE:
            result.dash = True
        elif key == pygame.K_r:
            result.reload = True
        elif key == pygame.K_t:
            result.unjam = True
        elif key == pygame.K_f:
            result.use_item = True
        elif key == pygame.K_e:
            result.interact = True
        elif key == pygame.K_g:
            result.drop_weapon = True
        elif key == pygame.K_F5:
            result.save = True
        elif key == pygame.K_F9:
            result.load = True
