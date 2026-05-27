import sys
import json
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTabWidget, QListWidget, QCheckBox, QLabel, QGroupBox, 
    QTextEdit, QDoubleSpinBox, QGridLayout, QDialog, QFormLayout, QDialogButtonBox,
    QComboBox, QPushButton, QToolBar, QSizePolicy, QFrame
)
from PySide6.QtCore import Qt, QPointF, QRectF, Signal, QSize
from PySide6.QtGui import QIcon, QLinearGradient, QPainter, QColor, QPen, QBrush, QKeyEvent, QMouseEvent, QWheelEvent, QPolygonF, QAction

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
        self.ngons = [[]]  # Začíname s jedným prázdnym n-uholníkom
        self.active_ngon_idx = 0  # Index n-uholníka, s ktorým práve pracujeme
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
        self.safe_l, self.safe_r = -175.0, 175.0
        self.safe_u, self.safe_d = -50.0, 0.0
        
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

        # --- PREMENNÉ PRE REŽIM ZMENY VEĽKOSTI (SCALE TOOL) ---
        self.scale_mode_active = False  # Či je nástroj aktívny
        self.scale_handles = {}         # Súradnice transformačných bodov na obrazovke
        self.dragging_handle = None     # Identifikátor ťahaného bodu (napr. 'R', 'L', 'T', 'B')
        self.orig_points_before_scale = [] # Záloha bodov pred začatím ťahania
        self.scale_bbox = QRectF()      # Aktuálny Bounding Box vo svete

    @property
    def points(self):
        """Vráti body aktuálne aktívneho n-uholníka."""
        if 0 <= self.active_ngon_idx < len(self.ngons):
            return self.ngons[self.active_ngon_idx]
        return []

    @points.setter
    def points(self, value):
        """Umožní zápis do bodov aktuálne aktívneho n-uholníka."""
        if 0 <= self.active_ngon_idx < len(self.ngons):
            self.ngons[self.active_ngon_idx] = value

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
            # Prejdeme cyklom cez úplne všetky n-uholníky v zozname self.ngons
            for points in self.ngons:
                if len(points) > 2:
                    # Vykreslenie vyplneného n-uholníka bez okrajov a bodov
                    screen_points = [self.to_screen(p) for p in points]
                    poly = QPolygonF(screen_points)
                    painter.setBrush(QBrush(QColor(0, 150, 255, 180)))  # Jemná modrá výplň
                    painter.setPen(Qt.NoPen)
                    painter.drawPolygon(poly)
            return  # V režime náhľadu preskakujeme kreslenie mriežky a bodov

        # 1. Vykreslenie mriežky (len ak je povolená)
        if self.show_grid:
            self.draw_grid(painter)
        
        # 2. Vykreslenie osí
        if self.show_axes:
            self.draw_axes(painter)

        # 3. Vykreslenie bezpečnej zóny
        if self.safe_enabled:
            self.draw_safe_region(painter)

        # 4. Vykreslenie všetkých n-uholníkov
        for ngon_idx, points in enumerate(self.ngons):
            if len(points) == 0:
                continue
                
            is_active_ngon = (ngon_idx == self.active_ngon_idx)

            for i in range(len(points)):
                p1 = self.to_screen(points[i])
                p2 = self.to_screen(points[(i + 1) % len(points)])
                
                is_closing_segment = (i == len(points) - 1 and len(points) > 2)
                
                if is_active_ngon and i == self.selected_segment_idx:
                    painter.setPen(QPen(QColor(255, 140, 0), 4))  # Oranžový výber hrany aktívneho tvaru
                elif is_active_ngon and i == self.hovered_segment_idx:
                    painter.setPen(QPen(QColor(255, 255, 0), 3))  # Žltý hover
                elif not is_active_ngon:
                    painter.setPen(QPen(QColor(100, 100, 100, 150), 1, Qt.DashLine)) # Neaktívne tvary budú matné a prerušované
                elif is_closing_segment:
                    gradient = QLinearGradient(p1, p2)
                    gradient.setColorAt(0.0, QColor(0, 150, 255))
                    gradient.setColorAt(0.8, QColor(200, 50, 50))
                    gradient.setColorAt(1.0, QColor(255, 0, 0))
                    painter.setPen(QPen(QBrush(gradient), 2))
                else:
                    painter.setPen(QPen(QColor(0, 150, 255), 2))  # Bežná modrá aktívna čiara
                
                painter.drawLine(p1, p2)

        # 5. Vykreslenie bodov (vrcholov) pre všetky n-uholníky
        for ngon_idx, points in enumerate(self.ngons):
            is_active_ngon = (ngon_idx == self.active_ngon_idx)
            
            for i, pt in enumerate(points):
                screen_pt = self.to_screen(pt)
                
                if is_active_ngon and i == self.selected_index:
                    color = QColor(255, 140, 0)
                    size = 5
                elif is_active_ngon and i == self.hovered_point_idx:
                    color = QColor(255, 255, 0)
                    size = 5
                elif not is_active_ngon:
                    color = QColor(80, 80, 80, 150) # Tmavé body pre neaktívne tvary
                    size = 3
                else:
                    color = QColor(255, 255, 255)
                    size = 4
                    
                painter.setBrush(QBrush(color))
                painter.setPen(QPen(QColor(0, 0, 0), 1) if size > 4 else Qt.NoPen)
                painter.drawEllipse(screen_pt, size, size)

        # Vykreslenie transformačného obdĺžnika pre Scale Tool
        if self.scale_mode_active and len(self.points) > 1:
            self.draw_scale_gizmo(painter)
        
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

    def draw_scale_gizmo(self, painter):
        """Vypočíta a vykreslí Bounding Box a transformačné body (handles)."""
        # Ak práve ťaháme, vizuálny box odvodíme z aktuálnych krajných bodov, 
        # ale ak neťaháme, prepočítame ho nanovo.
        if not self.dragging_handle:
            min_x = min(p.x() for p in self.points)
            max_x = max(p.x() for p in self.points)
            min_y = min(p.y() for p in self.points)
            max_y = max(p.y() for p in self.points)
            self.scale_bbox = QRectF(min_x, min_y, max_x - min_x, max_y - min_y)
            
        bbox = self.scale_bbox
        
        # Prepočet rohov na obrazovku
        tl = self.to_screen(QPointF(bbox.left(), bbox.top()))
        br = self.to_screen(QPointF(bbox.right(), bbox.bottom()))
        
        # Vykreslenie prerušovaného ohraničujúceho obdĺžnika
        painter.setPen(QPen(QColor(0, 255, 255), 1, Qt.DashLine))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(QRectF(tl, br))
        
        # 3. Definícia pozícií pre stredové transformačné body (handles) na obrazovke
        mid_x = (tl.x() + br.x()) / 2
        mid_y = (tl.y() + br.y()) / 2
        
        self.scale_handles = {
            "L": QPointF(tl.x(), mid_y),  # Vľavo
            "R": QPointF(br.x(), mid_y),  # Vpravo
            "T": QPointF(mid_x, tl.y()),  # Hore
            "B": QPointF(mid_x, br.y())   # Dole
        }
        
        # 4. Vykreslenie štvorčekov pre handles
        handle_size = 8
        painter.setPen(QPen(QColor(0, 0, 0), 1))
        painter.setBrush(QBrush(QColor(0, 255, 255)))
        
        for name, pt in self.scale_handles.items():
            # Ak na bode stojíme myšou (v budúcnosti), môžeme zmeniť farbu, teraz stačí základná
            painter.drawRect(QRectF(pt.x() - handle_size/2, pt.y() - handle_size/2, handle_size, handle_size))

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

        # Detekcia kliknutia na Scale Handles (iba ak je Scale Tool aktívny)
        if self.scale_mode_active and event.button() == Qt.LeftButton:
            for name, handle_screen_pt in self.scale_handles.items():
                if (handle_screen_pt - event.position()).manhattanLength() < 10:
                    self.dragging_handle = name
                    # Uložíme si kópiu pôvodných bodov pre relatívne prepočty
                    self.orig_points_before_scale = [QPointF(p.x(), p.y()) for p in self.points]
                    self.orig_bbox_before_scale = QRectF(self.scale_bbox) # Pevná záloha boxu
                    self.mouse_press_world_pos = world_pos # Pevná štartovacia pozícia myši
                    return  # Prerušíme vykonávanie, spracovali sme klik na transformáciu
            return
        
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

        # Logika pre zmenu veľkosti (Scale)
        if self.scale_mode_active and self.dragging_handle:
            bbox = self.orig_bbox_before_scale
            if bbox.width() == 0 or bbox.height() == 0:
                return

            # Výpočet posunu myši od momentu stlačenia
            delta_mouse = world_pos - self.mouse_press_world_pos

            # Ak je zapnutý snap, zaokrúhlime samotný posun myši, nie jednotlivé body tvaru
            if self.snap_x:
                can_show_sub_grid = self.zoom_level > self.CONFIG["GRID_SUB_THRESHOLD"]
                step = 1.0 if can_show_sub_grid else 10.0
                delta_mouse.setX(round(delta_mouse.x() / step) * step)
            if self.snap_y:
                can_show_sub_grid = self.zoom_level > self.CONFIG["GRID_SUB_THRESHOLD"]
                step = 1.0 if can_show_sub_grid else 10.0
                delta_mouse.setY(round(delta_mouse.y() / step) * step)

            scale_factor_x = 1.0
            scale_factor_y = 1.0
            anchor = QPointF()

            # Výpočet novej mierky na základe akumulovaného posunu delta_mouse
            if self.dragging_handle == "R":
                anchor = QPointF(bbox.left(), bbox.top() + bbox.height()/2)
                new_width = bbox.width() + delta_mouse.x()
                if abs(new_width) < 0.01: new_width = 0.01
                scale_factor_x = new_width / bbox.width()
            
            elif self.dragging_handle == "L":
                anchor = QPointF(bbox.right(), bbox.top() + bbox.height()/2)
                new_width = bbox.width() - delta_mouse.x()
                if abs(new_width) < 0.01: new_width = 0.01
                scale_factor_x = new_width / bbox.width()

            elif self.dragging_handle == "B":
                anchor = QPointF(bbox.left() + bbox.width()/2, bbox.top())
                new_height = bbox.height() + delta_mouse.y()
                if abs(new_height) < 0.01: new_height = 0.01
                scale_factor_y = new_height / bbox.height()

            elif self.dragging_handle == "T":
                anchor = QPointF(bbox.left() + bbox.width()/2, bbox.bottom())
                new_height = bbox.height() - delta_mouse.y()
                if abs(new_height) < 0.01: new_height = 0.01
                scale_factor_y = new_height / bbox.height()

            # Plynulá aplikácia transformácie z originálnych bodov
            for i, orig_pt in enumerate(self.orig_points_before_scale):
                dx = orig_pt.x() - anchor.x()
                dy = orig_pt.y() - anchor.y()
                
                # Výsledný bod (bez deformovania mriežkou počas pohybu)
                self.points[i] = QPointF(anchor.x() + dx * scale_factor_x, anchor.y() + dy * scale_factor_y)

            # NOVÉ: Dynamický prepočet rámu (scale_bbox) počas ťahania
            min_x = min(p.x() for p in self.points)
            max_x = max(p.x() for p in self.points)
            min_y = min(p.y() for p in self.points)
            max_y = max(p.y() for p in self.points)
            self.scale_bbox = QRectF(min_x, min_y, max_x - min_x, max_y - min_y)

            self.pointsChanged.emit(self.points)
            self.update()
            return
        
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

        # Ak je aktívny Scale Tool, riešime iba zmenu kurzora nad kontrolnými bodmi
        if self.scale_mode_active and not self.is_panning and self.dragging_handle is None:
            hover_handle = None
            for name, handle_screen_pt in self.scale_handles.items():
                if (handle_screen_pt - event.position()).manhattanLength() < 10:
                    hover_handle = name
                    break
            
            if hover_handle:
                if hover_handle in ["L", "R"]:
                    self.setCursor(Qt.SizeHorCursor)
                else:
                    self.setCursor(Qt.SizeVerCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
            return  # V Scale móde už nepokračujeme na detekciu bodov n-uholníka
        
        self.hovered_point_idx = -1
        self.hovered_segment_idx = -1

        # Zmena kurzora, ak sme nad nejakým handle v Scale režime
        if self.scale_mode_active and not self.is_panning and self.dragging_handle is None:
            for name, handle_screen_pt in self.scale_handles.items():
                if (handle_screen_pt - event.position()).manhattanLength() < 10:
                    if name in ["L", "R"]: self.setCursor(Qt.SizeHorCursor)
                    else: self.setCursor(Qt.SizeVerCursor)
                    return
        
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
        self.dragging_handle = None
        self.setCursor(Qt.ArrowCursor)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """Zistí, či bol zasiahnutý bod, a ak áno, vyvolá signál pre editáciu."""
        if self.scale_mode_active:
            return # V Scale móde ignorujeme dvojklik na úpravu bodov
        hit_index = -1
        for i, pt in enumerate(self.points):
            dist = (self.to_screen(pt) - event.position()).manhattanLength()
            if dist < 12:
                hit_index = i
                break
        
        if hit_index != -1:
            self.pointDoubleClicked.emit(hit_index)

    def keyPressEvent(self, event: QKeyEvent):
        # 1. Kontrola pre Shift + šípky (posun celého n-uholníka o 10 jednotiek)
        if event.modifiers() & Qt.ShiftModifier:
            moved = False
            delta = QPointF(0, 0)

            if event.key() == Qt.Key_Left:
                delta = QPointF(-1.0, 0.0)
                moved = True
            elif event.key() == Qt.Key_Right:
                delta = QPointF(1.0, 0.0)
                moved = True
            elif event.key() == Qt.Key_Up:
                # POZNÁMKA: Ak máte herné/matematické súradnice, kde UP znamená mínus v Y, 
                # upravte znamienko podľa potreby vášho plátna (napr. -10.0)
                delta = QPointF(0.0, -1.0)
                moved = True
            elif event.key() == Qt.Key_Down:
                delta = QPointF(0.0, 1.0)
                moved = True

            if moved and self.points:
                # Posunúť každý bod n-uholníka o stanovený delta posun
                for i in range(len(self.points)):
                    self.points[i] += delta
                
                # Oznámiť zmenu aplikácii (aktualizuje Outliner a JSON výstup)
                self.pointsChanged.emit(self.points)
                self.update()
                return  # Ukončíme spracovanie eventu

        # 2. Pôvodná logika pre zmazanie bodu
        if event.key() == Qt.Key_Delete and self.selected_index != -1:
            self.delete_selected_point()

    def delete_selected_point(self):
        if self.selected_index != -1 and 0 <= self.selected_index < len(self.points):
            self.points.pop(self.selected_index)
            self.selected_index = max(0, self.selected_index - 1) if self.points else -1
            self.pointsChanged.emit(self.points)
            self.selectionChanged.emit(self.selected_index)
            self.update()

    def center_view(self, all_ngons=False):
        """Vypočíta ohraničujúci obdĺžnik bodov a upraví zoom a posun tak, aby bol tvar v strede."""
        # Výber bodov na základe parametra
        if all_ngons:
            # Zlúčime body zo všetkých n-uholníkov do jedného zoznamu
            points_to_calc = [pt for ngon in self.ngons for pt in ngon]
        else:
            # Použijeme iba body aktuálneho n-uholníka
            points_to_calc = self.points

        if not points_to_calc:
            # Ak nie sú žiadne body, vrátime sa na predvolené hodnoty
            self.pan_offset = QPointF(0, 0)
            self.zoom_level = 1.0
            self.update()
            return

        # Zistenie min/max súradníc (Bounding Box) z vybraných bodov
        min_x = min(p.x() for p in points_to_calc)
        max_x = max(p.x() for p in points_to_calc)
        min_y = min(p.y() for p in points_to_calc)
        max_y = max(p.y() for p in points_to_calc)

        rect_w = max_x - min_x
        rect_h = max_y - min_y
        center_world = QPointF((min_x + max_x) / 2, (min_y + max_y) / 2)

        # Výpočet nového zoomu tak, aby sa n-uholník zmestil na 80% plochy (padding)
        margin = 0.8
        
        zoom_x = (self.target_width_units * margin) / rect_w if rect_w > 0 else float('inf')
        
        # Pre výšku musíme brať do úvahy pomer strán okna
        visible_height_units = self.target_width_units * (self.height() / self.width() if self.width() > 0 else 1)
        zoom_y = (visible_height_units * margin) / rect_h if rect_h > 0 else float('inf')

        # Použijeme menší z oboch zoomov
        new_zoom = min(zoom_x, zoom_y)
        
        if new_zoom > 10: new_zoom = 1.0

        # Aplikácia zmien
        self.zoom_level = max(self.CONFIG["MAX_ZOOM_OUT"], min(self.CONFIG["MAX_ZOOM_IN"], new_zoom))
        self.pan_offset = -center_world
        self.update()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NGon Editor")
        self.resize(1200, 800)

        self.setWindowIcon(QIcon("icon.png"))

        self.setStyleSheet("""
            QMainWindow { background-color: #252525; }
            QGroupBox { color: #aaa; font-weight: bold; }
            QToolBar {
                background-color: #1a1a1a;
                border-bottom: 1px solid #3a3a3a;
                spacing: 2px;
                padding: 3px 6px;
            }
            QToolBar QToolButton {
                background-color: #2d2d2d;
                color: #cccccc;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 12px;
                min-width: 28px;
            }
            QToolBar QToolButton:hover {
                background-color: #3d3d3d;
                color: #ffffff;
                border-color: #666;
            }
            QToolBar QToolButton:checked {
                background-color: #1565c0;
                color: #ffffff;
                border-color: #1976d2;
            }
            QToolBar QToolButton:checked:hover {
                background-color: #1976d2;
            }
            QToolBar::separator {
                width: 1px;
                background-color: #3a3a3a;
                margin: 4px 6px;
            }
        """)

        # ── TOOLBAR ──────────────────────────────────────────────────────────
        toolbar = QToolBar("Hlavný panel nástrojov")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(16, 16))
        toolbar.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.addToolBar(Qt.TopToolBarArea, toolbar)

        # Súbor
        self.btn_import = toolbar.addAction("⬆ Import")
        self.btn_import.setToolTip("Importovať tvar zo súboru JS")
        self.btn_save = toolbar.addAction("💾 Uložiť")
        self.btn_save.setToolTip("Uložiť tvar do súboru JS")

        toolbar.addSeparator()

        # Zobrazenie – toggle akcie
        self.act_axes = QAction("🗡 Osi", self)
        self.act_axes.setCheckable(True)
        self.act_axes.setChecked(True)
        self.act_axes.setToolTip("Zobraziť / skryť hlavné osi")
        toolbar.addAction(self.act_axes)

        self.act_grid = QAction("⊞ Mriežka", self)
        self.act_grid.setCheckable(True)
        self.act_grid.setChecked(True)
        self.act_grid.setToolTip("Zobraziť / skryť mriežku")
        toolbar.addAction(self.act_grid)

        self.act_coords = QAction("🔢 Coords", self)
        self.act_coords.setCheckable(True)
        self.act_coords.setChecked(False)
        self.act_coords.setToolTip("Zobraziť / skryť súradnice bodov")
        toolbar.addAction(self.act_coords)

        toolbar.addSeparator()

        # Akcie
        self.act_scale_tool = QAction("⤗ Mierka", self)
        self.act_scale_tool.setCheckable(True)
        self.act_scale_tool.setChecked(False)
        self.act_scale_tool.setToolTip("Aktivovať nástroj na zmenu veľkosti (Scale Tool)")
        toolbar.addAction(self.act_scale_tool)

        self.act_smooth = toolbar.addAction("〜 Smooth")
        self.act_smooth.setToolTip("Vyhladiť tvar (Chaikin)")

        self.act_center = toolbar.addAction("⊙ Centrovať")
        self.act_center.setToolTip("Vycentrovať pohľad na aktuálny tvar")

        self.act_center_all = toolbar.addAction("⊛ Centrovať všetko")
        self.act_center_all.setToolTip("Vycentrovať pohľad na všetky tvary")

        self.act_preview = toolbar.addAction("▶ Náhľad")
        self.act_preview.setToolTip("Zobraziť vyplnený náhľad tvaru")

        # Spacer aby ďalšie prvky išli doprava
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)

        # ── CENTRÁLNY WIDGET ─────────────────────────────────────────────────
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Hlavná časť so záložkami
        self.tabs = QTabWidget()
        self.canvas = NGonCanvas()
        self.tabs.addTab(self.canvas, "Návrhové plátno")

        self.json_view = QTextEdit()
        self.json_view.setReadOnly(True)
        self.json_view.setStyleSheet("background-color: #1e1e1e; color: #9cdcfe; font-family: 'Consolas';")
        self.tabs.addTab(self.json_view, "JavaScript výstup")
        layout.addWidget(self.tabs, stretch=4)

        # ── BOČNÝ PANEL (slim) ───────────────────────────────────────────────
        right_panel = QWidget()
        right_panel.setMaximumWidth(220)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(2, 2, 2, 2)
        right_layout.setSpacing(6)
        layout.addWidget(right_panel, stretch=1)

        # Prichytávanie
        snap_group = QGroupBox("Prichytávanie (Snap)")
        snap_layout = QGridLayout(snap_group)
        snap_layout.setSpacing(4)
        self.check_snap_x = QCheckBox("Snap X")
        self.check_snap_y = QCheckBox("Snap Y")
        self.check_snap_both = QCheckBox("Snap X+Y")
        self.btn_snap_all_int = QPushButton("Prichytiť na celé čísla")
        self.btn_snap_all_int.setStyleSheet("""
            QPushButton { background-color: #006064; color: white; font-weight: bold; border-radius: 4px; padding: 3px; }
            QPushButton:hover { background-color: #00838f; }
        """)
        snap_layout.addWidget(self.check_snap_x, 0, 0)
        snap_layout.addWidget(self.check_snap_y, 0, 1)
        snap_layout.addWidget(self.check_snap_both, 1, 0, 1, 2)
        snap_layout.addWidget(self.btn_snap_all_int, 2, 0, 1, 2)
        right_layout.addWidget(snap_group)

        # Bezpečná zóna
        safe_group = QGroupBox("Bezpečná zóna")
        safe_layout = QGridLayout(safe_group)
        safe_layout.setSpacing(3)
        self.chk_safe_enable = QCheckBox("Povoliť")
        self.spn_l = QDoubleSpinBox(); self.spn_l.setRange(-1000, 1000); self.spn_l.setValue(-175)
        self.spn_r = QDoubleSpinBox(); self.spn_r.setRange(-1000, 1000); self.spn_r.setValue(175)
        self.spn_u = QDoubleSpinBox(); self.spn_u.setRange(-1000, 1000); self.spn_u.setValue(-50)
        self.spn_d = QDoubleSpinBox(); self.spn_d.setRange(-1000, 1000); self.spn_d.setValue(0)
        safe_layout.addWidget(self.chk_safe_enable, 0, 0, 1, 2)
        safe_layout.addWidget(QLabel("L:"), 1, 0); safe_layout.addWidget(self.spn_l, 1, 1)
        safe_layout.addWidget(QLabel("R:"), 2, 0); safe_layout.addWidget(self.spn_r, 2, 1)
        safe_layout.addWidget(QLabel("U:"), 3, 0); safe_layout.addWidget(self.spn_u, 3, 1)
        safe_layout.addWidget(QLabel("D:"), 4, 0); safe_layout.addWidget(self.spn_d, 4, 1)
        right_layout.addWidget(safe_group)

        # Správa tvarov
        ngon_manage_group = QGroupBox("Správa tvarov")
        ngon_manage_layout = QVBoxLayout(ngon_manage_group)
        ngon_manage_layout.setSpacing(4)

        self.ngon_list_combo = QComboBox()
        self.ngon_list_combo.addItem("Tvar 0")

        self.btn_add_ngon = QPushButton("+ Pridať tvar")
        self.btn_add_ngon.setStyleSheet("""
            QPushButton { background-color: #2e7d32; color: white; font-weight: bold; border-radius: 4px; }
            QPushButton:hover { background-color: #388e3c; }
        """)
        self.btn_delete_ngon = QPushButton("✕ Zmazať tvar")
        self.btn_delete_ngon.setStyleSheet("""
            QPushButton { background-color: #c62828; color: white; font-weight: bold; border-radius: 4px; }
            QPushButton:hover { background-color: #d32f2f; }
        """)

        ngon_manage_layout.addWidget(self.ngon_list_combo)
        ngon_btns = QHBoxLayout()
        ngon_btns.addWidget(self.btn_add_ngon)
        ngon_btns.addWidget(self.btn_delete_ngon)
        ngon_manage_layout.addLayout(ngon_btns)
        right_layout.addWidget(ngon_manage_group)

        # Outliner
        right_layout.addWidget(QLabel("Body (Outliner):"))
        self.outliner = QListWidget()
        self.outliner.installEventFilter(self)
        right_layout.addWidget(self.outliner)

        # Skryté checkboxy pre spätnú kompatibilitu so setup_connections / update_canvas_settings
        self.chk_axes = QCheckBox()
        self.chk_axes.setChecked(True)
        self.chk_axes.setVisible(False)
        self.chk_grid_master = QCheckBox()
        self.chk_grid_master.setChecked(True)
        self.chk_grid_master.setVisible(False)
        self.chk_coords = QCheckBox()
        self.chk_coords.setChecked(False)
        self.chk_coords.setVisible(False)

        # Skryté tlačidlá – toolbar ich nahrádza, ale setup_connections ich používa
        self.btn_save_widget = QPushButton()
        self.btn_save_widget.setVisible(False)
        self.btn_import_widget = QPushButton()
        self.btn_import_widget.setVisible(False)
        self.btn_smooth_all = QPushButton()
        self.btn_smooth_all.setVisible(False)
        self.btn_center_current = QPushButton()
        self.btn_center_current.setVisible(False)
        self.btn_center_all = QPushButton()
        self.btn_center_all.setVisible(False)
        self.btn_preview = QPushButton()
        self.btn_preview.setVisible(False)

        self.setup_connections()
        self.update_ui([])
        self.update_canvas_settings()

    def setup_connections(self):
        self.canvas.pointsChanged.connect(self.update_ui)
        self.canvas.selectionChanged.connect(self.sync_selection_to_ui)
        self.outliner.currentRowChanged.connect(self.sync_selection_to_canvas)

        self.canvas.pointDoubleClicked.connect(self.open_coordinate_editor)
        self.outliner.itemDoubleClicked.connect(
            lambda item: self.open_coordinate_editor(self.outliner.row(item))
        )

        # Toolbar – súbor
        self.btn_save.triggered.connect(self.action_save_js)
        self.btn_import.triggered.connect(self.action_import_js)

        # Toolbar – toggle zobrazenia
        self.act_axes.toggled.connect(self._sync_axes)
        self.act_grid.toggled.connect(self._sync_grid)
        self.act_coords.toggled.connect(self._sync_coords)

        # Toolbar – akcie
        self.act_scale_tool.toggled.connect(self._sync_scale_tool)
        self.act_smooth.triggered.connect(self.smooth_all_points)
        self.act_center.triggered.connect(lambda: self.canvas.center_view(all_ngons=False))
        self.act_center_all.triggered.connect(lambda: self.canvas.center_view(all_ngons=True))
        self.act_preview.triggered.connect(self.enable_preview)

        # Prichytávanie
        self.check_snap_x.stateChanged.connect(self.update_canvas_settings)
        self.check_snap_y.stateChanged.connect(self.update_canvas_settings)
        self.check_snap_both.stateChanged.connect(self.toggle_both_snap)
        self.btn_snap_all_int.clicked.connect(self.snap_all_points_to_integer)

        # Bezpečná zóna
        self.chk_safe_enable.stateChanged.connect(self.update_canvas_settings)
        for s in [self.spn_l, self.spn_r, self.spn_u, self.spn_d]:
            s.valueChanged.connect(self.update_canvas_settings)

        # Správa tvarov
        self.btn_add_ngon.clicked.connect(self.action_add_new_ngon)
        self.btn_delete_ngon.clicked.connect(self.action_delete_current_ngon)
        self.ngon_list_combo.currentIndexChanged.connect(self.action_change_active_ngon)

    # ── Sync helpery pre toolbar toggle akcie ────────────────────────────────
    def _sync_axes(self, checked):
        self.chk_axes.setChecked(checked)
        self.update_canvas_settings()

    def _sync_grid(self, checked):
        self.chk_grid_master.setChecked(checked)
        self.update_canvas_settings()

    def _sync_coords(self, checked):
        self.chk_coords.setChecked(checked)
        self.update_canvas_settings()

    def action_add_new_ngon(self):
        """Pridá nový prázdny n-uholník a prepne sa naň."""
        self.canvas.ngons.append([])
        new_idx = len(self.canvas.ngons) - 1
        
        # Blokujeme signál, aby sme nevyvolali zmenu indexu dvakrát
        self.ngon_list_combo.blockSignals(True)
        self.ngon_list_combo.addItem(f"Tvar {new_idx}")
        self.ngon_list_combo.setCurrentIndex(new_idx)
        self.ngon_list_combo.blockSignals(False)
        
        self.canvas.active_ngon_idx = new_idx
        self.canvas.selected_index = -1
        self.canvas.selected_segment_idx = -1
        self.update_ui([])
        self.canvas.update()

    def action_delete_current_ngon(self):
        """Zmaže aktuálny n-uholník, ak to nie je jediný zostávajúci."""
        if len(self.canvas.ngons) <= 1:
            # Ak je posledný, iba ho vyčistíme
            self.canvas.ngons[0] = []
            self.canvas.selected_index = -1
            self.canvas.pointsChanged.emit([])
            self.canvas.update()
            return

        idx_to_remove = self.canvas.active_ngon_idx
        self.canvas.ngons.pop(idx_to_remove)
        
        # Nastavíme nový aktívny index
        self.canvas.active_ngon_idx = max(0, idx_to_remove - 1)
        
        # Obnovíme ComboBox
        self.ngon_list_combo.blockSignals(True)
        self.ngon_list_combo.clear()
        for i in range(len(self.canvas.ngons)):
            self.ngon_list_combo.addItem(f"Tvar {i}")
        self.ngon_list_combo.setCurrentIndex(self.canvas.active_ngon_idx)
        self.ngon_list_combo.blockSignals(False)
        
        self.canvas.selected_index = -1
        self.canvas.selected_segment_idx = -1
        self.canvas.pointsChanged.emit(self.canvas.points)
        self.canvas.update()

    def action_change_active_ngon(self, index):
        """Prepne aktívny n-uholník podľa výberu v menu."""
        if 0 <= index < len(self.canvas.ngons):
            self.canvas.active_ngon_idx = index
            self.canvas.selected_index = -1
            self.canvas.selected_segment_idx = -1
            # Vyvoláme aktualizáciu UI pre novo zvolený n-uholník
            self.update_ui(self.canvas.points)
            self.canvas.update()

    def eventFilter(self, watched, event):
        """Zachytí stlačenie klávesu Delete, ak má focus Outliner."""
        if watched == self.outliner and event.type() == QKeyEvent.Type.KeyPress:
            if event.key() == Qt.Key_Delete:
                self.canvas.delete_selected_point()
                return True
        return super().eventFilter(watched, event)
    
    def action_save_js(self):
        # POZMENA: Namiesto self.canvas.points posielame kompletne celé self.canvas.ngons
        save_ngon_to_js(self, self.canvas.ngons)

    def action_import_js(self):
        # POZMENA: Načítame zoznam všetkých tvarov (2D pole)
        imported_ngons = import_ngon_from_js(self)
        if imported_ngons is not None:
            self.canvas.ngons = imported_ngons
            
            # Prepne index na prvý n-uholník
            self.canvas.active_ngon_idx = 0
            self.canvas.selected_index = -1
            self.canvas.selected_segment_idx = -1
            
            # Aktualizujeme rozbaľovacie menu (ComboBox) podľa počtu načítaných tvarov
            self.ngon_list_combo.blockSignals(True)
            self.ngon_list_combo.clear()
            for i in range(len(self.canvas.ngons)):
                self.ngon_list_combo.addItem(f"Tvar {i}")
            self.ngon_list_combo.setCurrentIndex(0)
            self.ngon_list_combo.blockSignals(False)
            
            # Aktualizujeme UI a plátno
            self.canvas.pointsChanged.emit(self.canvas.points)
            self.canvas.center_view(all_ngons=True) # Vycentruje zobrazenie na všetky tvary
            self.canvas.update()

    def snap_all_points_to_integer(self):
        """Zaokrúhli súradnice všetkých bodov na najbližšie celé číslo."""
        if not self.canvas.points:
            return
            
        for i in range(len(self.canvas.points)):
            pt = self.canvas.points[i]
            self.canvas.points[i] = QPointF(round(pt.x()), round(pt.y()))
            
        # Oznámime aplikácii zmenu, aby sa prekreslilo plátno a aktualizoval Outliner/JSON
        self.canvas.pointsChanged.emit(self.canvas.points)
        self.canvas.update()

    def _sync_scale_tool(self, checked):
        self.canvas.scale_mode_active = checked
        self.canvas.update()

    def smooth_all_points(self):
        """Vyhladí tvar pomocou Chaikinovho algoritmu (Corner Cutting)."""
        points = self.canvas.points
        # Vyhladzovanie má zmysel len ak máme uzavretý tvar (aspoň 3 body)
        if len(points) < 3:
            return
            
        smoothed_points = []
        n = len(points)
        
        for i in range(n):
            pt_current = points[i]
            pt_next = points[(i + 1) % n]
            
            # Chaikinov algoritmus berie body v 1/4 a 3/4 úsečky
            # QPointF podporuje základnú lineárnu algebru
            q1 = pt_current * 0.75 + pt_next * 0.25
            q2 = pt_current * 0.25 + pt_next * 0.75
            
            smoothed_points.append(q1)
            smoothed_points.append(q2)
            
        # Prepíšeme body na plátne novými vyhladenými bodmi
        self.canvas.points = smoothed_points
        
        # Zrušíme aktuálny výber, keďže staré indexy bodov už neexistujú
        self.canvas.selected_index = -1
        self.canvas.selected_segment_idx = -1
        
        # Oznámime aplikácii zmenu (prekreslí sa Outliner a JSON)
        self.canvas.pointsChanged.emit(self.canvas.points)
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
        """Zapne režim náhľadu na plátne, ak existuje aspoň jeden vykresliteľný tvar."""
        # Overíme, či aspoň jeden n-uholník obsahuje nejaké body
        has_any_points = any(len(ngon) > 0 for ngon in self.canvas.ngons)
        
        if has_any_points:
            self.canvas.preview_mode = True
            self.tabs.setCurrentIndex(0)  # Prepnúť na plátno, ak sme v JSONe
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
        
        # Outliner plníme len pre AKTÍVNY n-uholník
        for i, pt in enumerate(points):
            self.outliner.addItem(f"Bod {i}: [{pt.x():.1f}, {pt.y():.1f}]")
        
        if self.canvas.selected_index != -1:
            self.outliner.setCurrentRow(self.canvas.selected_index)
        self.outliner.blockSignals(False)

        # GENEROVANIE EXPORTU PRE VŠETKY N-UHOLNÍKY
        all_ngons_js = []
        for idx, ngon in enumerate(self.canvas.ngons):
            items = [f"{{x: {pt.x():.2f}, y: {pt.y():.2f}}}" for pt in ngon]
            ngon_string = "[\n        " + ",\n        ".join(items) + "\n    ]"
            all_ngons_js.append(ngon_string)
            
        js_code = "const ngons = [\n    " + ",\n    ".join(all_ngons_js) + "\n];"
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