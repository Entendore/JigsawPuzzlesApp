import sys
import math
import random
import time
from PySide6.QtCore import Qt, QTimer, QRectF, QPointF, Signal
from PySide6.QtGui import (QPainter, QPen, QBrush, QColor, QPixmap, 
                            QPainterPath, QPolygonF, QTransform)
from PySide6.QtWidgets import (QApplication, QMainWindow, QGraphicsScene, 
                                QGraphicsView, QGraphicsObject, QWidget, 
                                QVBoxLayout, QHBoxLayout, QPushButton, 
                                QComboBox, QLabel, QProgressBar, QFileDialog,
                                QDialog)

TAB_RATIO = 0.15
SNAP_DIST = 28
SHADOW_OFFSET = 4
SHADOW_ALPHA = 0.28
GHOST_ALPHA = 0.12

# ── Edge / Shape helpers ────────────────────────────────────────────

def make_edge_matrix(rows, cols):
    h = [[random.choice([1, -1]) for _ in range(cols)] for _ in range(rows - 1)]
    v = [[random.choice([1, -1]) for _ in range(rows)] for _ in range(cols - 1)]
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
    pts = [(a[0] + dx * f + nx * p, a[1] + dy * f + ny * p) for f, p in profile]
    pts.append(b)
    return pts

def build_piece_shape(r, c, pw, ph, ts, edges):
    tl, tr = (ts, ts + ph), (ts + pw, ts + ph)
    br, bl = (ts + pw, ts), (ts, ts)
    top, right, bot, left = edges
    pts = [tl]
    pts += _edge_points(tl, tr, top, ts)
    pts += _edge_points(tr, br, right, ts)
    pts += _edge_points(br, bl, bot, ts)
    pts += _edge_points(bl, tl, left, ts)
    return pts

# ── Generate Sample Images ──────────────────────────────────────────

def generate_sample_images(W=960, H=680):
    images = {}
    
    # Image 1: Sunset
    pm1 = QPixmap(W, H)
    p1 = QPainter(pm1)
    grad1 = QLinearGradient(0, 0, 0, H)
    grad1.setColorAt(0.0, QColor(20, 50, 120))
    grad1.setColorAt(0.5, QColor(220, 100, 50))
    grad1.setColorAt(1.0, QColor(20, 80, 30))
    p1.fillRect(0, 0, W, H, grad1)
    p1.setBrush(QColor(255, 220, 50))
    p1.setPen(Qt.NoPen)
    p1.drawEllipse(W-200, 100, 150, 150)
    p1.end()
    images["Sunset"] = pm1

    # Image 2: Ocean
    pm2 = QPixmap(W, H)
    p2 = QPainter(pm2)
    grad2 = QLinearGradient(0, 0, 0, H)
    grad2.setColorAt(0.0, QColor(135, 206, 250))
    grad2.setColorAt(0.6, QColor(0, 105, 148))
    grad2.setColorAt(1.0, QColor(0, 30, 60))
    p2.fillRect(0, 0, W, H, grad2)
    p2.setPen(Qt.NoPen)
    for i in range(0, W, 80):
        p2.setBrush(QColor(255, 255, 255, 40))
        path = QPainterPath()
        path.moveTo(i, H*0.5 + math.sin(i*0.05)*20)
        path.cubicTo(i+40, H*0.5 - 30, i+80, H*0.5 + 30, i+80, H*0.5 + math.sin((i+80)*0.05)*20)
        path.lineTo(i+80, H)
        path.lineTo(i, H)
        path.closeSubpath()
        p2.drawPath(path)
    p2.end()
    images["Ocean"] = pm2

    # Image 3: Forest
    pm3 = QPixmap(W, H)
    p3 = QPainter(pm3)
    grad3 = QLinearGradient(0, 0, 0, H)
    grad3.setColorAt(0.0, QColor(200, 230, 200))
    grad3.setColorAt(1.0, QColor(30, 80, 30))
    p3.fillRect(0, 0, W, H, grad3)
    p3.setPen(Qt.NoPen)
    for tx in range(100, W, 150):
        p3.setBrush(QColor(100, 60, 20))
        p3.drawRect(tx, H//2, 30, H//2)
        p3.setBrush(QColor(20, 110 + random.randint(-20,20), 20))
        p3.drawEllipse(tx-50, H//2 - 80, 130, 160)
    p3.end()
    images["Forest"] = pm3

    return images

# ── Puzzle Piece ─────────────────────────────────────────────────────

class PuzzlePiece(QGraphicsObject):
    placed = Signal()

    def __init__(self, pixmap, path, row, col, pw, ph, ts, correct_pos):
        super().__init__()
        self.pixmap = pixmap
        self.path = path
        self.row = row
        self.col = col
        self.pw = pw
        self.ph = ph
        self.ts = ts
        self.correct_pos = correct_pos
        self.is_placed = False
        
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setZValue(1)
        self.setCursor(Qt.OpenHandCursor)

    def boundingRect(self):
        return QRectF(0, 0, self.pw + 2*self.ts, self.ph + 2*self.ts)

    def shape(self):
        return self.path

    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw Shadow
        if not self.is_placed:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, int(SHADOW_ALPHA * 255)))
            painter.drawPath(self.path.translated(SHADOW_OFFSET, SHADOW_OFFSET))

        # Clip and draw image
        painter.setClipPath(self.path)
        painter.drawPixmap(0, 0, self.pixmap)
        painter.setClipping(False)

        # Draw outline
        pen = QPen(QColor(40, 40, 50), 1.5 if not self.is_placed else 0.8)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(self.path)

    def mousePressEvent(self, event):
        if self.is_placed:
            event.ignore()
            return
        self.setCursor(Qt.ClosedHandCursor)
        self.setZValue(100) # Bring to front
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self.is_placed:
            event.ignore()
            return
        self.setCursor(Qt.OpenHandCursor)
        super().mouseReleaseEvent(event)
        
        # Snap logic
        dist = math.hypot(self.x() - self.correct_pos.x(), self.y() - self.correct_pos.y())
        if dist < SNAP_DIST:
            self.setPos(self.correct_pos)
            self.is_placed = True
            self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsMovable, False)
            self.setZValue(-1) # Send to back when placed
            self.placed.emit()
            self.update()

