import sys
import json
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTabWidget, QListWidget, QCheckBox, QLabel, QGroupBox, 
    QTextEdit, QDoubleSpinBox, QGridLayout
)
from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QKeyEvent, QMouseEvent, QWheelEvent

class NGonCanvas(QWidget):
    pointsChanged = Signal(list)
    selectionChanged = Signal(int)

    def __init__(self):
        super().__init__()
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

        # Konfigurácia zoomu a mriežky
        self.CONFIG = {
            "MAX_ZOOM_IN": 20.0,
            "MAX_ZOOM_OUT": 0.10,
            "GRID_1_THRESHOLD": 1.0  # Pod túto hodnotu zoomu sa 1x mriežka skryje
        }

        # Body n-gonu
        self.points = []
        self.selected_index = -1
        
        # Transformácia a zobrazenie
        self.pan_offset = QPointF(0, 0)
        self.zoom_level = 1.0
        self.target_width_units = 500.0
        
        # Nastavenia gridu a viditeľnosti
        self.snap_x = False
        self.snap_y = False
        self.show_grid_1 = True
        self.show_grid_5 = True
        self.show_grid_10 = True
        self.show_axes = True
        
        # Safe Region nastavenia
        self.safe_enabled = False
        self.safe_l, self.safe_r = -100.0, 100.0
        self.safe_u, self.safe_d = 100.0, -100.0
        
        # Stav myši
        self.last_mouse_pos = QPointF()
        self.is_panning = False
        self.dragging_point_idx = -1

    def get_scale(self):
        """Vypočíta aktuálnu mierku zohľadňujúcu šírku okna a zoom."""
        return (self.width() / self.target_width_units) * self.zoom_level

    def to_screen(self, world_pt):
        center = self.rect().center()
        scale = self.get_scale()
        screen_x = center.x() + (world_pt.x() + self.pan_offset.x()) * scale
        screen_y = center.y() - (world_pt.y() + self.pan_offset.y()) * scale
        return QPointF(screen_x, screen_y)

    def to_world(self, screen_pt):
        center = self.rect().center()
        scale = self.get_scale()
        world_x = (screen_pt.x() - center.x()) / scale - self.pan_offset.x()
        world_y = (center.y() - screen_pt.y()) / scale - self.pan_offset.y()
        return QPointF(world_x, world_y)

    def apply_snap(self, pt):
        x = round(pt.x()) if self.snap_x else pt.x()
        y = round(pt.y()) if self.snap_y else pt.y()
        return QPointF(x, y)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(25, 25, 25))

        # 1. Vykreslenie mriežky
        self.draw_grid(painter)
        
        # 2. Vykreslenie osí
        if self.show_axes:
            self.draw_axes(painter)

        # 3. Vykreslenie Safe Regionu
        if self.safe_enabled:
            self.draw_safe_region(painter)

        # 4. Vykreslenie N-gonu
        if len(self.points) > 0:
            painter.setPen(QPen(QColor(0, 150, 255), 2))
            for i in range(len(self.points)):
                p1 = self.to_screen(self.points[i])
                p2 = self.to_screen(self.points[(i + 1) % len(self.points)])
                painter.drawLine(p1, p2)

            for i, pt in enumerate(self.points):
                screen_pt = self.to_screen(pt)
                color = QColor(255, 255, 0) if i == self.selected_index else QColor(255, 255, 255)
                painter.setBrush(QBrush(color))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(screen_pt, 4, 4)

    def draw_grid(self, painter):
        top_left = self.to_world(QPointF(0, 0))
        bottom_right = self.to_world(QPointF(self.width(), self.height()))
        
        start_x = int(top_left.x()) - 1
        end_x = int(bottom_right.x()) + 1
        start_y = int(bottom_right.y()) - 1
        end_y = int(top_left.y()) + 1

        # Určenie, či je zoom dostatočný na zobrazenie 1x mriežky
        can_show_grid_1 = self.show_grid_1 and (self.zoom_level > self.CONFIG["GRID_1_THRESHOLD"])

        for x in range(start_x, end_x):
            self.draw_grid_line(painter, x, True, can_show_grid_1)
        for y in range(start_y, end_y):
            self.draw_grid_line(painter, y, False, can_show_grid_1)

    def draw_grid_line(self, painter, val, is_vertical, can_show_grid_1):
        # Logika viditeľnosti mriežky
        is_10 = (val % 10 == 0)
        is_5 = (val % 5 == 0)
        
        if is_10:
            if not self.show_grid_10: return
            painter.setPen(QPen(QColor(80, 80, 80), 1))
        elif is_5:
            if not self.show_grid_5: return
            painter.setPen(QPen(QColor(55, 55, 55), 1))
        else:
            if not can_show_grid_1: return
            painter.setPen(QPen(QColor(40, 40, 40), 1))
            
        p1_w = QPointF(val, self.to_world(QPointF(0, self.height())).y()) if is_vertical else QPointF(self.to_world(QPointF(0, 0)).x(), val)
        p2_w = QPointF(val, self.to_world(QPointF(0, 0)).y()) if is_vertical else QPointF(self.to_world(QPointF(self.width(), 0)).x(), val)
        
        painter.drawLine(self.to_screen(p1_w), self.to_screen(p2_w))

    def draw_axes(self, painter):
        zero = self.to_screen(QPointF(0, 0))
        # X Axis
        painter.setPen(QPen(QColor(200, 50, 50, 180), 2))
        painter.drawLine(0, zero.y(), self.width(), zero.y())
        # Y Axis
        painter.setPen(QPen(QColor(50, 200, 50, 180), 2))
        painter.drawLine(zero.x(), 0, zero.x(), self.height())

    def draw_safe_region(self, painter):
        p1 = self.to_screen(QPointF(self.safe_l, self.safe_u))
        p2 = self.to_screen(QPointF(self.safe_r, self.safe_d))
        rect = QRectF(p1, p2)
        
        painter.setPen(QPen(QColor(255, 165, 0, 150), 2, Qt.DashLine))
        painter.setBrush(QBrush(QColor(255, 165, 0, 20)))
        painter.drawRect(rect)

    def wheelEvent(self, event: QWheelEvent):
        # Zoom centrovaný na kurzor myši
        mouse_before = self.to_world(event.position())
        
        zoom_factor = 1.15 if event.angleDelta().y() > 0 else 1/1.15
        new_zoom = self.zoom_level * zoom_factor
        
        # Aplikácia limitov z CONFIG
        new_zoom = max(self.CONFIG["MAX_ZOOM_OUT"], min(self.CONFIG["MAX_ZOOM_IN"], new_zoom))
        
        # Prepíšeme zoom_level a upravíme pan_offset, aby bod pod myšou zostal na mieste
        self.zoom_level = new_zoom
        mouse_after = self.to_world(event.position())
        self.pan_offset += (mouse_after - mouse_before)
        
        self.update()

    def mousePressEvent(self, event: QMouseEvent):
        world_pos = self.to_world(event.position())
        
        # Panning (Middle button ALEBO Alt + Left Click)
        if event.button() == Qt.MiddleButton or (event.button() == Qt.LeftButton and event.modifiers() & Qt.AltModifier):
            self.is_panning = True
            self.last_mouse_pos = event.position()
            self.setCursor(Qt.ClosedHandCursor)
            return

        # Výber alebo tvorba bodu
        hit_index = -1
        for i, pt in enumerate(self.points):
            dist = (self.to_screen(pt) - event.position()).manhattanLength()
            if dist < 12:
                hit_index = i
                break
        
        if hit_index != -1:
            self.selected_index = hit_index
            self.dragging_point_idx = hit_index
            self.selectionChanged.emit(hit_index)
        else:
            new_pt = self.apply_snap(world_pos)
            self.points.append(new_pt)
            self.selected_index = len(self.points) - 1
            self.pointsChanged.emit(self.points)
            self.selectionChanged.emit(self.selected_index)
        
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.is_panning:
            delta = event.position() - self.last_mouse_pos
            scale = self.get_scale()
            self.pan_offset += QPointF(delta.x() / scale, -delta.y() / scale)
            self.last_mouse_pos = event.position()
            self.update()
        
        elif self.dragging_point_idx != -1:
            world_pos = self.to_world(event.position())
            self.points[self.dragging_point_idx] = self.apply_snap(world_pos)
            self.pointsChanged.emit(self.points)
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.is_panning = False
        self.dragging_point_idx = -1
        self.setCursor(Qt.ArrowCursor)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Delete and self.selected_index != -1:
            self.points.pop(self.selected_index)
            self.selected_index = -1
            self.pointsChanged.emit(self.points)
            self.selectionChanged.emit(-1)
            self.update()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NGon Editor Pro - Advanced")
        self.resize(1200, 800)
        self.setStyleSheet("QMainWindow { background-color: #252525; } QGroupBox { color: #aaa; font-weight: bold; }")

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)

        # Central Area (Tabs)
        self.tabs = QTabWidget()
        self.canvas = NGonCanvas()
        self.tabs.addTab(self.canvas, "Design Canvas")
        
        self.json_view = QTextEdit()
        self.json_view.setReadOnly(True)
        self.json_view.setStyleSheet("background-color: #1e1e1e; color: #9cdcfe; font-family: 'Consolas';")
        self.tabs.addTab(self.json_view, "JavaScript Output")
        layout.addWidget(self.tabs, stretch=4)

        # Control Panel
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        layout.addWidget(right_panel, stretch=1)

        # 1. Visibility Controls
        vis_group = QGroupBox("View Options")
        vis_layout = QVBoxLayout(vis_group)
        self.chk_grid_1 = QCheckBox("Show Grid 1x"); self.chk_grid_1.setChecked(True)
        self.chk_grid_5 = QCheckBox("Show Grid 5x"); self.chk_grid_5.setChecked(True)
        self.chk_grid_10 = QCheckBox("Show Grid 10x"); self.chk_grid_10.setChecked(True)
        self.chk_axes = QCheckBox("Show Axes"); self.chk_axes.setChecked(True)
        for w in [self.chk_grid_1, self.chk_grid_5, self.chk_grid_10, self.chk_axes]: vis_layout.addWidget(w)
        right_layout.addWidget(vis_group)

        # 2. Snapping Controls
        snap_group = QGroupBox("Snapping")
        snap_layout = QGridLayout(snap_group)
        self.check_snap_x = QCheckBox("Snap X")
        self.check_snap_y = QCheckBox("Snap Y")
        self.check_snap_both = QCheckBox("Snap Both")
        snap_layout.addWidget(self.check_snap_x, 0, 0)
        snap_layout.addWidget(self.check_snap_y, 0, 1)
        snap_layout.addWidget(self.check_snap_both, 1, 0, 1, 2)
        right_layout.addWidget(snap_group)

        # 3. Safe Region Controls
        safe_group = QGroupBox("Safe Region")
        safe_layout = QGridLayout(safe_group)
        self.chk_safe_enable = QCheckBox("Enable Safe Region")
        self.spn_l = QDoubleSpinBox(); self.spn_l.setRange(-1000, 1000); self.spn_l.setValue(-100)
        self.spn_r = QDoubleSpinBox(); self.spn_r.setRange(-1000, 1000); self.spn_r.setValue(100)
        self.spn_u = QDoubleSpinBox(); self.spn_u.setRange(-1000, 1000); self.spn_u.setValue(100)
        self.spn_d = QDoubleSpinBox(); self.spn_d.setRange(-1000, 1000); self.spn_d.setValue(-100)
        
        safe_layout.addWidget(self.chk_safe_enable, 0, 0, 1, 2)
        safe_layout.addWidget(QLabel("L:"), 1, 0); safe_layout.addWidget(self.spn_l, 1, 1)
        safe_layout.addWidget(QLabel("R:"), 2, 0); safe_layout.addWidget(self.spn_r, 2, 1)
        safe_layout.addWidget(QLabel("U:"), 3, 0); safe_layout.addWidget(self.spn_u, 3, 1)
        safe_layout.addWidget(QLabel("D:"), 4, 0); safe_layout.addWidget(self.spn_d, 4, 1)
        right_layout.addWidget(safe_group)

        # 4. Outliner
        right_layout.addWidget(QLabel("Points Outliner:"))
        self.outliner = QListWidget()
        right_layout.addWidget(self.outliner)

        self.setup_connections()
        self.update_ui([])

    def setup_connections(self):
        self.canvas.pointsChanged.connect(self.update_ui)
        self.canvas.selectionChanged.connect(self.sync_selection_to_ui)
        self.outliner.currentRowChanged.connect(self.sync_selection_to_canvas)
        
        # Grid/Vis connects
        self.chk_grid_1.stateChanged.connect(self.update_canvas_settings)
        self.chk_grid_5.stateChanged.connect(self.update_canvas_settings)
        self.chk_grid_10.stateChanged.connect(self.update_canvas_settings)
        self.chk_axes.stateChanged.connect(self.update_canvas_settings)
        
        # Snap connects
        self.check_snap_x.stateChanged.connect(self.update_canvas_settings)
        self.check_snap_y.stateChanged.connect(self.update_canvas_settings)
        self.check_snap_both.stateChanged.connect(self.toggle_both_snap)

        # Safe region connects
        self.chk_safe_enable.stateChanged.connect(self.update_canvas_settings)
        for s in [self.spn_l, self.spn_r, self.spn_u, self.spn_d]:
            s.valueChanged.connect(self.update_canvas_settings)

    def update_canvas_settings(self):
        self.canvas.show_grid_1 = self.chk_grid_1.isChecked()
        self.canvas.show_grid_5 = self.chk_grid_5.isChecked()
        self.canvas.show_grid_10 = self.chk_grid_10.isChecked()
        self.canvas.show_axes = self.chk_axes.isChecked()
        
        self.canvas.snap_x = self.check_snap_x.isChecked()
        self.canvas.snap_y = self.check_snap_y.isChecked()
        
        self.canvas.safe_enabled = self.chk_safe_enable.isChecked()
        self.canvas.safe_l = self.spn_l.value()
        self.canvas.safe_r = self.spn_r.value()
        self.canvas.safe_u = self.spn_u.value()
        self.canvas.safe_d = self.spn_d.value()
        self.canvas.update()

    def toggle_both_snap(self, state):
        is_checked = (state == Qt.Checked.value)
        self.check_snap_x.setChecked(is_checked)
        self.check_snap_y.setChecked(is_checked)
        self.update_canvas_settings()

    def update_ui(self, points):
        self.outliner.blockSignals(True)
        self.outliner.clear()
        json_data = []
        for i, pt in enumerate(points):
            self.outliner.addItem(f"P{i}: [{pt.x():.1f}, {pt.y():.1f}]")
            json_data.append({"x": round(pt.x(), 2), "y": round(pt.y(), 2)})
        
        if self.canvas.selected_index != -1:
            self.outliner.setCurrentRow(self.canvas.selected_index)
        self.outliner.blockSignals(False)

        js_code = "const ngon = " + json.dumps(json_data, indent=4) + ";"
        self.json_view.setPlainText(js_code)

    def sync_selection_to_ui(self, index):
        self.outliner.blockSignals(True)
        self.outliner.setCurrentRow(index)
        self.outliner.blockSignals(False)

    def sync_selection_to_canvas(self, index):
        self.canvas.selected_index = index
        self.canvas.update()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())