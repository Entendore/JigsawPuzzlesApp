#!/usr/bin/env python3
"""
Jigsaw Puzzle — Desktop Window App
"""

import os
import math
import random
import time

from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.scatter import Scatter
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.popup import Popup
from kivy.uix.spinner import Spinner
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.image import Image as KivyImage
from kivy.graphics import (
    Color, Rectangle, Line, Mesh,
    StencilPush, StencilUse, StencilUnUse, StencilPop,
    Ellipse, Triangle,
)
from kivy.graphics.fbo import Fbo
from kivy.core.window import Window
from kivy.core.image import Image as CoreImage
from kivy.properties import BooleanProperty, NumericProperty
from kivy.clock import Clock
from kivy.animation import Animation

Window.size = (1100, 760)
Window.minimum_width, Window.minimum_height = 800, 550
Window.clearcolor = (0.18, 0.20, 0.26, 1)

TAB_RATIO = 0.15
SNAP_DIST = 28
SHADOW_OFFSET = 4
SHADOW_ALPHA = 0.28
GHOST_ALPHA = 0.12


# ── edge / shape helpers ────────────────────────────────────────────

def make_edge_matrix(rows, cols):
    h = [[random.choice([1, -1]) for _ in range(cols)]
         for _ in range(rows - 1)]
    v = [[random.choice([1, -1]) for _ in range(rows)]
         for _ in range(cols - 1)]
    mat = []
    for r in range(rows):
        row = []
        for c in range(cols):
            row.append((
                -h[r - 1][c] if r > 0 else 0,
                 v[c][r]   if c < cols - 1 else 0,
                 h[r][c]   if r < rows - 1 else 0,
                -v[c - 1][r] if c > 0 else 0,
            ))
        mat.append(row)
    return mat


def _edge_points(a, b, tab_type, ts):
    if tab_type == 0:
        return [b]
    dx, dy = b[0] - a[0], b[1] - a[1]
    ln = math.hypot(dx, dy)
    if ln < 1:
        return [b]
    ux, uy = dx / ln, dy / ln
    nx, ny = -uy, ux
    s = tab_type * ts
    profile = [
        (.340,  0.0),    (.352, -s * 0.03), (.368, -s * 0.06),
        (.388, -s * 0.04), (.405,  s * 0.08), (.420,  s * 0.24),
        (.438,  s * 0.48), (.455,  s * 0.70), (.472,  s * 0.88),
        (.488,  s * 0.97), (.500,  s * 1.00), (.512,  s * 0.97),
        (.528,  s * 0.88), (.545,  s * 0.70), (.562,  s * 0.48),
        (.580,  s * 0.24), (.595,  s * 0.08), (.612, -s * 0.04),
        (.632, -s * 0.06), (.648, -s * 0.03), (.660,  0.0),
    ]
    pts = [(a[0] + dx * f + nx * p, a[1] + dy * f + ny * p)
           for f, p in profile]
    pts.append(b)
    return pts


def build_piece_shape(r, c, pw, ph, ts, edges):
    t = ts
    tl, tr = (t, t + ph), (t + pw, t + ph)
    br, bl = (t + pw, t), (t, t)
    top, right, bot, left = edges
    pts = [tl]
    pts += _edge_points(tl, tr, top, ts)
    pts += _edge_points(tr, br, right, ts)
    pts += _edge_points(br, bl, bot, ts)
    pts += _edge_points(bl, tl, left, ts)
    return pts


# ── Piece ────────────────────────────────────────────────────────────

