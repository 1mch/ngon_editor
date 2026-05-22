import sys
import json
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTabWidget, QListWidget, QCheckBox, QLabel, QGroupBox, 
    QTextEdit, QDoubleSpinBox, QGridLayout
)
from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PySide6.QtGui import QLinearGradient, QPainter, QColor, QPen, QBrush, QKeyEvent, QMouseEvent, QWheelEvent

class NGonCanvas(QWidget):
    pointsChanged = Signal(list)
    selectionChanged = Signal(int)

    def __init__(self):
        super().__init__()
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

        # Konfigurácia priblíženia (zoomu) a prahu pre slabšiu mriežku
        self.CONFIG = {
            "MAX_ZOOM_IN": 15.0,
            "MAX_ZOOM_OUT": 0.30,
            "GRID_SUB_THRESHOLD": 2.0  # Pod tento zoom sa slabšia (1-jednotková) mriežka skryje
        }

        # Body n-uholníka
        self.points = []
        self.selected_index = -1
        
        # Transformácia a posun zobrazenia
        self.pan_offset = QPointF(0, 0)
        self.zoom_level = 1.0
        self.target_width_units = 500.0
        
        # Nastavenia prichytávania a zobrazenia prkov
        self.snap_x = False
        self.snap_y = False
        self.show_grid = True  # Jeden hlavný vypínač pre mriežku
        self.show_axes = True
        
        # Nastavenie bezpečnej zóny (Safe Region)
        self.safe_enabled = False
        self.safe_l, self.safe_r = -100.0, 100.0
        self.safe_u, self.safe_d = 100.0, -100.0
        
        # Stavové premenné pre interakciu s myšou
        self.last_mouse_pos = QPointF()
        self.is_panning = False
        self.dragging_point_idx = -1
        
        self.hovered_segment_idx = -1
        self.selected_segment_idx = -1
        self.dragging_segment_idx = -1
        self.last_world_pos = QPointF()
        
        self.hovered_point_idx = -1

    def get_scale(self):
        """Vypočíta mierku na základe aktuálnej šírky okna a zoomu."""
        return (self.width() / self.target_width_units) * self.zoom_level

    def to_screen(self, world_pt):
        """Prepočíta súradnice zo sveta na obrazovku."""
        center = self.rect().center()
        scale = self.get_scale()
        screen_x = center.x() + (world_pt.x() + self.pan_offset.x()) * scale
        screen_y = center.y() - (world_pt.y() + self.pan_offset.y()) * scale
        return QPointF(screen_x, screen_y)

    def to_world(self, screen_pt):
        """Prepočíta súradnice z obrazovky do sveta."""
        center = self.rect().center()
        scale = self.get_scale()
        world_x = (screen_pt.x() - center.x()) / scale - self.pan_offset.x()
        world_y = (center.y() - screen_pt.y()) / scale - self.pan_offset.y()
        return QPointF(world_x, world_y)

    def apply_snap(self, pt):
        """Aplikuje prichytávanie bodu k celočíselnej mriežke."""
        x = round(pt.x()) if self.snap_x else pt.x()
        y = round(pt.y()) if self.snap_y else pt.y()
        return QPointF(x, y)

    def dist_to_segment(self, p, a, b):
        """Vráti najkratšiu vzdialenosť bodu P od úsečky AB v pixeloch."""
        pa = p - a
        ba = b - a
        dot = QPointF.dotProduct(pa, ba)
        mag = QPointF.dotProduct(ba, ba)
        t = max(0.0, min(1.0, dot / mag if mag != 0 else 0.0))
        return (pa - ba * t).manhattanLength()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(25, 25, 25))

        # 1. Vykreslenie mriežky (len ak je povolená)
        if self.show_grid:
            self.draw_grid(painter)
        
        # 2. Vykreslenie osí
        if self.show_axes:
            self.draw_axes(painter)

        # 3. Vykreslenie bezpečnej zóny
        if self.safe_enabled:
            self.draw_safe_region(painter)

        if len(self.points) == 0:
            return

        # 4. Vykreslenie čiar (segmentov)
        for i in range(len(self.points)):
            p1 = self.to_screen(self.points[i])
            p2 = self.to_screen(self.points[(i + 1) % len(self.points)])
            
            is_closing_segment = (i == len(self.points) - 1 and len(self.points) > 1)
            
            if i == self.selected_segment_idx:
                painter.setPen(QPen(QColor(255, 140, 0), 4))  # Oranžový výber
            elif i == self.hovered_segment_idx:
                painter.setPen(QPen(QColor(255, 255, 0), 3))  # Žltý hover
            elif is_closing_segment:
                # Farebný prechod pre uzatváraciu čiaru
                gradient = QLinearGradient(p1, p2)
                gradient.setColorAt(0.0, QColor(0, 150, 255))
                gradient.setColorAt(0.8, QColor(200, 50, 50))
                gradient.setColorAt(1.0, QColor(255, 0, 0))
                painter.setPen(QPen(QBrush(gradient), 2))
            else:
                painter.setPen(QPen(QColor(0, 150, 255), 2))  # Bežná modrá čiara
            
            painter.drawLine(p1, p2)

        # 5. Vykreslenie bodov (vrcholov) nad čiarami
        for i, pt in enumerate(self.points):
            screen_pt = self.to_screen(pt)
            
            if i == self.selected_index:
                color = QColor(255, 140, 0)  # Oranžový vybratý bod
                size = 5
            elif i == self.hovered_point_idx:
                color = QColor(255, 255, 0)  # Žltý zameraný bod
                size = 5
            else:
                color = QColor(255, 255, 255)  # Biely predvolený bod
                size = 4
                
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(QColor(0, 0, 0), 1) if size > 4 else Qt.NoPen)
            painter.drawEllipse(screen_pt, size, size)

    def draw_grid(self, painter):
        top_left = self.to_world(QPointF(0, 0))
        bottom_right = self.to_world(QPointF(self.width(), self.height()))
        
        start_x = int(top_left.x()) - 1
        end_x = int(bottom_right.x()) + 1
        start_y = int(bottom_right.y()) - 1
        end_y = int(top_left.y()) + 1

        # Rozhodnutie, či priblíženie povoľuje vykresliť aj jemnú 1-jednotkovú mriežku
        can_show_sub_grid = self.zoom_level > self.CONFIG["GRID_SUB_THRESHOLD"]

        for x in range(start_x, end_x):
            self.draw_grid_line(painter, x, True, can_show_sub_grid)
        for y in range(start_y, end_y):
            self.draw_grid_line(painter, y, False, can_show_sub_grid)

    def draw_grid_line(self, painter, val, is_vertical, can_show_sub_grid):
        is_10 = (val % 10 == 0)
        
        if is_10:
            # Hlavná mriežka každých 10 jednotiek (výraznejšia sivá)
            painter.setPen(QPen(QColor(45, 45, 45), 1))
        else:
            # Ak je to 1-jednotková mriežka a nemáme dostatočný zoom, nevykreslíme ju
            if not can_show_sub_grid:
                return
            # Slabšia mriežka každú 1 jednotku (veľmi jemná sivá)
            painter.setPen(QPen(QColor(30, 30, 30), 1))
            
        p1_w = QPointF(val, self.to_world(QPointF(0, self.height())).y()) if is_vertical else QPointF(self.to_world(QPointF(0, 0)).x(), val)
        p2_w = QPointF(val, self.to_world(QPointF(0, 0)).y()) if is_vertical else QPointF(self.to_world(QPointF(self.width(), 0)).x(), val)
        
        painter.drawLine(self.to_screen(p1_w), self.to_screen(p2_w))

    def draw_axes(self, painter):
        zero = self.to_screen(QPointF(0, 0))
        # X os (Červená)
        painter.setPen(QPen(QColor(200, 50, 50, 180), 2))
        painter.drawLine(0, zero.y(), self.width(), zero.y())
        # Y os (Zelená)
        painter.setPen(QPen(QColor(50, 200, 50, 180), 2))
        painter.drawLine(zero.x(), 0, zero.x(), self.height())

    def draw_safe_region(self, painter):
        p1 = self.to_screen(QPointF(self.safe_l, self.safe_u))
        p2 = self.to_screen(QPointF(self.safe_r, self.safe_d))
        rect = QRectF(p1, p2)
        
        painter.setPen(QPen(QColor(255, 165, 0, 150), 1, Qt.SolidLine))
        painter.setBrush(QBrush(QColor(195, 165, 0, 5)))
        painter.drawRect(rect)

    def wheelEvent(self, event: QWheelEvent):
        # Zoom centrovaný na kurzor myši
        mouse_before = self.to_world(event.position())
        zoom_factor = 1.15 if event.angleDelta().y() > 0 else 1/1.15
        new_zoom = self.zoom_level * zoom_factor
        new_zoom = max(self.CONFIG["MAX_ZOOM_OUT"], min(self.CONFIG["MAX_ZOOM_IN"], new_zoom))
        
        self.zoom_level = new_zoom
        mouse_after = self.to_world(event.position())
        self.pan_offset += (mouse_after - mouse_before)
        self.update()

    def mousePressEvent(self, event: QMouseEvent):
        world_pos = self.to_world(event.position())
        self.last_world_pos = world_pos
        
        # Posúvanie pohľadu (Stredné tlačidlo ALEBO Alt + Ľavé tlačidlo)
        if event.button() == Qt.MiddleButton or (event.button() == Qt.LeftButton and event.modifiers() & Qt.AltModifier):
            self.is_panning = True
            self.last_mouse_pos = event.position()
            self.setCursor(Qt.ClosedHandCursor)
            return

        # 1. Výber existujúceho bodu
        hit_index = -1
        for i, pt in enumerate(self.points):
            dist = (self.to_screen(pt) - event.position()).manhattanLength()
            if dist < 12:
                hit_index = i
                break
        
        if hit_index != -1:
            self.selected_index = hit_index
            self.dragging_point_idx = hit_index
            self.selected_segment_idx = -1
            self.selectionChanged.emit(hit_index)
            self.update()
            return

        # 2. Kliknutie na segment (čiara)
        if self.hovered_segment_idx != -1:
            if event.modifiers() & Qt.ControlModifier:
                # Vloženie nového bodu do vybratej čiary
                new_pt = self.apply_snap(world_pos)
                self.points.insert(self.hovered_segment_idx + 1, new_pt)
                self.selected_index = self.hovered_segment_idx + 1
                self.selected_segment_idx = -1
                self.pointsChanged.emit(self.points)
                self.selectionChanged.emit(self.selected_index)
            else:
                # Označenie segmentu na posunutie celej hrany
                self.selected_segment_idx = self.hovered_segment_idx
                self.dragging_segment_idx = self.hovered_segment_idx
                self.selected_index = -1
                self.selectionChanged.emit(-1)
            self.update()
            return

        # 3. Pridanie nového bodu na koniec (len s Ctrl)
        if event.modifiers() & Qt.ControlModifier:
            new_pt = self.apply_snap(world_pos)
            self.points.append(new_pt)
            self.selected_index = len(self.points) - 1
            self.selected_segment_idx = -1
            self.pointsChanged.emit(self.points)
            self.selectionChanged.emit(self.selected_index)
        else:
            self.selected_index = -1
            self.selected_segment_idx = -1
            self.selectionChanged.emit(-1)
        
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        world_pos = self.to_world(event.position())
        
        if self.is_panning:
            delta = event.position() - self.last_mouse_pos
            scale = self.get_scale()
            self.pan_offset += QPointF(delta.x() / scale, -delta.y() / scale)
            self.last_mouse_pos = event.position()
            self.update()
            return
        
        if self.dragging_point_idx != -1:
            self.points[self.dragging_point_idx] = self.apply_snap(world_pos)
            self.pointsChanged.emit(self.points)
            self.update()
            return

        if self.dragging_segment_idx != -1:
            delta = world_pos - self.last_world_pos
            idx1 = self.dragging_segment_idx
            idx2 = (idx1 + 1) % len(self.points)
            
            self.points[idx1] += delta
            self.points[idx2] += delta
            
            self.points[idx1] = self.apply_snap(self.points[idx1])
            self.points[idx2] = self.apply_snap(self.points[idx2])
            
            self.last_world_pos = world_pos
            self.pointsChanged.emit(self.points)
            self.update()
            return

        old_h_point = self.hovered_point_idx
        old_h_segment = self.hovered_segment_idx
        
        self.hovered_point_idx = -1
        self.hovered_segment_idx = -1
        
        # Kontrola prechodu myši nad bodmi
        for i, pt in enumerate(self.points):
            dist = (self.to_screen(pt) - event.position()).manhattanLength()
            if dist < 12:
                self.hovered_point_idx = i
                break
        
        # Kontrola prechodu myši nad hranami
        if self.hovered_point_idx == -1 and len(self.points) >= 2:
            mouse_px = event.position()
            for i in range(len(self.points)):
                p1 = self.to_screen(self.points[i])
                p2 = self.to_screen(self.points[(i + 1) % len(self.points)])
                if self.dist_to_segment(mouse_px, p1, p2) < 8:
                    self.hovered_segment_idx = i
                    break
        
        if old_h_point != self.hovered_point_idx or old_h_segment != self.hovered_segment_idx:
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.is_panning = False
        self.dragging_point_idx = -1
        self.dragging_segment_idx = -1
        self.setCursor(Qt.ArrowCursor)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Delete and self.selected_index != -1:
            self.delete_selected_point()

    def delete_selected_point(self):
        if self.selected_index != -1 and 0 <= self.selected_index < len(self.points):
            self.points.pop(self.selected_index)
            self.selected_index = -1
            self.pointsChanged.emit(self.points)
            self.selectionChanged.emit(-1)
            self.update()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NGon Editor Pro - Pokročilý editor")
        self.resize(1200, 800)
        self.setStyleSheet("QMainWindow { background-color: #252525; } QGroupBox { color: #aaa; font-weight: bold; }")

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)

        # Hlavná časť so záložkami
        self.tabs = QTabWidget()
        self.canvas = NGonCanvas()
        self.tabs.addTab(self.canvas, "Návrhové plátno")
        
        self.json_view = QTextEdit()
        self.json_view.setReadOnly(True)
        self.json_view.setStyleSheet("background-color: #1e1e1e; color: #9cdcfe; font-family: 'Consolas';")
        self.tabs.addTab(self.json_view, "JavaScript výstup")
        layout.addWidget(self.tabs, stretch=4)

        # Bočný ovládací panel
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        layout.addWidget(right_panel, stretch=1)

        # 1. Možnosti zobrazenia (Mriežka a osi)
        vis_group = QGroupBox("Možnosti zobrazenia")
        vis_layout = QVBoxLayout(vis_group)
        
        # Jediný globálny prepínač pre mriežku
        self.chk_grid_master = QCheckBox("Zobraziť mriežku")
        self.chk_grid_master.setChecked(True)
        vis_layout.addWidget(self.chk_grid_master)
        
        self.chk_axes = QCheckBox("Zobraziť hlavné osi")
        self.chk_axes.setChecked(True)
        vis_layout.addWidget(self.chk_axes)
            
        right_layout.addWidget(vis_group)

        # 2. Nastavenia prichytávania
        snap_group = QGroupBox("Prichytávanie (Snap)")
        snap_layout = QGridLayout(snap_group)
        self.check_snap_x = QCheckBox("Prichytiť na X")
        self.check_snap_y = QCheckBox("Prichytiť na Y")
        self.check_snap_both = QCheckBox("Prichytiť na obe osi")
        snap_layout.addWidget(self.check_snap_x, 0, 0)
        snap_layout.addWidget(self.check_snap_y, 0, 1)
        snap_layout.addWidget(self.check_snap_both, 1, 0, 1, 2)
        right_layout.addWidget(snap_group)

        # 3. Nastavenie bezpečnej zóny
        safe_group = QGroupBox("Bezpečná zóna")
        safe_layout = QGridLayout(safe_group)
        self.chk_safe_enable = QCheckBox("Povoliť bezpečnú zónu")
        self.spn_l = QDoubleSpinBox(); self.spn_l.setRange(-1000, 1000); self.spn_l.setValue(-100)
        self.spn_r = QDoubleSpinBox(); self.spn_r.setRange(-1000, 1000); self.spn_r.setValue(100)
        self.spn_u = QDoubleSpinBox(); self.spn_u.setRange(-1000, 1000); self.spn_u.setValue(100)
        self.spn_d = QDoubleSpinBox(); self.spn_d.setRange(-1000, 1000); self.spn_d.setValue(-100)
        
        safe_layout.addWidget(self.chk_safe_enable, 0, 0, 1, 2)
        safe_layout.addWidget(QLabel("Ľavá (L):"), 1, 0); safe_layout.addWidget(self.spn_l, 1, 1)
        safe_layout.addWidget(QLabel("Pravá (R):"), 2, 0); safe_layout.addWidget(self.spn_r, 2, 1)
        safe_layout.addWidget(QLabel("Horná (U):"), 3, 0); safe_layout.addWidget(self.spn_u, 3, 1)
        safe_layout.addWidget(QLabel("Dolná (D):"), 4, 0); safe_layout.addWidget(self.spn_d, 4, 1)
        right_layout.addWidget(safe_group)

        # 4. Zoznam vrcholov (Outliner)
        right_layout.addWidget(QLabel("Zoznam bodov (Outliner):"))
        self.outliner = QListWidget()
        # Inštalácia event filtra na zachytávanie klávesov priamo v Outlineri
        self.outliner.installEventFilter(self)
        right_layout.addWidget(self.outliner)

        self.setup_connections()
        self.update_ui([])
        self.update_canvas_settings() # Inicializácia stavu zaškrtávadiel

    def setup_connections(self):
        self.canvas.pointsChanged.connect(self.update_ui)
        self.canvas.selectionChanged.connect(self.sync_selection_to_ui)
        self.outliner.currentRowChanged.connect(self.sync_selection_to_canvas)
        
        # Prepojenie zobrazenia
        self.chk_grid_master.stateChanged.connect(self.update_canvas_settings)
        self.chk_axes.stateChanged.connect(self.update_canvas_settings)
        
        # Prepojenie prichytávania
        self.check_snap_x.stateChanged.connect(self.update_canvas_settings)
        self.check_snap_y.stateChanged.connect(self.update_canvas_settings)
        self.check_snap_both.stateChanged.connect(self.toggle_both_snap)

        # Prepojenie bezpečnej zóny
        self.chk_safe_enable.stateChanged.connect(self.update_canvas_settings)
        for s in [self.spn_l, self.spn_r, self.spn_u, self.spn_d]:
            s.valueChanged.connect(self.update_canvas_settings)

    def eventFilter(self, watched, event):
        """Zachytí stlačenie klávesu Delete, ak má focus Outliner."""
        if watched == self.outliner and event.type() == QKeyEvent.Type.KeyPress:
            if event.key() == Qt.Key_Delete:
                self.canvas.delete_selected_point()
                return True
        return super().eventFilter(watched, event)

    def update_canvas_settings(self):
        # Načítanie stavu hlavného prepínača mriežky
        self.canvas.show_grid = self.chk_grid_master.isChecked()
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
        # Správne ošetrenie CheckState pre verziu PySide6
        is_checked = (state == Qt.CheckState.Checked.value or state == 2)
        self.check_snap_x.setChecked(is_checked)
        self.check_snap_y.setChecked(is_checked)
        self.update_canvas_settings()

    def update_ui(self, points):
        self.outliner.blockSignals(True)
        self.outliner.clear()
        json_data = []
        for i, pt in enumerate(points):
            self.outliner.addItem(f"Bod {i}: [{pt.x():.1f}, {pt.y():.1f}]")
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
        self.canvas.selected_segment_idx = -1  # Výber v outlineri zruší označenie hrany (identické s kliknutím na bod)
        self.canvas.update()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())