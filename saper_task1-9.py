import flet as ft
import random
import time
import asyncio
import json
import os
from typing import List

CELL_SIZE = 36
RECORDS_FILE = "records.json"


def load_records() -> dict:
    if os.path.exists(RECORDS_FILE):
        with open(RECORDS_FILE) as f:
            return json.load(f)
    return {}


def save_records(records: dict):
    with open(RECORDS_FILE, "w") as f:
        json.dump(records, f)


class Cell:
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y
        self.is_mine = False
        self.is_revealed = False
        self.is_flagged = False
        self.is_questioned = False
        self.mines_around = 0

    def reset(self):
        self.is_mine = False
        self.is_revealed = False
        self.is_flagged = False
        self.is_questioned = False
        self.mines_around = 0


class MineSweeper:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "Сапер"

        # Налаштування (можна змінити)
        self.size = 8
        self.mines = 10

        # Ігрові структури
        self.cells: List[List[Cell]] = []
        self.cell_ui: List[List[ft.Container]] = []
        self.gesture_ui: List[List[ft.GestureDetector]] = []

        # Стан гри
        self.first_click = True
        self.game_over = False

        # Таймер
        self.start_time = None
        self.is_paused = False
        self.pause_time = 0

        # Опції
        self.no_flags = False
        self.dark_mode = False

        # Сканер
        self.scanner_uses = 3

        # Лічильник прапорців
        self.flags_count = 0

        # Лічильник мін для відображення (в UI показуємо mines - flags_count)
        self.remaining_mines = self.mines
        self.mines_text = ft.Text(f"Міни: {self.remaining_mines}")

        # Статистика сесії (Задача 2)
        self.games_played = 0
        self.games_won = 0
        self.stats_label = ft.Text("Ігор: 0  Перемог: 0%", size=14)

        # Рекорди (Задача 3)
        self.records = load_records()
        self.record_label = ft.Text(f"Рекорд: {self._get_record_display()}", size=14)

        # Побудова UI і старт
        self._build_ui()
        self.reset()

        # Запуск асинхронного таймера
        self.page.run_task(self._timer_loop)

    # ---------- UI ----------
    def _build_ui(self):
        self.timer = ft.Text("Час: 0")

        self.pause_btn = ft.IconButton(
            icon=ft.Icons.PAUSE,
            on_click=self._toggle_pause
        )

        self.theme_btn = ft.IconButton(
            icon=ft.Icons.DARK_MODE,
            on_click=self._toggle_theme
        )

        self.flags_switch = ft.Switch(
            label="Без прапорців",
            value=False,
            on_change=self._toggle_flags
        )

        self.scanner_btn = ft.TextButton(
            f"📡 Сканер ({self.scanner_uses})",
            on_click=self._scanner
        )

        top_row = ft.Row(
            controls=[
                self.theme_btn,
                self.pause_btn,
                self.scanner_btn,
                self.flags_switch,
                ft.ElevatedButton("Скинути", on_click=self._on_reset),
                self.mines_text
            ],
            alignment=ft.MainAxisAlignment.START,
            spacing=12
        )

        self.grid = ft.Column(spacing=4)

        # Додаємо таймер, рекорд і статистику під верхнім рядом
        self.page.add(
            top_row,
            self.timer,
            self.record_label,
            self.stats_label,
            self.grid
        )

    # ---------- TIMER ----------
    async def _timer_loop(self):
        while True:
            if self.start_time and not self.game_over and not self.is_paused:
                t = int(time.time() - self.start_time)
                self.timer.value = f"Час: {t}"
                self.page.update()
            await asyncio.sleep(1)

    # ---------- SETTINGS ----------
    def _toggle_theme(self, e):
        self.dark_mode = not self.dark_mode
        self.page.theme_mode = (
            ft.ThemeMode.DARK if self.dark_mode else ft.ThemeMode.LIGHT
        )
        self.page.update()

    def _toggle_pause(self, e):
        if self.game_over:
            return

        # Ігнорувати паузу до першого кліку
        if self.first_click:
            return

        self.is_paused = not self.is_paused

        if self.is_paused:
            self.pause_btn.icon = ft.Icons.PLAY_ARROW
            self.pause_time = time.time()
            self._hide()
        else:
            self.pause_btn.icon = ft.Icons.PAUSE
            if self.start_time is not None:
                self.start_time += time.time() - self.pause_time
            self._show()

        self.page.update()

    def _toggle_flags(self, e):
        self.no_flags = e.control.value

    # ---------- GAME ----------
    def reset(self):
        # Очистка структур
        self.cells = []
        self.cell_ui = []
        self.gesture_ui = []
        self.grid.controls.clear()

        self.first_click = True
        self.game_over = False
        self.start_time = None
        self.is_paused = False

        self.scanner_uses = 3
        self.scanner_btn.text = f"📡 Сканер ({self.scanner_uses})"
        self.scanner_btn.disabled = True

        # Скидаємо лічильник прапорців
        self.flags_count = 0

        self.remaining_mines = self.mines
        self.mines_text.value = f"Міни: {self.remaining_mines}"

        # Блокувати паузу до старту
        self.pause_btn.disabled = True

        for x in range(self.size):
            row = ft.Row(spacing=4)
            row_cells = []
            row_ui = []
            row_gest = []

            for y in range(self.size):
                c = Cell(x, y)
                row_cells.append(c)

                box = ft.Container(
                    width=CELL_SIZE,
                    height=CELL_SIZE,
                    bgcolor=ft.Colors.BLUE_GREY_300,
                    alignment=ft.Alignment.CENTER
                )

                g = ft.GestureDetector(
                    content=box,
                    on_tap=lambda e, cx=x, cy=y: self._click(cx, cy),
                    on_secondary_tap=lambda e, cx=x, cy=y: self._right_click(cx, cy),
                )

                row.controls.append(g)
                row_ui.append(box)
                row_gest.append(g)

            self.cells.append(row_cells)
            self.cell_ui.append(row_ui)
            self.gesture_ui.append(row_gest)
            self.grid.controls.append(row)

        # Оновлюємо UI-лейбли (на випадок, якщо розмір/мін змінилися)
        self.mines_text.value = f"Міни: {self.mines - self.flags_count}"
        self.record_label.value = f"Рекорд: {self._get_record_display()}"
        self.stats_label.value = f"Ігор: {self.games_played}  Перемог: {self._win_rate()}%"

        self.page.update()

    def _on_reset(self, e):
        self.reset()

    def _get_neighbors_coords(self, x: int, y: int):
        for i in range(max(0, x - 1), min(x + 2, self.size)):
            for j in range(max(0, y - 1), min(y + 2, self.size)):
                yield i, j

    def _set_mines(self, ex: int, ey: int):
        """
        Розставляємо міни після першого кліку.
        Клітинка (ex,ey) та її сусіди виключені з розстановки.
        """
        excluded = set()
        excluded.add((ex, ey))
        for i, j in self._get_neighbors_coords(ex, ey):
            excluded.add((i, j))

        placed = 0
        while placed < self.mines:
            x = random.randint(0, self.size - 1)
            y = random.randint(0, self.size - 1)
            if (x, y) not in excluded and not self.cells[x][y].is_mine:
                self.cells[x][y].is_mine = True
                placed += 1

        # Порахувати сусідів для всіх клітин
        for x in range(self.size):
            for y in range(self.size):
                if not self.cells[x][y].is_mine:
                    count = 0
                    for i, j in self._get_neighbors_coords(x, y):
                        if self.cells[i][j].is_mine:
                            count += 1
                    self.cells[x][y].mines_around = count

    def _click(self, x: int, y: int):
        if self.game_over or self.is_paused:
            return

        # Перший клік: розставити міни, запустити таймер, розблокувати паузу/сканер
        if self.first_click:
            self._set_mines(x, y)
            self.start_time = time.time()
            self.first_click = False
            self.pause_btn.disabled = False
            self.scanner_btn.disabled = False

        cell = self.cells[x][y]
        ui = self.cell_ui[x][y]

        # Захист від відкриття якщо вже відкрито або прапорець або знак питання
        if cell.is_revealed or cell.is_flagged or cell.is_questioned:
            return

        cell.is_revealed = True

        if cell.is_mine:
            ui.bgcolor = ft.Colors.RED
            ui.content = ft.Text("💣")
            self._reveal_all_mines()
            self.game_over = True
            self._on_game_end(won=False)
            self._show_game_over(False)
        else:
            ui.bgcolor = ft.Colors.GREY_200
            if cell.mines_around > 0:
                ui.content = ft.Text(str(cell.mines_around))
            else:
                ui.content = None
                self._reveal_neighbors(x, y)

            if self._check_win():
                self.game_over = True
                self._on_game_end(won=True)
                self._show_game_over(True)

        self.page.update()

    def _right_click(self, x: int, y: int):
        if self.no_flags or self.game_over or self.is_paused:
            return

        cell = self.cells[x][y]
        ui = self.cell_ui[x][y]

        # Не дозволяти змінювати стан вже відкритої клітини
        if cell.is_revealed:
            return

        # Цикл станів: звичайна -> прапорець -> знак питання -> звичайна
        if cell.is_questioned:
            # знак питання -> звичайна
            cell.is_questioned = False
        elif cell.is_flagged:
            # прапорець -> знак питання
            cell.is_flagged = False
            cell.is_questioned = True
            # зменшуємо лічильник прапорців
            self.flags_count = max(0, self.flags_count - 1)
        else:
            # звичайна -> прапорець
            cell.is_flagged = True
            self.flags_count += 1

        # Оновити UI клітини
        self._update_cell_ui(x, y)
        # Відображаємо скільки мін залишилось: mines - flags_count
        self.mines_text.value = f"Міни: {self.mines - self.flags_count}"
        self.page.update()

    def _update_cell_ui(self, x: int, y: int):
        cell = self.cells[x][y]
        ui = self.cell_ui[x][y]

        # Базовий вигляд закритої клітини
        ui.bgcolor = ft.Colors.BLUE_GREY_300
        ui.content = None

        if cell.is_revealed:
            ui.bgcolor = ft.Colors.GREY_200
            if cell.is_mine:
                ui.content = ft.Text("💣")
            elif cell.mines_around > 0:
                ui.content = ft.Text(str(cell.mines_around))
            else:
                ui.content = None
        else:
            if cell.is_flagged:
                ui.content = ft.Text("🚩")
            elif cell.is_questioned:
                ui.bgcolor = ft.Colors.AMBER_100
                ui.content = ft.Text("?", size=16)
            else:
                ui.content = None

    def _scanner(self, e):
        if self.scanner_uses <= 0 or self.first_click or self.game_over or self.is_paused:
            return

        safe = [
            c for row in self.cells for c in row
            if not c.is_mine and not c.is_revealed and not c.is_flagged and not c.is_questioned
        ]

        if not safe:
            return

        for c in random.sample(safe, min(3, len(safe))):
            self._click(c.x, c.y)

        self.scanner_uses -= 1
        self.scanner_btn.text = f"📡 Сканер ({self.scanner_uses})"
        if self.scanner_uses <= 0:
            self.scanner_btn.disabled = True

        self.page.update()

    def _hide(self):
        for x in range(self.size):
            for y in range(self.size):
                ui = self.cell_ui[x][y]
                ui.bgcolor = ft.Colors.GREY_400
                ui.content = None
        self.page.update()

    def _show(self):
        for x in range(self.size):
            for y in range(self.size):
                self._update_cell_ui(x, y)
        self.page.update()

    def _reveal_neighbors(self, x: int, y: int):
        stack = [(x, y)]
        while stack:
            cx, cy = stack.pop()
            for i, j in self._get_neighbors_coords(cx, cy):
                neighbor = self.cells[i][j]
                ui = self.cell_ui[i][j]
                if neighbor.is_revealed or neighbor.is_flagged or neighbor.is_questioned:
                    continue
                neighbor.is_revealed = True
                ui.bgcolor = ft.Colors.GREY_200
                if neighbor.mines_around > 0:
                    ui.content = ft.Text(str(neighbor.mines_around))
                else:
                    ui.content = None
                    stack.append((i, j))

    def _reveal_all_mines(self):
        for x in range(self.size):
            for y in range(self.size):
                cell = self.cells[x][y]
                ui = self.cell_ui[x][y]
                if cell.is_mine:
                    ui.bgcolor = ft.Colors.RED
                    ui.content = ft.Text("💣")
                elif cell.is_flagged and not cell.is_mine:
                    ui.bgcolor = ft.Colors.ORANGE_200
                    ui.content = ft.Text("❌")
        self.page.update()

    def _check_win(self) -> bool:
        for row in self.cells:
            for c in row:
                if not c.is_mine and not c.is_revealed:
                    return False
        return True

    def _get_record_display(self):
        rec = self.records.get(str(self.size))
        return rec if rec is not None else "-"

    def _win_rate(self) -> int:
        if self.games_played == 0:
            return 0
        return int(self.games_won / self.games_played * 100)

    def _on_game_end(self, won: bool):
        """
        Оновлює статистику та рекорд при завершенні гри.
        Викликається перед показом діалогу.
        """
        # Оновлюємо статистику сесії
        self.games_played += 1
        if won:
            self.games_won += 1

        # Оновлюємо лейбл статистики
        self.stats_label.value = f"Ігор: {self.games_played}  Перемог: {self._win_rate()}%"

        # Якщо виграли — перевіряємо рекорд
        if won and self.start_time is not None:
            elapsed = int(time.time() - self.start_time)
            key = str(self.size)
            current_record = self.records.get(key)
            # Якщо немає рекорду або новий час кращий (менший)
            if current_record is None or elapsed < current_record:
                self.records[key] = elapsed
                save_records(self.records)
                self.record_label.value = f"Рекорд: {elapsed}"
                # Показуємо коротке повідомлення про новий рекорд
                self.page.open(ft.SnackBar(content=ft.Text("Новий рекорд!")))
        else:
            # Оновлюємо лейбл рекорду (на випадок, якщо файл змінився)
            self.record_label.value = f"Рекорд: {self._get_record_display()}"

        # Оновлюємо mines label (щоб відобразити поточний стан)
        self.mines_text.value = f"Міни: {self.mines - self.flags_count}"

        self.page.update()

    def _show_game_over(self, won: bool):
        if won:
            for x in range(self.size):
                for y in range(self.size):
                    cell = self.cells[x][y]
                    ui = self.cell_ui[x][y]
                    if cell.is_mine:
                        ui.bgcolor = ft.Colors.GREEN_300
                        ui.content = ft.Text("🚩")
            dlg = ft.AlertDialog(
                title=ft.Text("Ви виграли!"),
                actions=[ft.TextButton("OK", on_click=lambda e: self._close_dialog(e))],
                actions_alignment=ft.MainAxisAlignment.END
            )
        else:
            dlg = ft.AlertDialog(
                title=ft.Text("Ви програли"),
                content=ft.Text("Натисніть Скинути, щоб почати заново."),
                actions=[ft.TextButton("OK", on_click=lambda e: self._close_dialog(e))],
                actions_alignment=ft.MainAxisAlignment.END
            )

        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

    def _close_dialog(self, e):
        if self.page.dialog:
            self.page.dialog.open = False
            self.page.update()


def main(page: ft.Page):
    page.window_width = 600
    page.window_height = 700
    MineSweeper(page)


if __name__ == "__main__":
    ft.app(target=main)