# ── Board / Scene ───────────────────────────────────────────────────

class PuzzleScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pieces = []
        self.total = 0
        self.rows = 0
        self.cols = 0
        self._board_rect = QRectF()
        self.show_ghost = True
        self.original_pixmap = None

    def setup(self, pixmap, rows, cols, bx, by, pw, ph):
        self.clear()
        self.pieces = []
        self.total = rows * cols
        self.rows, self.cols = rows, cols
        self._board_rect = QRectF(bx, by, pw, ph)
        self.original_pixmap = pixmap
        self.setSceneRect(0, 0, self.parent().board_view.width(), self.parent().board_view.height())

        pcw, pch = pw / cols, ph / rows
        ts = TAB_RATIO * min(pcw, pch)
        edge_mat = make_edge_matrix(rows, cols)

        # Draw background board
        self.addRect(bx-2, by-2, pw+4, ph+4, QPen(QColor(60,60,70), 2), QBrush(QColor(240, 240, 245)))
        
        # Draw Grid
        pen = QPen(QColor(180, 180, 190, 80), 0.5)
        for r in range(rows + 1):
            y = by + r * pch
            self.addLine(bx, y, bx + pw, y, pen)
        for c in range(cols + 1):
            x = bx + c * pcw
            self.addLine(x, by, x, by + ph, pen)

        # Draw Ghost
        self.ghost_item = self.addPixmap(pixmap)
        self.ghost_item.setPos(bx, by)
        self.ghost_item.setOpacity(GHOST_ALPHA if self.show_ghost else 0.0)
        self.ghost_item.setZValue(-2)

        # Create Pieces
        for r in range(rows):
            for c in range(cols):
                shape_pts = build_piece_shape(r, c, pcw, pch, ts, edge_mat[r][c])
                path = QPainterPath()
                poly = QPolygonF([QPointF(x, y) for x, y in shape_pts])
                path.addPolygon(poly)
                path.closeSubpath()

                # Extract piece pixmap
                src_rect = QRectF(c*pcw - ts, r*pch - ts, pcw + 2*ts, pch + 2*ts)
                piece_pm = QPixmap(int(pcw + 2*ts), int(pch + 2*ts))
                piece_pm.fill(Qt.transparent)
                
                p_painter = QPainter(piece_pm)
                p_painter.setRenderHint(QPainter.Antialiasing)
                p_painter.setClipPath(path)
                p_painter.drawPixmap(0, 0, pixmap.copy(src_rect.toRect()))
                p_painter.end()

                correct_pos = QPointF(bx + c*pcw - ts, by + r*pch - ts)
                piece = PuzzlePiece(piece_pm, path, r, c, pcw, pch, ts, correct_pos)
                piece.setPos(correct_pos)
                piece.placed.connect(self.on_piece_placed)
                
                self.addItem(piece)
                self.pieces.append(piece)

        self.scatter_pieces()

    def scatter_pieces(self):
        m = 20
        for p in self.pieces:
            if p.is_placed: continue
            for _ in range(80):
                x = random.uniform(m, max(m+1, self.width() - p.pw - m))
                y = random.uniform(m, max(m+1, self.height() - p.ph - m))
                cx, cy = x + p.pw/2, y + p.ph/2
                if not self._board_rect.contains(QPointF(cx, cy)):
                    p.setPos(x, y)
                    break
            else:
                p.setPos(random.uniform(m, self.width() - p.pw - m), 
                         random.uniform(m, self.height() - p.ph - m))

    def toggle_ghost(self):
        self.show_ghost = not self.show_ghost
        self.ghost_item.setOpacity(GHOST_ALPHA if self.show_ghost else 0.0)

    def on_piece_placed(self):
        n = sum(1 for p in self.pieces if p.is_placed)
        if self.parent():
            self.parent().update_status(n, self.total)
        if n == self.total and self.parent():
            self.parent().on_win()

