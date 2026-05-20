import sys
import json
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTabWidget, QListWidget, QCheckBox, QLabel, QGroupBox, 
    QTextEdit, QFrame
)
from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QKeyEvent, QMouseEvent

class NGonCanvas(QWidget):
    # Signál vyslaný pri zmene bodov pre update outlineru a JSONu
    pointsChanged = Signal(list)
    selectionChanged = Signal(int)

    def __init__(self):
        super().__init__()
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

        # Body n-gonu: list objektov QPointF (v herných súradniciach)
        self.points = []
        self.selected_index = -1
        
        # Transformácia a zobrazenie
        self.pan_offset = QPointF(0, 0)
        self.unit_size = 1.0  # Výpočet dynamicky podľa šírky okna
        self.target_width_units = 500.0
        
        # Nastavenia gridu
        self.snap_x = False
        self.snap_y = False
        
        # Stav myši
        self.last_mouse_pos = QPointF()
        self.is_panning = False
        self.dragging_point_idx = -1

    def to_screen(self, world_pt):
        """Konvertuje herné súradnice [x, y] na pixely obrazovky."""
        center = self.rect().center()
        scale = self.width() / self.target_width_units
        screen_x = center.x() + (world_pt.x() + self.pan_offset.x()) * scale
        screen_y = center.y() - (world_pt.y() + self.pan_offset.y()) * scale
        return QPointF(screen_x, screen_y)

    def to_world(self, screen_pt):
        """Konvertuje pixely obrazovky na herné súradnice [x, y]."""
        center = self.rect().center()
        scale = self.width() / self.target_width_units
        world_x = (screen_pt.x() - center.x()) / scale - self.pan_offset.x()
        world_y = (center.y() - screen_pt.y()) / scale - self.pan_offset.y()
        return QPointF(world_x, world_y)

    def apply_snap(self, pt):
        """Aplikuje mriežkový snap na bod."""
        x = round(pt.x()) if self.snap_x else pt.x()
        y = round(pt.y()) if self.snap_y else pt.y()
        return QPointF(x, y)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(30, 30, 30))  # Tmavé pozadie

        scale = self.width() / self.target_width_units
        
        # Vykreslenie mriežky
        self.draw_grid(painter, scale)
        
        # Vykreslenie osí
        self.draw_axes(painter)

        # Vykreslenie N-gonu
        if len(self.points) > 0:
            # Čiary
            painter.setPen(QPen(QColor(0, 150, 255), 2))
            for i in range(len(self.points)):
                p1 = self.to_screen(self.points[i])
                p2 = self.to_screen(self.points[(i + 1) % len(self.points)])
                painter.drawLine(p1, p2)

            # Body
            for i, pt in enumerate(self.points):
                screen_pt = self.to_screen(pt)
                color = QColor(255, 255, 0) if i == self.selected_index else QColor(255, 255, 255)
                painter.setBrush(QBrush(color))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(screen_pt, 4, 4)

    def draw_grid(self, painter, scale):
        # Dynamický výpočet viditeľného rozsahu
        top_left = self.to_world(QPointF(0, 0))
        bottom_right = self.to_world(QPointF(self.width(), self.height()))
        
        start_x = int(top_left.x()) - 1
        end_x = int(bottom_right.x()) + 1
        start_y = int(bottom_right.y()) - 1
        end_y = int(top_left.y()) + 1

        # Vykresľovanie čiar mriežky
        for x in range(start_x, end_x):
            self.draw_grid_line(painter, x, True)
        for y in range(start_y, end_y):
            self.draw_grid_line(painter, y, False)

    def draw_grid_line(self, painter, val, is_vertical):
        if val == 0: return # Osy kreslíme separátne
        
        if val % 10 == 0:
            painter.setPen(QPen(QColor(80, 80, 80), 1))
        elif val % 5 == 0:
            painter.setPen(QPen(QColor(60, 60, 60), 1))
        else:
            painter.setPen(QPen(QColor(45, 45, 45), 1))
            
        if is_vertical:
            p1 = self.to_screen(QPointF(val, self.to_world(QPointF(0, self.height())).y()))
            p2 = self.to_screen(QPointF(val, self.to_world(QPointF(0, 0)).y()))
        else:
            p1 = self.to_screen(QPointF(self.to_world(QPointF(0, 0)).x(), val))
            p2 = self.to_screen(QPointF(self.to_world(QPointF(self.width(), 0)).x(), val))
        
        painter.drawLine(p1, p2)

    def draw_axes(self, painter):
        # Os X (Červená)
        painter.setPen(QPen(QColor(255, 50, 50), 2))
        y_zero = self.to_screen(QPointF(0, 0)).y()
        painter.drawLine(0, y_zero, self.width(), y_zero)
        
        # Os Y (Zelená)
        painter.setPen(QPen(QColor(50, 255, 50), 2))
        x_zero = self.to_screen(QPointF(0, 0)).x()
        painter.drawLine(x_zero, 0, x_zero, self.height())

    def mousePressEvent(self, event: QMouseEvent):
        world_pos = self.to_world(event.position())
        
        if event.button() == Qt.MiddleButton:
            self.is_panning = True
            self.last_mouse_pos = event.position()
            return

        # Skús vybrať existujúci bod
        hit_index = -1
        for i, pt in enumerate(self.points):
            screen_pt = self.to_screen(pt)
            dist = (screen_pt - event.position()).manhattanLength()
            if dist < 15:
                hit_index = i
                break
        
        if hit_index != -1:
            self.selected_index = hit_index
            self.dragging_point_idx = hit_index
            self.selectionChanged.emit(hit_index)
        else:
            # Vytvor nový bod
            new_pt = self.apply_snap(world_pos)
            self.points.append(new_pt)
            self.selected_index = len(self.points) - 1
            self.pointsChanged.emit(self.points)
            self.selectionChanged.emit(self.selected_index)
        
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.is_panning:
            delta = event.position() - self.last_mouse_pos
            scale = self.target_width_units / self.width()
            self.pan_offset += QPointF(delta.x() * scale, -delta.y() * scale)
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
        self.setWindowTitle("NGon Editor Pro")
        self.resize(1000, 700)

        # Hlavný layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)

        # Tabuľka s Canvasom a JSONom
        self.tabs = QTabWidget()
        self.canvas = NGonCanvas()
        self.tabs.addTab(self.canvas, "Canvas View")
        
        self.json_view = QTextEdit()
        self.json_view.setReadOnly(True)
        self.json_view.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4; font-family: 'Consolas';")
        self.tabs.addTab(self.json_view, "JavaScript / JSON")
        
        layout.addWidget(self.tabs, stretch=4)

        # Pravý panel (Controls & Outliner)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        layout.addWidget(right_panel, stretch=1)

        # Nastavenia Snapu
        snap_group = QGroupBox("Grid Snapping")
        snap_layout = QVBoxLayout(snap_group)
        self.check_snap_x = QCheckBox("Snap X")
        self.check_snap_y = QCheckBox("Snap Y")
        self.check_snap_both = QCheckBox("Snap Both")
        
        snap_layout.addWidget(self.check_snap_x)
        snap_layout.addWidget(self.check_snap_y)
        snap_layout.addWidget(self.check_snap_both)
        right_layout.addWidget(snap_group)

        # Outliner
        right_layout.addWidget(QLabel("Points Outliner:"))
        self.outliner = QListWidget()
        right_layout.addWidget(self.outliner)

        # Prepojenie signálov
        self.canvas.pointsChanged.connect(self.update_ui)
        self.canvas.selectionChanged.connect(self.sync_selection_to_ui)
        self.outliner.currentRowChanged.connect(self.sync_selection_to_canvas)
        
        self.check_snap_x.stateChanged.connect(self.update_snap_settings)
        self.check_snap_y.stateChanged.connect(self.update_snap_settings)
        self.check_snap_both.stateChanged.connect(self.toggle_both_snap)

        self.update_ui([])

    def update_snap_settings(self):
        self.canvas.snap_x = self.check_snap_x.isChecked()
        self.canvas.snap_y = self.check_snap_y.isChecked()
        
    def toggle_both_snap(self, state):
        is_checked = (state == Qt.Checked.value)
        self.check_snap_x.setChecked(is_checked)
        self.check_snap_y.setChecked(is_checked)
        self.update_snap_settings()

    def update_ui(self, points):
        # Aktualizácia Outlineru
        self.outliner.blockSignals(True)
        self.outliner.clear()
        json_data = []
        for i, pt in enumerate(points):
            self.outliner.addItem(f"Point {i}: [{pt.x():.1f}, {pt.y():.1f}]")
            json_data.append({"x": round(pt.x(), 2), "y": round(pt.y(), 2)})
        
        if self.canvas.selected_index != -1:
            self.outliner.setCurrentRow(self.canvas.selected_index)
        self.outliner.blockSignals(False)

        # Aktualizácia JSON view
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