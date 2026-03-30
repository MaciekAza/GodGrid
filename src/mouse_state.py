from dataclasses import dataclass


@dataclass
class MouseState:
    dragging: bool = False
    painting: bool = False
    last_paint_tile: tuple[int, int] | None = None

    def start_paint(self):
        self.painting = True

    def stop_paint(self):
        self.painting = False
        self.last_paint_tile = None

    def start_drag(self):
        self.dragging = True

    def stop_drag(self):
        self.dragging = False