# ── Game / Main Window ──────────────────────────────────────────────

class Game(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🧩 Jigsaw Puzzle")
        self.resize(1100, 760)
        self.setMinimumSize(800, 550)

        self.sample_images = generate_sample_images()
        self.current_pixmap = self.sample_images["Sunset"]
        self.t0 = 0.0
        self.active = False
        self.paused = False
        self._pause_start = 0
        self._pause_accum = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        # UI Setup
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QWidget()
        toolbar.setFixedHeight(50)
        toolbar.setStyleSheet("background-color: #2e3040; color: white;")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(10, 5, 10, 5)

        title = QLabel("🧩 Jigsaw Puzzle")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        tb_layout.addWidget(title)

        self.diff_combo = QComboBox()
        self.diff_combo.addItems(["Easy (4×3)", "Medium (5×4)", "Hard (6×5)", "Expert (8×6)"])
        self.diff_combo.setStyleSheet("background-color: #4a4d5e; padding: 4px; color: white;")
        tb_layout.addWidget(self.diff_combo)

        self.img_combo = QComboBox()
        self.img_combo.addItems(self.sample_images.keys())
        self.img_combo.setStyleSheet("background-color: #4a4d5e; padding: 4px; color: white;")
        tb_layout.addWidget(self.img_combo)

        buttons = [
            ("New", self.new_game), ("Shuffle", self.shuffle), 
            ("Load", self._desktop_load), ("Reference", self.show_reference),
            ("Hint", self.give_hint), ("Ghost", self._toggle_ghost), ("Pause", self.toggle_pause)
        ]
        self._pause_btn = None
        for text, cb in buttons:
            btn = QPushButton(text)
            btn.setStyleSheet("background-color: #4a4d5e; padding: 4px 8px; color: white;")
            btn.clicked.connect(cb)
            if text == "Pause": self._pause_btn = btn
            tb_layout.addWidget(btn)

        self.progress = QProgressBar()
        self.progress.setFixedHeight(15)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet("QProgressBar { background-color: #1f2028; border: none; } QProgressBar::chunk { background-color: #38a946; }")
        tb_layout.addWidget(self.progress)

        self.status = QLabel("")
        self.status.setStyleSheet("font-size: 14px; padding-left: 10px;")
        tb_layout.addWidget(self.status)
        
        layout.addWidget(toolbar)

        # Board View
        self.board_view = QGraphicsView()
        self.board_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.board_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.board_view.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.board_view.setStyleSheet("background-color: #2e3040;")
        layout.addWidget(self.board_view)

        self.board = PuzzleScene(self)
        self.board_view.setScene(self.board)

        QTimer.singleShot(150, self.new_game)

    def _parse_diff(self):
        t = self.diff_combo.currentText()
        if "Easy" in t:   return 3, 4
        if "Hard" in t:   return 5, 6
        if "Expert" in t: return 6, 8
        return 4, 5

    def new_game(self):
        if self.paused:
            self.toggle_pause()
        self.current_pixmap = self.sample_images[self.img_combo.currentText()]
        
        rows, cols = self._parse_diff()
        margin = 35
        aw = self.board_view.width() - 2 * margin
        ah = self.board_view.height() - 2 * margin
        
        pm = self.current_pixmap.scaled(int(aw), int(ah), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        pw, ph = pm.width(), pm.height()
        bx = (self.board_view.width() - pw) / 2
        by = (self.board_view.height() - ph) / 2

        self.board.setup(pm, rows, cols, bx, by, pw, ph)
        self.t0 = time.time()
        self.active = True
        self._pause_accum = 0
        self._timer.start(500)
        self.update_status(0, rows * cols)

    def _elapsed(self):
        if not self.active: return int(self._pause_accum) if self._pause_accum else 0
        return int(time.time() - self.t0 - self._pause_accum)

    def _tick(self):
        if not self.active or self.paused: return
        n = sum(1 for p in self.board.pieces if p.is_placed)
        m, s = divmod(self._elapsed(), 60)
        self.status.setText(f"{n}/{self.board.total}   {m}:{s:02d}")

    def update_status(self, placed, total):
        m, s = divmod(self._elapsed(), 60)
        self.status.setText(f"{placed}/{total}   {m}:{s:02d}")
        self.progress.setValue(int((placed / max(1, total)) * 100))

    def toggle_pause(self):
        if not self.active: return
        self.paused = not self.paused
        self._pause_btn.setText("Resume" if self.paused else "Pause")
        if self.paused:
            self._pause_start = time.time()
            for p in self.board.pieces: 
                if not p.is_placed: p.setVisible(False)
        else:
            self._pause_accum += time.time() - self._pause_start
            for p in self.board.pieces: p.setVisible(True)

    def give_hint(self):
        unplaced = [p for p in self.board.pieces if not p.is_placed]
        if not unplaced: return
        piece = random.choice(unplaced)
        # Flash the piece opacity
        piece.setOpacity(0.3)
        QTimer.singleShot(250, lambda: piece.setOpacity(1.0))
        QTimer.singleShot(500, lambda: piece.setOpacity(0.3))
        QTimer.singleShot(750, lambda: piece.setOpacity(1.0))

    def _toggle_ghost(self):
        self.board.toggle_ghost()

    def shuffle(self):
        self.board.scatter_pieces()

    def show_reference(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Reference Image")
        layout = QVBoxLayout(dlg)
        lbl = QLabel()
        lbl.setPixmap(self.current_pixmap.scaled(600, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        layout.addWidget(lbl)
        dlg.exec()

    def _desktop_load(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose an Image", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)")
        if path:
            pm = QPixmap(path)
            if not pm.isNull():
                self.sample_images["Custom"] = pm
                self.img_combo.addItem("Custom")
                self.img_combo.setCurrentText("Custom")
                self.new_game()

    def on_win(self):
        self.active = False
        self._timer.stop()
        m, s = divmod(self._elapsed(), 60)
        
        dlg = QDialog(self)
        dlg.setWindowTitle("🎉 PUZZLE COMPLETE! 🎉")
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel(f"Pieces: {self.board.total}\nTime: {m}:{s:02d}\nDifficulty: {self.diff_combo.currentText()}"))
        btn = QPushButton("Play Again")
        btn.clicked.connect(lambda: (dlg.accept(), self.new_game()))
        layout.addWidget(btn)
        dlg.exec()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # Set Dark Palette
    palette = app.palette()
    palette.setColor(palette.ColorRole.Window, QColor(46, 48, 64))
    palette.setColor(palette.ColorRole.WindowText, Qt.white)
    palette.setColor(palette.ColorRole.Base, QColor(35, 37, 50))
    palette.setColor(palette.ColorRole.AlternateBase, QColor(46, 48, 64))
    palette.setColor(palette.ColorRole.ToolTipBase, Qt.white)
    palette.setColor(palette.ColorRole.ToolTipText, Qt.white)
    palette.setColor(palette.ColorRole.Text, Qt.white)
    palette.setColor(palette.ColorRole.Button, QColor(46, 48, 64))
    palette.setColor(palette.ColorRole.ButtonText, Qt.white)
    palette.setColor(palette.ColorRole.BrightText, Qt.red)
    palette.setColor(palette.ColorRole.Link, QColor(42, 130, 218))
    palette.setColor(palette.ColorRole.Highlight, QColor(42, 130, 218))
    palette.setColor(palette.ColorRole.HighlightedText, Qt.black)
    app.setPalette(palette)

    window = Game()
    window.show()
    sys.exit(app.exec())