class Piece(Scatter):
    placed = BooleanProperty(False)

    def __init__(self, texture, shape, pw, ph, ts,
                 row, col, rows, cols, puzzle_w, puzzle_h, **kw):
        self._shape = shape
        self._pw, self._ph, self._ts = pw, ph, ts
        self.row, self.col = row, col
        self.ww = pw + 2 * ts
        self.wh = ph + 2 * ts
        self.correct_pos = None
        self._pulse_event = None

        super().__init__(**kw)
        self.size = (self.ww, self.wh)
        self.do_scale = self.do_rotation = False

        cx, cy = ts + pw / 2, ts + ph / 2
        self._verts = [cx, cy]
        for p in shape:
            self._verts += [p[0], p[1]]
        n = len(shape)
        self._idx = []
        for i in range(n):
            self._idx += [0, i + 1, (i + 1) % n + 1]

        self._line_pts = []
        for p in shape:
            self._line_pts += [p[0], p[1]]
        self._line_pts += [shape[0][0], shape[0][1]]

        self._tex_pos = (ts - col * pw, ts - (rows - row - 1) * ph)
        self._tex_size = (puzzle_w, puzzle_h)

        so = SHADOW_OFFSET
        self._shadow_verts = [cx + so, cy - so]
        for p in shape:
            self._shadow_verts += [p[0] + so, p[1] - so]

        self._tex_ref = texture
        self._draw_floating()

    def _draw_floating(self):
        self.canvas.clear()
        with self.canvas:
            Color(0, 0, 0, SHADOW_ALPHA)
            Mesh(vertices=self._shadow_verts, indices=self._idx,
                 mode="triangles")
            self._draw_piece_body(outline_w=1.6, glow_a=0.15)

    def _draw_placed(self):
        self.canvas.clear()
        with self.canvas:
            self._draw_piece_body(outline_w=0.8, glow_a=0.0)

    def _draw_piece_body(self, outline_w=1.6, glow_a=0.15):
        with self.canvas:
            StencilPush()
            Color(1, 1, 1, 1)
            Mesh(vertices=self._verts, indices=self._idx, mode="triangles")
            StencilUse()
            Color(1, 1, 1, 1)
            Rectangle(texture=self._tex_ref,
                      pos=self._tex_pos, size=self._tex_size)
            StencilUnUse()
            StencilPop()
            Color(0.05, 0.05, 0.07)
            Line(points=self._line_pts, width=outline_w, close=True)
            if glow_a > 0:
                Color(0.50, 0.60, 0.78, glow_a)
                Line(points=self._line_pts, width=3.5, close=True)

    def start_hint_pulse(self):
        if self._pulse_event:
            return
        self._pulse_step = 0
        self._pulse_event = Clock.schedule_interval(self._do_pulse, 0.25)

    def stop_hint_pulse(self):
        if self._pulse_event:
            self._pulse_event.cancel()
            self._pulse_event = None
        Animation.stop_all(self, 'opacity')
        self.opacity = 1.0

    def _do_pulse(self, _dt):
        self._pulse_step += 1
        target = 0.30 if self._pulse_step % 2 else 1.0
        Animation(opacity=target, duration=0.12).start(self)

    def on_touch_down(self, touch):
        if self.placed:
            return False
        if self.collide_point(*touch.pos):
            self.stop_hint_pulse()
            p = self.parent
            if p:
                p.remove_widget(self)
                p.add_widget(self)
            Animation.stop_all(self, 'scale')
            Animation(scale=1.06, duration=0.07).start(self)
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if self.placed or self.correct_pos is None:
            return super().on_touch_up(touch)
        if touch.grab_current is not self:
            return super().on_touch_up(touch)
        Animation.stop_all(self, 'scale')
        Animation(scale=1.0, duration=0.06).start(self)
        dx = self.x - self.correct_pos[0]
        dy = self.y - self.correct_pos[1]
        if math.hypot(dx, dy) < SNAP_DIST:
            self.pos = self.correct_pos
            self.placed = True
            self.do_translate = False
            self._draw_placed()
            anim = Animation(opacity=0.55, duration=0.08)
            anim += Animation(opacity=1.0, duration=0.12)
            anim.start(self)
            p = self.parent
            if p:
                p.remove_widget(self)
                p.add_widget(self, index=0)
                if hasattr(p, "on_piece_placed"):
                    p.on_piece_placed()
        return super().on_touch_up(touch)


