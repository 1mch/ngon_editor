import sys
import json
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTabWidget, QListWidget, QCheckBox, QLabel, QGroupBox, 
    QTextEdit, QDoubleSpinBox, QGridLayout, QDialog, QFormLayout, QDialogButtonBox,
    QPushButton  # Pridané tlačidlo pre Náhľad
)
from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PySide6.QtGui import QLinearGradient, QPainter, QColor, QPen, QBrush, QKeyEvent, QMouseEvent, QWheelEvent, QPolygonF

from file_manager import save_ngon_to_js, import_ngon_from_js

class CoordinateDialog(QDialog):
    def __init__(self, x, y, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Upraviť súradnice bodu")
        self.setMinimumWidth(250)
        layout = QFormLayout(self)

        # Polia pre zadávanie číselných hodnôt
        self.spn_x = QDoubleSpinBox()
        self.spn_x.setRange(-10000, 10000)
        self.spn_x.setValue(x)
        self.spn_x.setDecimals(2)
        
        self.spn_y = QDoubleSpinBox()
        self.spn_y.setRange(-10000, 10000)
        self.spn_y.setValue(y)
        self.spn_y.setDecimals(2)

        layout.addRow("Súradnica X:", self.spn_x)
        layout.addRow("Súradnica Y:", self.spn_y)

        # Štandardné tlačidlá OK a Zrušiť
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addRow(self.buttons)

    def get_values(self):
        """Vráti nastavené hodnoty X a Y."""
        return self.spn_x.value(), self.spn_y.value()

class NGonCanvas(QWidget):
    pointsChanged = Signal(list)
    selectionChanged = Signal(int)
    pointDoubleClicked = Signal(int)

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
        self.show_coords = False
        
        # Nastavenie bezpečnej zóny (Safe Region)
        self.safe_enabled = False
        self.safe_l, self.safe_r = -100.0, 100.0
        self.safe_u, self.safe_d = -100.0, 100.0
        
        # Stavové premenné pre interakciu s myšou
        self.last_mouse_pos = QPointF()
        self.is_panning = False
        self.dragging_point_idx = -1
        
        self.dragging_all = False
        
        self.hovered_segment_idx = -1
        self.selected_segment_idx = -1
        self.dragging_segment_idx = -1
        self.last_world_pos = QPointF()
        
        self.hovered_point_idx = -1
        
        self.preview_mode = False

    def get_scale(self):
        """Vypočíta mierku na základe aktuálnej šírky okna a zoomu."""
        return (self.width() / self.target_width_units) * self.zoom_level

    def to_screen(self, world_pt):
        """Prepočíta súradnice zo sveta na obrazovku."""
        center = self.rect().center()
        scale = self.get_scale()
        screen_x = center.x() + (world_pt.x() + self.pan_offset.x()) * scale
        screen_y = center.y() + (world_pt.y() + self.pan_offset.y()) * scale
        return QPointF(screen_x, screen_y)

    def to_world(self, screen_pt):
        """Prepočíta súradnice z obrazovky do sveta."""
        center = self.rect().center()
        scale = self.get_scale()
        world_x = (screen_pt.x() - center.x()) / scale - self.pan_offset.x()
        world_y = (screen_pt.y() - center.y()) / scale - self.pan_offset.y()
        return QPointF(world_x, world_y)

    def apply_snap(self, pt):
        """Aplikuje prichytávanie bodu podľa aktuálne viditeľnej mriežky."""
        # Zistíme, či je zobrazená len 10-ková mriežka (rovnaká podmienka ako v draw_grid)
        can_show_sub_grid = self.zoom_level > self.CONFIG["GRID_SUB_THRESHOLD"]
        
        # Ak vidíme jemnú mriežku, krok je 1. Ak vidíme len hlavnú, krok je 10.
        step = 1.0 if can_show_sub_grid else 10.0

        # Výpočet súradníc vydelením krokom, zaokrúhlením a vynásobením späť
        x = round(pt.x() / step) * step if self.snap_x else pt.x()
        y = round(pt.y() / step) * step if self.snap_y else pt.y()
        
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

        if self.preview_mode:
            if len(self.points) > 2:
                # Vykreslenie vyplneného n-uholníka bez okrajov a bodov
                screen_points = [self.to_screen(p) for p in self.points]
                poly = QPolygonF(screen_points)
                painter.setBrush(QBrush(QColor(0, 150, 255, 180))) # Jemná modrá výplň
                painter.setPen(Qt.NoPen)
                painter.drawPolygon(poly)
            return # V režime náhľadu preskakujeme kreslenie mriežky a bodov

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
            
            is_closing_segment = (i == len(self.points) - 1 and len(self.points) > 2)
            
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
        
        if self.show_coords:
            painter.setFont(self.font()) # Nastavenie písma
            for i, pt in enumerate(self.points):
                screen_pt = self.to_screen(pt)
                # Formátovanie textu (súradnice vo svete)
                text = f"{pt.x():.1f}, {pt.y():.1f}"
                
                # Výpočet veľkosti obdĺžnika podľa textu
                metrics = painter.fontMetrics()
                rect = metrics.boundingRect(text)
                rect.adjust(-2, -2, 2, 2) # Malý padding
                rect.translate(screen_pt.x() + 10, screen_pt.y() - 10) # Posun vedľa bodu

                # Rozhodnutie o farbách na základe výberu
                is_selected = (i == self.selected_index)
                bg_color = QColor(255, 140, 0) if is_selected else QColor(255, 255, 255, 220)
                text_color = QColor(255, 255, 255) if is_selected else QColor(0, 0, 0)

                # Kreslenie pozadia štítku
                painter.setPen(QPen(QColor(0, 0, 0), 1))
                painter.setBrush(QBrush(bg_color))
                painter.drawRoundedRect(rect, 3, 3)

                # Kreslenie textu súradníc
                painter.setPen(text_color)
                painter.drawText(rect, Qt.AlignCenter, text)

    def draw_grid(self, painter):
        top_left = self.to_world(QPointF(0, 0))
        bottom_right = self.to_world(QPointF(self.width(), self.height()))
        
        start_x = int(top_left.x()) - 1
        end_x = int(bottom_right.x()) + 1
        start_y = int(top_left.y()) - 1
        end_y = int(bottom_right.y()) + 1

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
        
        if self.preview_mode:
            self.preview_mode = False
            self.update()
            return

        if event.modifiers() & Qt.ShiftModifier and event.button() == Qt.LeftButton:
            if self.points:
                self.dragging_all = True
                self.setCursor(Qt.SizeAllCursor)
                return

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
            self.pan_offset += QPointF(delta.x() / scale, delta.y() / scale)
            self.last_mouse_pos = event.position()
            self.update()
            return
        
        if self.dragging_all:
            delta = world_pos - self.last_world_pos
            for i in range(len(self.points)):
                self.points[i] += delta
            
            self.last_world_pos = world_pos
            self.pointsChanged.emit(self.points)
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
        self.dragging_all = False
        self.setCursor(Qt.ArrowCursor)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """Zistí, či bol zasiahnutý bod, a ak áno, vyvolá signál pre editáciu."""
        hit_index = -1
        for i, pt in enumerate(self.points):
            dist = (self.to_screen(pt) - event.position()).manhattanLength()
            if dist < 12:
                hit_index = i
                break
        
        if hit_index != -1:
            self.pointDoubleClicked.emit(hit_index)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Delete and self.selected_index != -1:
            self.delete_selected_point()

    def delete_selected_point(self):
        if self.selected_index != -1 and 0 <= self.selected_index < len(self.points):
            self.points.pop(self.selected_index)
            self.selected_index = max(0, self.selected_index - 1) if self.points else -1
            self.pointsChanged.emit(self.points)
            self.selectionChanged.emit(self.selected_index)
            self.update()

    def center_view(self):
        """Vypočíta ohraničujúci obdĺžnik bodov a upraví zoom a posun tak, aby bol n-uholník v strede."""
        if not self.points:
            # Ak nie sú body, vrátime sa na predvolené hodnoty
            self.pan_offset = QPointF(0, 0)
            self.zoom_level = 1.0
            self.update()
            return

        # Zistenie min/max súradníc (Bounding Box)
        min_x = min(p.x() for p in self.points)
        max_x = max(p.x() for p in self.points)
        min_y = min(p.y() for p in self.points)
        max_y = max(p.y() for p in self.points)

        rect_w = max_x - min_x
        rect_h = max_y - min_y
        center_world = QPointF((min_x + max_x) / 2, (min_y + max_y) / 2)

        # Výpočet nového zoomu tak, aby sa n-uholník zmestil na 80% plochy (padding)
        margin = 0.8
        
        # Šírka vo svete, ktorú chceme zobraziť: rect_w / margin
        # Z rovnice scale: (width / 500) * zoom
        # Chceme: rect_w * scale = width * margin
        # Po dosadení scale: rect_w * (width / 500) * zoom = width * margin
        # zoom = (500 * margin) / rect_w
        
        zoom_x = (self.target_width_units * margin) / rect_w if rect_w > 0 else float('inf')
        
        # Pre výšku musíme brať do úvahy pomer strán okna
        visible_height_units = self.target_width_units * (self.height() / self.width() if self.width() > 0 else 1)
        zoom_y = (visible_height_units * margin) / rect_h if rect_h > 0 else float('inf')

        # Použijeme menší z oboch zoomov (aby sa to zmestilo v oboch smeroch)
        new_zoom = min(zoom_x, zoom_y)
        
        # Ak máme len 1 bod alebo veľmi malý objekt, nedávame nekonečný zoom
        if new_zoom > 10: new_zoom = 1.0

        # Aplikácia zmien
        self.zoom_level = max(self.CONFIG["MAX_ZOOM_OUT"], min(self.CONFIG["MAX_ZOOM_IN"], new_zoom))
        self.pan_offset = -center_world
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

        # Vytvorenie GroupBoxu pre súborové operácie
        file_group = QGroupBox("Súbor")
        file_layout = QVBoxLayout(file_group)

        self.btn_import = QPushButton("Importovať JS...")
        self.btn_import.setFixedHeight(35)
        self.btn_import.setStyleSheet("""
            QPushButton { background-color: #37474f; color: white; font-weight: bold; border-radius: 4px; }
            QPushButton:hover { background-color: #455a64; }
        """)

        self.btn_save = QPushButton("Uložiť JS...")
        self.btn_save.setFixedHeight(35)
        self.btn_save.setStyleSheet("""
            QPushButton { background-color: #00838f; color: white; font-weight: bold; border-radius: 4px; }
            QPushButton:hover { background-color: #0097a7; }
        """)

        file_layout.addWidget(self.btn_import)
        file_layout.addWidget(self.btn_save)
        right_layout.addWidget(file_group) # Pridanie do pravého panelu

        # 1. Možnosti zobrazenia (Mriežka a osi)
        vis_group = QGroupBox("Možnosti zobrazenia")
        vis_layout = QVBoxLayout(vis_group)
        
        self.chk_axes = QCheckBox("Zobraziť hlavné osi")
        self.chk_axes.setChecked(True)
        vis_layout.addWidget(self.chk_axes)
        
        # Jediný globálny prepínač pre mriežku
        self.chk_grid_master = QCheckBox("Zobraziť mriežku")
        self.chk_grid_master.setChecked(True)
        vis_layout.addWidget(self.chk_grid_master)

        self.chk_coords = QCheckBox("Zobraziť súradnice")
        vis_layout.addWidget(self.chk_coords)
            
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
        self.spn_u = QDoubleSpinBox(); self.spn_u.setRange(-1000, 1000); self.spn_u.setValue(-100)
        self.spn_d = QDoubleSpinBox(); self.spn_d.setRange(-1000, 1000); self.spn_d.setValue(100)
        
        safe_layout.addWidget(self.chk_safe_enable, 0, 0, 1, 2)
        safe_layout.addWidget(QLabel("Ľavá (L):"), 1, 0); safe_layout.addWidget(self.spn_l, 1, 1)
        safe_layout.addWidget(QLabel("Pravá (R):"), 2, 0); safe_layout.addWidget(self.spn_r, 2, 1)
        safe_layout.addWidget(QLabel("Horná (U):"), 3, 0); safe_layout.addWidget(self.spn_u, 3, 1)
        safe_layout.addWidget(QLabel("Dolná (D):"), 4, 0); safe_layout.addWidget(self.spn_d, 4, 1)
        right_layout.addWidget(safe_group)

        self.btn_center = QPushButton("Vycentrovať pohľad")
        self.btn_center.setFixedHeight(40)
        self.btn_center.setStyleSheet("""
            QPushButton { 
                background-color: #455a64; 
                color: white; 
                font-weight: bold; 
                border-radius: 4px;
                margin-bottom: 5px;
            }
            QPushButton:hover { background-color: #546e7a; }
        """)
        right_layout.addWidget(self.btn_center)

        self.btn_preview = QPushButton("Spustiť Náhľad")
        self.btn_preview.setFixedHeight(40)
        self.btn_preview.setStyleSheet("""
            QPushButton { 
                background-color: #2e7d32; 
                color: white; 
                font-weight: bold; 
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #388e3c; }
        """)
        right_layout.addWidget(self.btn_preview)

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
        
        self.canvas.pointDoubleClicked.connect(self.open_coordinate_editor)
        self.outliner.itemDoubleClicked.connect(
            lambda item: self.open_coordinate_editor(self.outliner.row(item))
        )

        self.btn_save.clicked.connect(self.action_save_js)
        self.btn_import.clicked.connect(self.action_import_js)
        
        self.btn_center.clicked.connect(self.canvas.center_view)
        self.btn_preview.clicked.connect(self.enable_preview)
        
        # Prepojenie zobrazenia
        self.chk_grid_master.stateChanged.connect(self.update_canvas_settings)
        self.chk_axes.stateChanged.connect(self.update_canvas_settings)
        self.chk_coords.stateChanged.connect(self.update_canvas_settings)
        
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
    
    def action_save_js(self):
        # Zavolá pomocnú funkciu a odovzdá aktuálne body z plátna
        save_ngon_to_js(self, self.canvas.points)

    def action_import_js(self):
        # Zavolá pomocnú funkciu a ak sa načítanie podarí, aktualizuje plátno a UI
        imported_points = import_ngon_from_js(self)
        if imported_points is not None:
            self.canvas.points = imported_points
            self.canvas.selected_index = -1
            self.canvas.selected_segment_idx = -1
            self.canvas.pointsChanged.emit(self.canvas.points)
            self.canvas.center_view() # Vycentruje novo importovaný tvar
            self.canvas.update()

    def update_canvas_settings(self):
        # Načítanie stavu hlavného prepínača mriežky
        self.canvas.show_grid = self.chk_grid_master.isChecked()
        self.canvas.show_axes = self.chk_axes.isChecked()
        
        self.canvas.snap_x = self.check_snap_x.isChecked()
        self.canvas.snap_y = self.check_snap_y.isChecked()

        self.canvas.show_coords = self.chk_coords.isChecked()
        
        self.canvas.safe_enabled = self.chk_safe_enable.isChecked()
        self.canvas.safe_l = self.spn_l.value()
        self.canvas.safe_r = self.spn_r.value()
        self.canvas.safe_u = self.spn_u.value()
        self.canvas.safe_d = self.spn_d.value()
        self.canvas.update()

    def enable_preview(self):
        """Zapne režim náhľadu na plátne."""
        if len(self.canvas.points) > 0:
            self.canvas.preview_mode = True
            self.tabs.setCurrentIndex(0) # Prepnúť na plátno, ak sme v JSONe
            self.canvas.update()

    def toggle_both_snap(self, state):
        # Správne ošetrenie CheckState pre verziu PySide6
        is_checked = (state == Qt.CheckState.Checked.value or state == 2)
        self.check_snap_x.setChecked(is_checked)
        self.check_snap_y.setChecked(is_checked)
        self.update_canvas_settings()

    def open_coordinate_editor(self, index):
        """Otvorí okno pre manuálnu úpravu súradníc vybraného bodu."""
        if 0 <= index < len(self.canvas.points):
            # Synchronizácia výberu
            self.canvas.selected_index = index
            self.sync_selection_to_ui(index)
            self.canvas.update()

            pt = self.canvas.points[index]
            dialog = CoordinateDialog(pt.x(), pt.y(), self)
            
            if dialog.exec() == QDialog.Accepted:
                new_x, new_y = dialog.get_values()
                self.canvas.points[index] = QPointF(new_x, new_y)
                
                # Emitovanie signálu spustí update_ui a prekreslenie
                self.canvas.pointsChanged.emit(self.canvas.points)
                self.canvas.update()

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