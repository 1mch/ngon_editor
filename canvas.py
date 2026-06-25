from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QLinearGradient, QPolygonF, QWheelEvent, QMouseEvent, QKeyEvent, QImage
import math
import copy

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
        self.selected_indices = set()
        self.selection_rect = QRectF() # Pre marquee selection
        self.is_marquee_selecting = False
        self.marquee_start_pos = QPointF()
        
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

        # --- PREMENNÉ PRE REŽIM ROTÁCIE (ROTATE TOOL) ---
        self.rotate_mode_active = False
        self.is_rotating = False
        self.orig_points_before_rotate = []
        self.rotate_center = QPointF()
        self.start_angle = 0.0
        self.current_rotation_angle = 0.0

        # --- UNDO / REDO ---
        self.undo_stack = []
        self.redo_stack = []

        # --- REFERENČNÝ OBRÁZOK ---
        self.bg_image = None
        self.bg_opacity = 0.5
        self.bg_width_auto = True
        self.bg_width = 500.0
        self.bg_height_auto = True
        self.bg_height = 500.0
        self.bg_center_x = True
        self.bg_center_y = True
        self.bg_offset = QPointF(0, 0)
        
    def push_history(self):
        current_state = {
            'ngons': [[QPointF(p.x(), p.y()) for p in ngon] for ngon in self.ngons],
            'active_idx': self.active_ngon_idx,
            'selected_indices': set(self.selected_indices)
        }
        self.undo_stack.append(current_state)
        if len(self.undo_stack) > 50:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self):
        if not self.undo_stack: return
        current_state = {
            'ngons': [[QPointF(p.x(), p.y()) for p in ngon] for ngon in self.ngons],
            'active_idx': self.active_ngon_idx,
            'selected_indices': set(self.selected_indices)
        }
        self.redo_stack.append(current_state)
        state = self.undo_stack.pop()
        self.ngons = [[QPointF(p.x(), p.y()) for p in ngon] for ngon in state['ngons']]
        self.active_ngon_idx = state['active_idx']
        self.selected_indices = set(state['selected_indices'])
        self.pointsChanged.emit(self.points)
        self.selectionChanged.emit(-1)
        self.update()

    def redo(self):
        if not self.redo_stack: return
        current_state = {
            'ngons': [[QPointF(p.x(), p.y()) for p in ngon] for ngon in self.ngons],
            'active_idx': self.active_ngon_idx,
            'selected_indices': set(self.selected_indices)
        }
        self.undo_stack.append(current_state)
        state = self.redo_stack.pop()
        self.ngons = [[QPointF(p.x(), p.y()) for p in ngon] for ngon in state['ngons']]
        self.active_ngon_idx = state['active_idx']
        self.selected_indices = set(state['selected_indices'])
        self.pointsChanged.emit(self.points)
        self.selectionChanged.emit(-1)
        self.update()

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

        if self.bg_image:
            painter.setOpacity(self.bg_opacity)
            
            orig_w = self.bg_image.width()
            orig_h = self.bg_image.height()
            
            if self.bg_width_auto and self.bg_height_auto:
                w = orig_w
                h = orig_h
            elif self.bg_width_auto:
                h = self.bg_height
                w = orig_w * (h / orig_h) if orig_h != 0 else orig_w
            elif self.bg_height_auto:
                w = self.bg_width
                h = orig_h * (w / orig_w) if orig_w != 0 else orig_h
            else:
                w = self.bg_width
                h = self.bg_height
                
            x = self.bg_offset.x()
            y = self.bg_offset.y()
            
            if self.bg_center_x:
                x -= w / 2.0
            if self.bg_center_y:
                y -= h / 2.0
                
            world_rect = QRectF(x, y, w, h)
            
            tl = self.to_screen(world_rect.topLeft())
            br = self.to_screen(world_rect.bottomRight())
            painter.drawImage(QRectF(tl, br), self.bg_image)
            painter.setOpacity(1.0)

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
                
                if is_active_ngon and i in self.selected_indices:
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

        # Vykreslenie Marquee selection boxu
        if self.is_marquee_selecting:
            painter.setPen(QPen(QColor(0, 150, 255), 1, Qt.DashLine))
            painter.setBrush(QBrush(QColor(0, 150, 255, 40)))
            painter.drawRect(self.selection_rect)

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
                is_selected = (i in self.selected_indices)
                bg_color = QColor(255, 140, 0) if is_selected else QColor(255, 255, 255, 220)
                text_color = QColor(255, 255, 255) if is_selected else QColor(0, 0, 0)

                # Kreslenie pozadia štítku
                painter.setPen(QPen(QColor(0, 0, 0), 1))
                painter.setBrush(QBrush(bg_color))
                painter.drawRoundedRect(rect, 3, 3)

                # Kreslenie textu súradníc
                painter.setPen(text_color)
                painter.drawText(rect, Qt.AlignCenter, text)

        # Vykreslenie uhla rotácie počas otáčania
        if self.rotate_mode_active and self.is_rotating:
            painter.setFont(self.font())
            text = f"{self.current_rotation_angle:.1f}°"
            screen_center = self.to_screen(self.rotate_center)
            metrics = painter.fontMetrics()
            rect = metrics.boundingRect(text)
            rect.adjust(-4, -2, 4, 2)
            rect.translate(screen_center.x() + 15, screen_center.y() - 15)
            
            painter.setPen(QPen(QColor(0, 0, 0), 1))
            painter.setBrush(QBrush(QColor(255, 140, 0, 220)))
            painter.drawRoundedRect(rect, 3, 3)
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(rect, Qt.AlignCenter, text)

    def draw_scale_gizmo(self, painter):
        """Vypočíta a vykreslí Bounding Box a transformačné body (handles)."""
        # Ak práve ťaháme, vizuálny box odvodíme z aktuálnych krajných bodov, 
        # ale ak neťaháme, prepočítame ho nanovo.
        if not self.dragging_handle:
            points_to_scale = [p for i, p in enumerate(self.points) if i in self.selected_indices] if len(self.selected_indices) > 1 else self.points
            if not points_to_scale:
                return
            min_x = min(p.x() for p in points_to_scale)
            max_x = max(p.x() for p in points_to_scale)
            min_y = min(p.y() for p in points_to_scale)
            max_y = max(p.y() for p in points_to_scale)
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
            "B": QPointF(mid_x, br.y()),  # Dole
            "TL": QPointF(tl.x(), tl.y()), # Vľavo Hore
            "TR": QPointF(br.x(), tl.y()), # Vpravo Hore
            "BL": QPointF(tl.x(), br.y()), # Vľavo Dole
            "BR": QPointF(br.x(), br.y())  # Vpravo Dole
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
        
        # Logika pre Rotáciu
        if self.rotate_mode_active and event.button() == Qt.LeftButton and len(self.points) > 1:
            self.is_rotating = True
            self.orig_points_before_rotate = [QPointF(p.x(), p.y()) for p in self.points]
            
            points_to_rotate = [p for i, p in enumerate(self.points) if i in self.selected_indices] if len(self.selected_indices) > 1 else self.points
            min_x = min(p.x() for p in points_to_rotate)
            max_x = max(p.x() for p in points_to_rotate)
            min_y = min(p.y() for p in points_to_rotate)
            max_y = max(p.y() for p in points_to_rotate)
            self.rotate_center = QPointF((min_x + max_x) / 2, (min_y + max_y) / 2)
            
            self.start_angle = math.degrees(math.atan2(world_pos.y() - self.rotate_center.y(), world_pos.x() - self.rotate_center.x()))
            self.current_rotation_angle = 0.0
            return
        
        if self.preview_mode:
            self.preview_mode = False
            self.update()
            return

        if event.modifiers() & Qt.ShiftModifier and event.button() == Qt.LeftButton:
            if self.points:
                self.dragging_all = True
                self.orig_points_before_drag = [QPointF(p.x(), p.y()) for p in self.points]
                self.mouse_press_world_pos = world_pos
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
            self.push_history()
            if event.modifiers() & Qt.ControlModifier:
                if hit_index in self.selected_indices:
                    self.selected_indices.remove(hit_index)
                else:
                    self.selected_indices.add(hit_index)
            else:
                if hit_index not in self.selected_indices:
                    self.selected_indices.clear()
                    self.selected_indices.add(hit_index)
                    
            self.dragging_point_idx = hit_index
            self.selected_segment_idx = -1
            self.orig_points_before_drag = [QPointF(p.x(), p.y()) for p in self.points]
            self.mouse_press_world_pos = world_pos
            self.selectionChanged.emit(hit_index if len(self.selected_indices) == 1 else -1)
            self.update()
            return

        # 2. Kliknutie na segment (čiara)
        if self.hovered_segment_idx != -1:
            self.push_history()
            if event.modifiers() & Qt.ControlModifier:
                # Vloženie nového bodu do vybratej čiary
                new_pt = self.apply_snap(world_pos)
                self.points.insert(self.hovered_segment_idx + 1, new_pt)
                self.selected_indices.clear()
                self.selected_indices.add(self.hovered_segment_idx + 1)
                self.selected_segment_idx = -1
                self.pointsChanged.emit(self.points)
                self.selectionChanged.emit(self.hovered_segment_idx + 1)
            else:
                # Označenie segmentu na posunutie celej hrany
                self.selected_segment_idx = self.hovered_segment_idx
                self.dragging_segment_idx = self.hovered_segment_idx
                self.orig_points_before_drag = [QPointF(p.x(), p.y()) for p in self.points]
                self.mouse_press_world_pos = world_pos
                self.selected_indices.clear()
                self.selectionChanged.emit(-1)
            self.update()
            return

        # 3. Pridanie nového bodu na koniec (len s Ctrl)
        if event.modifiers() & Qt.ControlModifier:
            self.push_history()
            new_pt = self.apply_snap(world_pos)
            self.points.append(new_pt)
            self.selected_indices.clear()
            self.selected_indices.add(len(self.points) - 1)
            self.selected_segment_idx = -1
            self.pointsChanged.emit(self.points)
            self.selectionChanged.emit(len(self.points) - 1)
            self.update()
            return
            
        # 4. Klik do prázdna (Marquee selection)
        if event.button() == Qt.LeftButton:
            if not (event.modifiers() & Qt.ControlModifier):
                self.selected_indices.clear()
            self.selected_segment_idx = -1
            self.selectionChanged.emit(-1)
            
            self.is_marquee_selecting = True
            self.marquee_start_pos = event.position()
            self.selection_rect = QRectF(self.marquee_start_pos, self.marquee_start_pos)
            self.update()
            return

    def mouseMoveEvent(self, event: QMouseEvent):
        world_pos = self.to_world(event.position())

        # Logika pre voľnú rotáciu
        if self.rotate_mode_active and self.is_rotating:
            current_mouse_angle = math.degrees(math.atan2(world_pos.y() - self.rotate_center.y(), world_pos.x() - self.rotate_center.x()))
            delta_angle = current_mouse_angle - self.start_angle
            
            # Snap na násobky 10° ak je stlačený Shift
            if event.modifiers() & Qt.ShiftModifier:
                delta_angle = round(delta_angle / 10.0) * 10.0
                
            self.current_rotation_angle = delta_angle
            
            # Rotácia bodov okolo self.rotate_center
            rad_angle = math.radians(delta_angle)
            cos_a = math.cos(rad_angle)
            sin_a = math.sin(rad_angle)
            
            for i, orig_pt in enumerate(self.orig_points_before_rotate):
                dx = orig_pt.x() - self.rotate_center.x()
                dy = orig_pt.y() - self.rotate_center.y()
                
                new_x = self.rotate_center.x() + dx * cos_a - dy * sin_a
                new_y = self.rotate_center.y() + dx * sin_a + dy * cos_a
                
                self.points[i] = QPointF(new_x, new_y)
                
            self.pointsChanged.emit(self.points)
            self.update()
            return

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

            elif self.dragging_handle == "TL":
                anchor = QPointF(bbox.right(), bbox.bottom())
                new_width = bbox.width() - delta_mouse.x()
                new_height = bbox.height() - delta_mouse.y()
                if abs(new_width) < 0.01: new_width = 0.01
                if abs(new_height) < 0.01: new_height = 0.01
                scale_factor_x = new_width / bbox.width()
                scale_factor_y = new_height / bbox.height()

            elif self.dragging_handle == "TR":
                anchor = QPointF(bbox.left(), bbox.bottom())
                new_width = bbox.width() + delta_mouse.x()
                new_height = bbox.height() - delta_mouse.y()
                if abs(new_width) < 0.01: new_width = 0.01
                if abs(new_height) < 0.01: new_height = 0.01
                scale_factor_x = new_width / bbox.width()
                scale_factor_y = new_height / bbox.height()

            elif self.dragging_handle == "BL":
                anchor = QPointF(bbox.right(), bbox.top())
                new_width = bbox.width() - delta_mouse.x()
                new_height = bbox.height() + delta_mouse.y()
                if abs(new_width) < 0.01: new_width = 0.01
                if abs(new_height) < 0.01: new_height = 0.01
                scale_factor_x = new_width / bbox.width()
                scale_factor_y = new_height / bbox.height()

            elif self.dragging_handle == "BR":
                anchor = QPointF(bbox.left(), bbox.top())
                new_width = bbox.width() + delta_mouse.x()
                new_height = bbox.height() + delta_mouse.y()
                if abs(new_width) < 0.01: new_width = 0.01
                if abs(new_height) < 0.01: new_height = 0.01
                scale_factor_x = new_width / bbox.width()
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
        
        if self.is_marquee_selecting:
            self.selection_rect = QRectF(self.marquee_start_pos, event.position()).normalized()
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
            delta = world_pos - self.mouse_press_world_pos
            
            if self.snap_x:
                can_show_sub_grid = self.zoom_level > self.CONFIG["GRID_SUB_THRESHOLD"]
                step = 1.0 if can_show_sub_grid else 10.0
                delta.setX(round(delta.x() / step) * step)
            if self.snap_y:
                can_show_sub_grid = self.zoom_level > self.CONFIG["GRID_SUB_THRESHOLD"]
                step = 1.0 if can_show_sub_grid else 10.0
                delta.setY(round(delta.y() / step) * step)

            for i in range(len(self.points)):
                self.points[i] = self.orig_points_before_drag[i] + delta
            
            self.pointsChanged.emit(self.points)
            self.update()
            return

        if self.dragging_point_idx != -1:
            delta = world_pos - self.mouse_press_world_pos
            if self.snap_x:
                can_show_sub_grid = self.zoom_level > self.CONFIG["GRID_SUB_THRESHOLD"]
                step = 1.0 if can_show_sub_grid else 10.0
                delta.setX(round(delta.x() / step) * step)
            if self.snap_y:
                can_show_sub_grid = self.zoom_level > self.CONFIG["GRID_SUB_THRESHOLD"]
                step = 1.0 if can_show_sub_grid else 10.0
                delta.setY(round(delta.y() / step) * step)

            for idx in self.selected_indices:
                self.points[idx] = self.orig_points_before_drag[idx] + delta
                
            self.pointsChanged.emit(self.points)
            self.update()
            return

        if self.dragging_segment_idx != -1:
            delta = world_pos - self.mouse_press_world_pos
            
            if self.snap_x:
                can_show_sub_grid = self.zoom_level > self.CONFIG["GRID_SUB_THRESHOLD"]
                step = 1.0 if can_show_sub_grid else 10.0
                delta.setX(round(delta.x() / step) * step)
            if self.snap_y:
                can_show_sub_grid = self.zoom_level > self.CONFIG["GRID_SUB_THRESHOLD"]
                step = 1.0 if can_show_sub_grid else 10.0
                delta.setY(round(delta.y() / step) * step)

            idx1 = self.dragging_segment_idx
            idx2 = (idx1 + 1) % len(self.points)
            
            self.points[idx1] = self.orig_points_before_drag[idx1] + delta
            self.points[idx2] = self.orig_points_before_drag[idx2] + delta
            
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
                elif hover_handle in ["T", "B"]:
                    self.setCursor(Qt.SizeVerCursor)
                elif hover_handle in ["TL", "BR"]:
                    self.setCursor(Qt.SizeFDiagCursor)
                elif hover_handle in ["TR", "BL"]:
                    self.setCursor(Qt.SizeBDiagCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
            return  # V Scale móde už nepokračujeme na detekciu bodov n-uholníka
        
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
        if self.is_marquee_selecting:
            self.is_marquee_selecting = False
            
            if not (event.modifiers() & Qt.ControlModifier):
                self.selected_indices.clear()
                
            for i, pt in enumerate(self.points):
                screen_pt = self.to_screen(pt)
                if self.selection_rect.contains(screen_pt):
                    self.selected_indices.add(i)
                    
            self.selectionChanged.emit(next(iter(self.selected_indices)) if len(self.selected_indices) == 1 else -1)
            self.update()
            return
            
        self.is_panning = False
        self.dragging_point_idx = -1
        self.dragging_segment_idx = -1
        self.dragging_all = False
        self.dragging_handle = None
        self.is_rotating = False
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
        # Esc zruší rotáciu
        if event.key() == Qt.Key_Escape and self.is_rotating:
            self.is_rotating = False
            self.points = [QPointF(p.x(), p.y()) for p in self.orig_points_before_rotate]
            self.current_rotation_angle = 0.0
            self.pointsChanged.emit(self.points)
            self.update()
            return
            
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
        if event.key() == Qt.Key_Delete and self.selected_indices:
            self.delete_selected_point()

    def delete_selected_point(self):
        if not self.selected_indices:
            return
            
        self.push_history()
        
        # Sort indices in reverse order so popping doesn't shift indices
        for idx in sorted(self.selected_indices, reverse=True):
            if 0 <= idx < len(self.points):
                self.points.pop(idx)
                
        self.selected_indices.clear()
        self.pointsChanged.emit(self.points)
        self.selectionChanged.emit(-1)
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

    def rotate_ngon(self, angle_degrees):
        """Otočí aktívny n-uholník o špecifikovaný uhol v stupňoch."""
        if len(self.points) < 2:
            return
            
        self.push_history()
        
        min_x = min(p.x() for p in self.points)
        max_x = max(p.x() for p in self.points)
        min_y = min(p.y() for p in self.points)
        max_y = max(p.y() for p in self.points)
        center = QPointF((min_x + max_x) / 2, (min_y + max_y) / 2)
        
        rad_angle = math.radians(angle_degrees)
        cos_a = math.cos(rad_angle)
        sin_a = math.sin(rad_angle)
        
        for i, pt in enumerate(self.points):
            dx = pt.x() - center.x()
            dy = pt.y() - center.y()
            new_x = center.x() + dx * cos_a - dy * sin_a
            new_y = center.y() + dx * sin_a + dy * cos_a
            self.points[i] = QPointF(new_x, new_y)
            
        self.pointsChanged.emit(self.points)
        self.update()

    def flip_ngon(self, horizontal=True, vertical=False):
        """Preklopí aktívny n-uholník horizontálne alebo vertikálne."""
        if len(self.points) < 2:
            return
            
        self.push_history()
            
        min_x = min(p.x() for p in self.points)
        max_x = max(p.x() for p in self.points)
        min_y = min(p.y() for p in self.points)
        max_y = max(p.y() for p in self.points)
        center = QPointF((min_x + max_x) / 2, (min_y + max_y) / 2)
        
        for i, pt in enumerate(self.points):
            new_x = pt.x()
            new_y = pt.y()
            if horizontal:
                new_x = center.x() - (pt.x() - center.x())
            if vertical:
                new_y = center.y() - (pt.y() - center.y())
            self.points[i] = QPointF(new_x, new_y)
            
        self.pointsChanged.emit(self.points)
        self.update()