# ── ProgressIndicator (renamed to avoid Kivy class conflict) ────────

class ProgressIndicator(Widget):
    progress = NumericProperty(0.0)

    def __init__(self, **kw):
        super().__init__(**kw)
        self.bind(progress=self._redraw, size=self._redraw, pos=self._redraw)

    def _redraw(self, *_):
        self.canvas.clear()
        if self.width < 2:
            return
        with self.canvas:
            Color(0.12, 0.13, 0.18)
            Rectangle(pos=self.pos, size=self.size)
            fw = self.width * max(0.0, min(1.0, self.progress))
            if fw > 1:
                Color(0.22, 0.58, 0.32)
                Rectangle(pos=self.pos, size=(fw, self.height))
                Color(0.32, 0.72, 0.42, 0.45)
                Rectangle(pos=self.pos,
                          size=(fw, self.height * 0.45))
            Color(0.35, 0.38, 0.48, 0.8)
            Line(rectangle=(*self.pos, *self.size), width=1)


# ── Board ────────────────────────────────────────────────────────────

class Board(Widget):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.pieces = []
        self.total = 0
        self.rows = self.cols = 0
        self._board_rect = (0, 0, 0, 0)
        self.ghost_color_instr = None
        self.show_ghost = True
        self._target_hint = []

    def setup(self, texture, rows, cols, bx, by, pw, ph):
        self.clear_widgets()
        self.canvas.clear()
        self.pieces.clear()
        self.total = rows * cols
        self.rows, self.cols = rows, cols
        self._board_rect = (bx, by, pw, ph)

        pcw, pch = pw / cols, ph / rows
        ts = TAB_RATIO * min(pcw, pch)
        edge_mat = make_edge_matrix(rows, cols)

        with self.canvas:
            Color(0, 0, 0, 0.22)
            Rectangle(pos=(bx + 5, by - 5), size=(pw, ph))
            Color(0.90, 0.90, 0.93, 1)
            Rectangle(pos=(bx, by), size=(pw, ph))
            self.ghost_color_instr = Color(
                1, 1, 1, GHOST_ALPHA if self.show_ghost else 0)
            Rectangle(texture=texture, pos=(bx, by), size=(pw, ph))
            Color(0.72, 0.72, 0.78, 0.30)
            for r in range(rows + 1):
                y = by + r * pch
                Line(points=[bx, y, bx + pw, y], width=0.5)
            for c in range(cols + 1):
                x = bx + c * pcw
                Line(points=[x, by, x, by + ph], width=0.5)
            Color(0.40, 0.42, 0.52, 0.8)
            Line(rectangle=(bx, by, pw, ph), width=2)

        for r in range(rows):
            for c in range(cols):
                shape = build_piece_shape(
                    r, c, pcw, pch, ts, edge_mat[r][c])
                p = Piece(texture, shape, pcw, pch, ts,
                          r, c, rows, cols, pw, ph)
                p.correct_pos = (
                    bx + c * pcw - ts,
                    by + (rows - r - 1) * pch - ts,
                )
                self.add_widget(p)
                self.pieces.append(p)

        self.scatter_pieces()

    def scatter_pieces(self):
        bx, by, pw, ph = self._board_rect
        m = 10
        w, h = self.width, self.height
        for p in self.pieces:
            if p.placed:
                continue
            placed = False
            for _ in range(80):
                x = random.uniform(m, max(m + 1, w - p.ww - m))
                y = random.uniform(m, max(m + 1, h - p.wh - m))
                cx = x + p.ww / 2
                cy = y + p.wh / 2
                overlap = (
                    cx > bx + pw * 0.10 and cx < bx + pw * 0.90
                    and cy > by + ph * 0.10 and cy < by + ph * 0.90
                )
                if not overlap:
                    p.pos = (x, y)
                    placed = True
                    break
            if not placed:
                p.pos = (
                    random.uniform(m, max(m + 1, w - p.ww - m)),
                    random.uniform(m, max(m + 1, h - p.wh - m)),
                )

    def toggle_ghost(self):
        self.show_ghost = not self.show_ghost
        if self.ghost_color_instr:
            self.ghost_color_instr.a = GHOST_ALPHA if self.show_ghost else 0

    def get_hint_piece(self):
        unplaced = [p for p in self.pieces if not p.placed]
        return random.choice(unplaced) if unplaced else None

    def show_target(self, piece):
        self.hide_target()
        x, y = piece.correct_pos
        ts = piece._ts
        pw, ph = piece._pw, piece._ph
        with self.canvas.after:
            c = Color(0.20, 0.92, 0.35, 0.55)
            l = Line(rectangle=(x + ts, y + ts, pw, ph), width=2.5)
            mx, my = x + ts + pw / 2, y + ts + ph / 2
            cr = min(pw, ph) * 0.15
            lc = Color(0.20, 0.92, 0.35, 0.35)
            l1 = Line(points=[mx - cr, my, mx + cr, my], width=1.5)
            l2 = Line(points=[mx, my - cr, mx, my + cr], width=1.5)
            self._target_hint = [c, l, lc, l1, l2]

    def hide_target(self):
        for instr in self._target_hint:
            try:
                self.canvas.after.remove(instr)
            except Exception:
                pass
        self._target_hint = []

    def on_piece_placed(self):
        n = sum(1 for p in self.pieces if p.placed)
        g = self.parent
        if hasattr(g, "update_status"):
            g.update_status(n, self.total)
        if n == self.total and hasattr(g, "on_win"):
            g.on_win()


class ToolButton(Button):
    pass


# ── Game ─────────────────────────────────────────────────────────────

class Game(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation='vertical', **kw)
        self.texture = None
        self.t0 = 0.0
        self._timer = None
        self.active = False
        self.paused = False
        self._pause_start = 0
        self._pause_accum = 0
        self._hint_piece = None
        self._hint_clock = None
        self._moves = 0

        bar = BoxLayout(size_hint_y=None, height=52,
                        spacing=4, padding=(8, 5))

        title = Label(text="🧩 Jigsaw Puzzle",
                      font_size=18, bold=True,
                      color=(1, 1, 1, 1),
                      size_hint_x=0.14)
        bar.add_widget(title)

        self.diff = Spinner(
            text="Medium (5×4)",
            values=["Easy (4×3)", "Medium (5×4)", "Hard (6×5)",
                    "Expert (8×6)"],
            size_hint_x=0.12, font_size=12,
            background_color=(0.38, 0.41, 0.52, 1),
            color=(1, 1, 1, 1),
        )
        bar.add_widget(self.diff)

        bkw = dict(font_size=11, padding=(4, 3))
        buttons_cfg = [
            ("New",      self.new_game,       0.055),
            ("Shuffle",  self.shuffle,        0.065),
            ("Load",     self._desktop_load,  0.055),
            ("Reference",self.show_reference, 0.075),
            ("Hint",     self.give_hint,      0.055),
            ("Ghost",    self._toggle_ghost,  0.055),
            ("Pause",    self.toggle_pause,   0.055),
        ]
        self._pause_btn = None
        for txt, cb, sx in buttons_cfg:
            b = ToolButton(text=txt, size_hint_x=sx, **bkw)
            b.bind(on_press=cb)
            if txt == "Pause":
                self._pause_btn = b
            bar.add_widget(b)

        self.progress = ProgressIndicator(size_hint_x=0.08,
                                          size_hint_y=None, height=14)
        bar.add_widget(self.progress)

        self.status = Label(text="",
                            size_hint_x=0.18,
                            font_size=13,
                            color=(0.82, 0.88, 1, 1),
                            halign="center")
        bar.add_widget(self.status)
        self.add_widget(bar)

        self.board = Board()
        self.add_widget(self.board)

        Window.bind(on_keyboard=self._on_key)
        Clock.schedule_once(self._boot, 0.12)

    def _on_key(self, _win, key, _sc, _cp, _mod):
        if key == 110:    self.new_game(None)
        elif key == 104:  self.give_hint(None)
        elif key == 112:  self.toggle_pause(None)
        elif key == 114:  self.show_reference(None)
        elif key == 115:  self.shuffle(None)
        elif key == 103:  self._toggle_ghost(None)

    def _boot(self, _dt):
        self._make_sample_image()
        Clock.schedule_once(lambda _: self.new_game(None), 0.15)

    def _make_sample_image(self):
        W, H = 960, 680
        fbo = Fbo(size=(W, H))

        with fbo:
            for i in range(60):
                t = i / 60
                Color(0.04 + t * .30, 0.08 + t * .38, 0.40 + t * .50)
                bh = H // 60 + 1
                Rectangle(pos=(0, i * bh), size=(W, bh))

            R = random.Random(42)

            Color(1, .93, .32)
            Ellipse(pos=(650, 420), size=(130, 130))
            Color(1, .96, .50, .18)
            Ellipse(pos=(620, 390), size=(190, 190))
            Color(1, .98, .65, .08)
            Ellipse(pos=(590, 360), size=(250, 250))

            mtn = [(0, 230), (90, 380), (210, 260), (350, 350),
                   (480, 235), (620, 330), (770, 250), (900, 300),
                   (960, 260), (960, 230), (0, 230)]
            Color(.30, .46, .26)
            for i in range(len(mtn) - 2):
                Triangle(points=list(mtn[0]) + list(mtn[i + 1])
                         + list(mtn[i + 2]))
            Color(.95, .97, 1)
            for cx, cy in [(90, 380), (480, 235), (770, 250)]:
                Triangle(points=[cx - 24, cy - 30, cx, cy + 10,
                                 cx + 24, cy - 30])

            Color(.25, .50, .22)
            for _ in range(8):
                Ellipse(pos=(R.randint(0, W), R.randint(180, 260)),
                        size=(R.randint(120, 280), R.randint(42, 98)))

            Color(.20, .50, .14)
            Rectangle(pos=(0, 0), size=(W, 160))
            Color(.16, .42, .11)
            Rectangle(pos=(0, 130), size=(W, 35))

            Color(.24, .54, .18)
            for _ in range(25):
                Ellipse(pos=(R.randint(0, W), R.randint(100, 185)),
                        size=(R.randint(40, 120), R.randint(16, 40)))

            for tx in [60, 170, 310, 470, 620, 780, 890]:
                th = R.randint(60, 110)
                Color(.38, .24, .08)
                Rectangle(pos=(tx - 6, 120), size=(12, th))
                g = .40 + R.random() * .18
                Color(.08, g, .08)
                Ellipse(pos=(tx - 30, 120 + th - 20), size=(60, 70))
                Color(.11, g + .06, .11)
                Ellipse(pos=(tx - 22, 120 + th + 4), size=(44, 48))

            fc = [(1, .28, .28), (1, .80, .18), (.88, .28, .88),
                  (1, 1, .32), (1, .52, .52), (.52, .28, 1),
                  (1, .65, .15), (.3, .8, 1)]
            for _ in range(80):
                Color(*R.choice(fc), .85)
                Ellipse(pos=(R.randint(3, W - 3), R.randint(3, 130)),
                        size=(R.randint(4, 14),) * 2)

            Color(1, 1, 1, .55)
            for cx, cy, sc in [(100, 500, 1.), (320, 530, .75),
                               (680, 490, .90), (870, 520, .65),
                               (500, 555, .55)]:
                for dx, dy, r in [(-24, 0, 30), (8, 14, 38),
                                  (36, 3, 28), (16, -12, 24),
                                  (-8, 10, 20)]:
                    Ellipse(pos=(cx + dx * sc - r * sc,
                                 cy + dy * sc - r * sc),
                            size=(r * 2 * sc, r * 2 * sc))

            Color(.18, .40, .70, .40)
            for i in range(0, 155, 6):
                xo = math.sin(i * .052) * 40
                Ellipse(pos=(440 + xo - 24, i - 6), size=(48, 15))
            Color(.30, .55, .85, .18)
            for i in range(0, 155, 6):
                xo = math.sin(i * .052) * 40
                Ellipse(pos=(438 + xo - 18, i - 4), size=(30, 8))

            Color(.15, .15, .18, .6)
            for bx_, by_ in [(200, 560), (240, 575),
                              (580, 545), (620, 560)]:
                s = 8
                Line(points=[bx_ - s, by_ + s // 2, bx_, by_,
                             bx_ + s, by_ + s // 2], width=1.2)

            rainbow = [(.90, .20, .20), (1, .55, .10),
                       (1, .90, .15), (.20, .80, .20),
                       (.20, .50, .90), (.45, .20, .75)]
            for idx, rc in enumerate(rainbow):
                Color(*rc, 0.13)
                rr = 260 - idx * 14
                Ellipse(pos=(180 - rr, 340 - rr), size=(rr * 2, rr * 2))

        fbo.draw()
        fbo.bind()
        self.texture = fbo.texture
        fbo.release()

    def _parse_diff(self):
        t = self.diff.text
        if "Easy" in t:   return 3, 4
        if "Hard" in t:   return 5, 6
        if "Expert" in t: return 6, 8
        return 4, 5

    def new_game(self, _):
        self._clear_hint()
        if self._timer:
            self._timer.cancel()
        if self.texture is None:
            return
        if self.paused:
            self.toggle_pause(None)

        rows, cols = self._parse_diff()
        margin = 35
        aw = self.board.width - 2 * margin
        ah = self.board.height - 2 * margin
        ar = self.texture.width / self.texture.height
        if aw / ah > ar:
            ph = ah; pw = ph * ar
        else:
            pw = aw; ph = pw / ar
        bx = (self.board.width - pw) / 2
        by = (self.board.height - ph) / 2

        self.board.setup(self.texture, rows, cols, bx, by, pw, ph)
        self.t0 = time.time()
        self.active = True
        self.paused = False
        self._pause_accum = 0
        self._moves = 0
        self._timer = Clock.schedule_interval(self._tick, 0.5)
        self.update_status(0, rows * cols)

    def _elapsed(self):
        if not self.active:
            return int(self._pause_accum) if self._pause_accum else 0
        return int(time.time() - self.t0 - self._pause_accum)

    def _tick(self, _):
        if not self.active or self.paused:
            return
        n = sum(1 for p in self.board.pieces if p.placed)
        m, s = divmod(self._elapsed(), 60)
        self.status.text = f"{n}/{self.board.total}   {m}:{s:02d}"
        self.progress.progress = n / max(1, self.board.total)

    def update_status(self, placed, total):
        m, s = divmod(self._elapsed(), 60)
        self.status.text = f"{placed}/{total}   {m}:{s:02d}"
        self.progress.progress = placed / max(1, total)

    def toggle_pause(self, _):
        if not self.active:
            return
        self.paused = not self.paused
        if self._pause_btn:
            self._pause_btn.text = "Resume" if self.paused else "Pause"
        if self.paused:
            self._pause_start = time.time()
            for p in self.board.pieces:
                if not p.placed:
                    p.opacity = 0
        else:
            self._pause_accum += time.time() - self._pause_start
            for p in self.board.pieces:
                p.opacity = 1

    def give_hint(self, _):
        self._clear_hint()
        piece = self.board.get_hint_piece()
        if piece is None:
            return
        self._hint_piece = piece
        piece.start_hint_pulse()
        self.board.show_target(piece)
        self._hint_clock = Clock.schedule_once(
            lambda _: self._clear_hint(), 3.5)

    def _clear_hint(self):
        if self._hint_piece:
            self._hint_piece.stop_hint_pulse()
            self._hint_piece = None
        self.board.hide_target()
        if self._hint_clock:
            self._hint_clock.cancel()
            self._hint_clock = None

    def _toggle_ghost(self, _):
        self.board.toggle_ghost()

    def on_win(self):
        self.active = False
        self._clear_hint()
        if self._timer:
            self._timer.cancel()
        m, s = divmod(self._elapsed(), 60)

        for p in self.board.pieces:
            a = Animation(opacity=0.6, duration=0.15)
            a += Animation(opacity=1.0, duration=0.15)
            a.repeat = True
            a.start(p)
            Clock.schedule_once(
                lambda pp=p: Animation.stop_all(pp, 'opacity'), 2.5)

        box = BoxLayout(orientation="vertical", padding=28, spacing=14)
        box.add_widget(Label(
            text="🎉  PUZZLE COMPLETE!  🎉",
            font_size=22, bold=True,
            color=(0.15, 0.55, 0.25, 1),
            halign="center", size_hint_y=None, height=44))
        box.add_widget(Label(
            text=(f"Pieces:       {self.board.total}\n"
                  f"Time:           {m}:{s:02d}\n"
                  f"Difficulty:  {self.diff.text}"),
            font_size=17, color=(.30, .30, .35, 1),
            halign="left", size_hint_y=None, height=80))
        btn = ToolButton(text="Play Again", size_hint_y=None, height=46,
                         font_size=15, bold=True)
        box.add_widget(btn)
        popup = Popup(title="", content=box,
                      size_hint=(0.38, 0.40),
                      separator_height=0,
                      background_color=(.95, .95, .97, 1))
        btn.bind(on_press=lambda _: (popup.dismiss(),
                                     self.new_game(None)))
        popup.open()

    def shuffle(self, _):
        self._clear_hint()
        self.board.scatter_pieces()

    def show_reference(self, _):
        if self.texture is None:
            return
        img = KivyImage(texture=self.texture)
        Popup(title="Reference Image", content=img,
              size_hint=(0.65, 0.78),
              background_color=(.95, .95, .97, 1)).open()

    def _desktop_load(self, _):
        fc = FileChooserListView(
            filters=["*.png", "*.jpg", "*.jpeg", "*.bmp", "*.gif"],
            dirselect=False)
        fc.path = os.path.expanduser("~")
        box = BoxLayout(orientation="vertical", spacing=6)
        box.add_widget(fc)
        row = BoxLayout(size_hint_y=None, height=50,
                        spacing=10, padding=10)
        bc = ToolButton(text="Cancel")
        bl = ToolButton(text="Load", bold=True)
        row.add_widget(Widget())
        row.add_widget(bc)
        row.add_widget(bl)
        row.add_widget(Widget())
        box.add_widget(row)
        popup = Popup(title="Choose an Image", content=box,
                      size_hint=(0.80, 0.80),
                      background_color=(.95, .95, .97, 1))

        def cancel(_):
            popup.dismiss()

        def load(_):
            if fc.selection:
                path = fc.selection[0]
                try:
                    self.texture = CoreImage(path).texture
                    self.new_game(None)
                    popup.dismiss()
                except Exception as e:
                    err = Popup(
                        title="Error",
                        content=Label(text=f"Failed to load:\n{e}",
                                      padding=16),
                        size_hint=(0.4, 0.25))
                    err.open()

        bc.bind(on_press=cancel)
        bl.bind(on_press=load)
        popup.open()


class JigsawPuzzleApp(App):
    def build(self):
        self.title = "Jigsaw Puzzle"
        return Game()


if __name__ == "__main__":
    JigsawPuzzleApp().run()