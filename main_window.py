import sys
from PySide6.QtWidgets import QMainWindow, QFileDialog, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QListWidget, QCheckBox, QLabel, QGroupBox, QTextEdit, QDoubleSpinBox, QGridLayout, QComboBox, QPushButton, QToolBar, QSizePolicy, QDialog
from PySide6.QtCore import Qt, QSize, QPointF
from PySide6.QtGui import QIcon, QAction, QKeyEvent, QImage
from file_manager import save_ngon_to_js, import_ngon_from_js, save_project, load_project, export_ngon_to_svg
from dialogs import CoordinateDialog, SafeZoneDialog, BackgroundDialog, FilletDialog
from canvas import NGonCanvas
from translations import tr

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(tr("window_title"))
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

        # ── MENU BAR ─────────────────────────────────────────────────────────
        menubar = self.menuBar()
        file_menu = menubar.addMenu(tr("menu_file"))
        file_menu.setTearOffEnabled(True)
        
        edit_menu = menubar.addMenu(tr("menu_edit"))
        edit_menu.setTearOffEnabled(True)
        
        view_menu = menubar.addMenu("Zobrazenie")
        view_menu.setTearOffEnabled(True)
        
        self.act_safe_zone = QAction("Bezpečná zóna", self)
        view_menu.addAction(self.act_safe_zone)
        self.act_bg_settings = QAction("Referenčný obrázok", self)
        view_menu.addAction(self.act_bg_settings)
        
        snap_menu = menubar.addMenu(tr("group_snap") if hasattr(tr, '__call__') else "Prichytávanie")
        snap_menu.setTearOffEnabled(True)
        self.act_snap_x = QAction(tr("snap_x"), self)
        self.act_snap_x.setCheckable(True)
        self.act_snap_y = QAction(tr("snap_y"), self)
        self.act_snap_y.setCheckable(True)
        self.act_snap_both = QAction(tr("snap_both"), self)
        self.act_snap_both.setCheckable(True)
        self.act_snap_int = QAction(tr("btn_snap_int"), self)
        self.act_snap_ten = QAction(tr("btn_snap_ten"), self)
        
        snap_menu.addAction(self.act_snap_x)
        snap_menu.addAction(self.act_snap_y)
        snap_menu.addAction(self.act_snap_both)
        snap_menu.addSeparator()
        snap_menu.addAction(self.act_snap_int)
        snap_menu.addAction(self.act_snap_ten)
        
        self.act_rotate_90 = QAction(tr("act_rotate_90"), self)
        self.act_rotate_180 = QAction(tr("act_rotate_180"), self)
        self.act_flip_h = QAction(tr("act_flip_h"), self)
        self.act_flip_v = QAction(tr("act_flip_v"), self)
        
        self.act_undo = QAction(tr("act_undo"), self)
        self.act_undo.setShortcut("Ctrl+Z")
        self.act_redo = QAction(tr("act_redo"), self)
        self.act_redo.setShortcut("Ctrl+Y")
        
        edit_menu.addAction(self.act_undo)
        edit_menu.addAction(self.act_redo)
        edit_menu.addSeparator()
        
        edit_menu.addAction(self.act_rotate_90)
        edit_menu.addAction(self.act_rotate_180)
        edit_menu.addAction(self.act_flip_h)
        edit_menu.addAction(self.act_flip_v)

        # ── TOOLBAR ──────────────────────────────────────────────────────────
        toolbar = QToolBar(tr("toolbar_main"))
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(16, 16))
        toolbar.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.addToolBar(Qt.TopToolBarArea, toolbar)

        # Súbor
        self.btn_import = QAction(tr("btn_import"), self)
        self.btn_import.setToolTip(tr("tooltip_import"))
        self.btn_save = QAction(tr("btn_save"), self)
        self.btn_save.setToolTip(tr("tooltip_save"))
        
        self.btn_load_project = QAction("Načítať projekt...", self)
        self.btn_save_project = QAction("Uložiť projekt...", self)
        self.btn_export_svg = QAction("Exportovať do SVG...", self)
        
        file_menu.addAction(self.btn_import)
        file_menu.addAction(self.btn_save)
        file_menu.addSeparator()
        file_menu.addAction(self.btn_load_project)
        file_menu.addAction(self.btn_save_project)
        file_menu.addSeparator()
        file_menu.addAction(self.btn_export_svg)
        
        toolbar.addSeparator()
        toolbar.addAction(self.act_undo)
        toolbar.addAction(self.act_redo)

        toolbar.addSeparator()

        # Zobrazenie – toggle akcie
        self.act_axes = QAction(tr("act_axes"), self)
        self.act_axes.setCheckable(True)
        self.act_axes.setChecked(True)
        self.act_axes.setToolTip(tr("tooltip_axes"))
        toolbar.addAction(self.act_axes)

        self.act_grid = QAction(tr("act_grid"), self)
        self.act_grid.setCheckable(True)
        self.act_grid.setChecked(True)
        self.act_grid.setToolTip(tr("tooltip_grid"))
        toolbar.addAction(self.act_grid)

        self.act_coords = QAction(tr("act_coords"), self)
        self.act_coords.setCheckable(True)
        self.act_coords.setChecked(False)
        self.act_coords.setToolTip(tr("tooltip_coords"))
        toolbar.addAction(self.act_coords)

        toolbar.addSeparator()

        # Akcie
        self.act_scale_tool = QAction(tr("act_scale_tool"), self)
        self.act_scale_tool.setCheckable(True)
        self.act_scale_tool.setChecked(False)
        self.act_scale_tool.setToolTip(tr("tooltip_scale_tool"))
        toolbar.addAction(self.act_scale_tool)
        
        self.act_rotate_tool = QAction(tr("act_rotate_tool"), self)
        self.act_rotate_tool.setCheckable(True)
        self.act_rotate_tool.setChecked(False)
        self.act_rotate_tool.setToolTip(tr("tooltip_rotate_tool"))
        toolbar.addAction(self.act_rotate_tool)

        self.act_smooth = toolbar.addAction(tr("act_smooth"))
        self.act_smooth.setToolTip(tr("tooltip_smooth"))

        self.act_fillet = toolbar.addAction("Zaobliť rohy")
        self.act_fillet.setToolTip("Zaoblí vybrané rohy")

        self.act_center = toolbar.addAction(tr("act_center"))
        self.act_center.setToolTip(tr("tooltip_center"))

        self.act_center_all = toolbar.addAction(tr("act_center_all"))
        self.act_center_all.setToolTip(tr("tooltip_center_all"))

        self.act_preview = toolbar.addAction(tr("act_preview"))
        self.act_preview.setToolTip(tr("tooltip_preview"))

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
        self.tabs.addTab(self.canvas, tr("tab_canvas"))

        self.json_view = QTextEdit()
        self.json_view.setReadOnly(True)
        self.json_view.setStyleSheet("background-color: #1e1e1e; color: #9cdcfe; font-family: 'Consolas';")
        self.tabs.addTab(self.json_view, tr("tab_json"))
        layout.addWidget(self.tabs, stretch=4)

        # ── BOČNÝ PANEL (slim) ───────────────────────────────────────────────
        right_panel = QWidget()
        right_panel.setMaximumWidth(220)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(2, 2, 2, 2)
        right_layout.setSpacing(6)
        layout.addWidget(right_panel, stretch=1)

        # Správa tvarov
        ngon_manage_group = QGroupBox(tr("group_ngon_manage"))
        ngon_manage_layout = QVBoxLayout(ngon_manage_group)
        ngon_manage_layout.setSpacing(4)

        self.ngon_list_combo = QComboBox()
        self.ngon_list_combo.addItem("Tvar 0")

        self.btn_add_ngon = QPushButton(tr("btn_add_ngon"))
        self.btn_add_ngon.setStyleSheet("""
            QPushButton { background-color: #2e7d32; color: white; font-weight: bold; border-radius: 4px; }
            QPushButton:hover { background-color: #388e3c; }
        """)
        self.btn_delete_ngon = QPushButton(tr("btn_delete_ngon"))
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
        right_layout.addWidget(QLabel(tr("label_outliner")))
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
        self.btn_load_project.triggered.connect(self.action_load_project)
        self.btn_save_project.triggered.connect(self.action_save_project)
        self.btn_export_svg.triggered.connect(self.action_export_svg)

        # Toolbar – toggle zobrazenia
        self.act_axes.toggled.connect(self._sync_axes)
        self.act_grid.toggled.connect(self._sync_grid)
        self.act_coords.toggled.connect(self._sync_coords)

        # Toolbar – akcie
        self.act_scale_tool.toggled.connect(self._sync_scale_tool)
        self.act_rotate_tool.toggled.connect(self._sync_rotate_tool)
        self.act_smooth.triggered.connect(self.smooth_all_points)
        self.act_fillet.triggered.connect(self.action_fillet)
        self.act_center.triggered.connect(lambda: self.canvas.center_view(all_ngons=False))
        self.act_center_all.triggered.connect(lambda: self.canvas.center_view(all_ngons=True))
        self.act_preview.triggered.connect(self.enable_preview)
        
        # Menu - akcie
        self.act_undo.triggered.connect(self.canvas.undo)
        self.act_redo.triggered.connect(self.canvas.redo)
        self.act_rotate_90.triggered.connect(lambda: self.canvas.rotate_ngon(90))
        self.act_rotate_180.triggered.connect(lambda: self.canvas.rotate_ngon(180))
        self.act_flip_h.triggered.connect(lambda: self.canvas.flip_ngon(horizontal=True, vertical=False))
        self.act_flip_v.triggered.connect(lambda: self.canvas.flip_ngon(horizontal=False, vertical=True))

        # Prichytávanie
        self.act_snap_x.toggled.connect(self.update_canvas_settings)
        self.act_snap_y.toggled.connect(self.update_canvas_settings)
        self.act_snap_both.toggled.connect(self.toggle_both_snap)
        self.act_snap_int.triggered.connect(self.snap_all_points_to_integer)
        self.act_snap_ten.triggered.connect(self.snap_all_points_to_ten)

        # Bezpečná zóna
        self.act_safe_zone.triggered.connect(self.open_safe_zone_dialog)
        self.act_bg_settings.triggered.connect(self.open_background_dialog)

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
        self.ngon_list_combo.addItem(tr("ngon_name", i=new_idx))
        self.ngon_list_combo.setCurrentIndex(new_idx)
        self.ngon_list_combo.blockSignals(False)
        
        self.canvas.active_ngon_idx = new_idx
        self.canvas.selected_indices.clear()
        self.canvas.selected_segment_idx = -1
        self.update_ui([])
        self.canvas.update()

    def action_delete_current_ngon(self):
        """Zmaže aktuálny n-uholník, ak to nie je jediný zostávajúci."""
        if len(self.canvas.ngons) <= 1:
            # Ak je posledný, iba ho vyčistíme
            self.canvas.ngons[0] = []
            self.canvas.selected_indices.clear()
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
            self.ngon_list_combo.addItem(tr("ngon_name", i=i))
        self.ngon_list_combo.setCurrentIndex(self.canvas.active_ngon_idx)
        self.ngon_list_combo.blockSignals(False)
        
        self.canvas.selected_indices.clear()
        self.canvas.selected_segment_idx = -1
        self.canvas.pointsChanged.emit(self.canvas.points)
        self.canvas.update()

    def action_change_active_ngon(self, index):
        """Prepne aktívny n-uholník podľa výberu v menu."""
        if 0 <= index < len(self.canvas.ngons):
            self.canvas.active_ngon_idx = index
            self.canvas.selected_indices.clear()
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
            self.canvas.selected_indices.clear()
            self.canvas.selected_segment_idx = -1
            
            # Aktualizujeme rozbaľovacie menu (ComboBox) podľa počtu načítaných tvarov
            self.ngon_list_combo.blockSignals(True)
            self.ngon_list_combo.clear()
            for i in range(len(self.canvas.ngons)):
                self.ngon_list_combo.addItem(tr("ngon_name", i=i))
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
            
        self.canvas.push_history()
        self.canvas.push_history()
        for i in range(len(self.canvas.points)):
            pt = self.canvas.points[i]
            self.canvas.points[i] = QPointF(round(pt.x()), round(pt.y()))
            
        # Oznámime aplikácii zmenu, aby sa prekreslilo plátno a aktualizoval Outliner/JSON
        self.canvas.pointsChanged.emit(self.canvas.points)
        self.canvas.update()

    def snap_all_points_to_ten(self):
        """Zaokrúhli súradnice všetkých bodov na najbližšie celé desiatky."""
        if not self.canvas.points:
            return
            
        self.canvas.push_history()
        self.canvas.push_history()
        for i in range(len(self.canvas.points)):
            pt = self.canvas.points[i]
            self.canvas.points[i] = QPointF(round(pt.x() / 10.0) * 10.0, round(pt.y() / 10.0) * 10.0)
            
        self.canvas.pointsChanged.emit(self.canvas.points)
        self.canvas.update()

    def _sync_scale_tool(self, checked):
        self.canvas.scale_mode_active = checked
        if checked:
            self.act_rotate_tool.setChecked(False)
        self.canvas.update()

    def _sync_rotate_tool(self, checked):
        self.canvas.rotate_mode_active = checked
        if checked:
            self.act_scale_tool.setChecked(False)
        self.canvas.update()

    def smooth_all_points(self):
        """Vyhladí tvar pomocou Chaikinovho algoritmu (Corner Cutting)."""
        points = self.canvas.points
        # Vyhladzovanie má zmysel len ak máme uzavretý tvar (aspoň 3 body)
        if len(points) < 3:
            return
            
        self.canvas.push_history()
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
        self.canvas.selected_indices.clear()
        self.canvas.selected_segment_idx = -1
        
        # Oznámime aplikácii zmenu (prekreslí sa Outliner a JSON)
        self.canvas.pointsChanged.emit(self.canvas.points)
        self.canvas.update()

    def update_canvas_settings(self):
        # Načítanie stavu hlavného prepínača mriežky
        self.canvas.show_grid = self.chk_grid_master.isChecked()
        self.canvas.show_axes = self.chk_axes.isChecked()
        
        self.canvas.snap_x = self.act_snap_x.isChecked()
        self.canvas.snap_y = self.act_snap_y.isChecked()

        self.canvas.show_coords = self.chk_coords.isChecked()
        
        self.canvas.update()

    def enable_preview(self):
        """Zapne režim náhľadu na plátne, ak existuje aspoň jeden vykresliteľný tvar."""
        # Overíme, či aspoň jeden n-uholník obsahuje nejaké body
        has_any_points = any(len(ngon) > 0 for ngon in self.canvas.ngons)
        
        if has_any_points:
            self.canvas.preview_mode = True
            self.tabs.setCurrentIndex(0)  # Prepnúť na plátno, ak sme v JSONe
            self.canvas.update()

    def toggle_both_snap(self, checked):
        self.act_snap_x.setChecked(checked)
        self.act_snap_y.setChecked(checked)
        self.update_canvas_settings()

    def open_coordinate_editor(self, index):
        """Otvorí okno pre manuálnu úpravu súradníc vybraného bodu."""
        if 0 <= index < len(self.canvas.points):
            # Synchronizácia výberu
            self.canvas.selected_indices = {index}
            self.sync_selection_to_ui(index)
            self.canvas.update()

            pt = self.canvas.points[index]
            dialog = CoordinateDialog(pt.x(), pt.y(), self)
            
            if dialog.exec() == QDialog.Accepted:
                self.canvas.push_history()
                new_x, new_y = dialog.get_values()
                self.canvas.points[index] = QPointF(new_x, new_y)
                
                # Emitovanie signálu spustí update_ui a prekreslenie
                self.canvas.pointsChanged.emit(self.canvas.points)
                self.canvas.update()

    def open_safe_zone_dialog(self):
        dialog = SafeZoneDialog(self.canvas.safe_enabled, self.canvas.safe_l, self.canvas.safe_r, self.canvas.safe_u, self.canvas.safe_d, self)
        if dialog.exec() == QDialog.Accepted:
            enabled, l, r, u, d = dialog.get_values()
            self.canvas.safe_enabled = enabled
            self.canvas.safe_l = l
            self.canvas.safe_r = r
            self.canvas.safe_u = u
            self.canvas.safe_d = d
            self.canvas.update()

    def update_ui(self, points):
        self.outliner.blockSignals(True)
        self.outliner.clear()
        
        # Outliner plníme len pre AKTÍVNY n-uholník
        for i, pt in enumerate(points):
            self.outliner.addItem(tr("outliner_item", i=i, x=pt.x(), y=pt.y()))
        
        if self.canvas.selected_indices:
            self.outliner.setCurrentRow(next(iter(self.canvas.selected_indices)))
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
        self.canvas.selected_indices = {index}
        self.canvas.selected_segment_idx = -1  # Výber v outlineri zruší označenie hrany (identické s kliknutím na bod)
        self.canvas.update()

    def open_background_dialog(self):
        dialog = BackgroundDialog(self)
        dialog.exec()

    def action_load_project(self):
        project_data = load_project(self)
        if project_data:
            self.canvas.ngons = project_data["ngons"]
            cd = project_data["canvas_data"]
            self.canvas.bg_opacity = cd.get("bg_opacity", 0.5)
            self.canvas.bg_width_auto = cd.get("bg_width_auto", True)
            self.canvas.bg_width = cd.get("bg_width", 500.0)
            self.canvas.bg_height_auto = cd.get("bg_height_auto", True)
            self.canvas.bg_height = cd.get("bg_height", 500.0)
            self.canvas.bg_center_x = cd.get("bg_center_x", True)
            self.canvas.bg_center_y = cd.get("bg_center_y", True)
            
            if "bg_offset" in cd:
                self.canvas.bg_offset = QPointF(cd["bg_offset"]["x"], cd["bg_offset"]["y"])
                
            self.canvas.safe_enabled = cd.get("safe_enabled", False)
            self.canvas.safe_l = cd.get("safe_l", -175.0)
            self.canvas.safe_r = cd.get("safe_r", 175.0)
            self.canvas.safe_u = cd.get("safe_u", -50.0)
            self.canvas.safe_d = cd.get("safe_d", 0.0)
            
            self.canvas.snap_x = cd.get("snap_x", False)
            self.canvas.snap_y = cd.get("snap_y", False)
            self.canvas.show_grid = cd.get("show_grid", True)
            self.canvas.show_axes = cd.get("show_axes", True)
            self.canvas.show_coords = cd.get("show_coords", False)
            
            if project_data["bg_image"]:
                self.canvas.bg_image = project_data["bg_image"]
                
            # Update UI state
            self.chk_axes.setChecked(self.canvas.show_axes)
            self.chk_grid_master.setChecked(self.canvas.show_grid)
            self.chk_coords.setChecked(self.canvas.show_coords)
            self.act_snap_x.setChecked(self.canvas.snap_x)
            self.act_snap_y.setChecked(self.canvas.snap_y)
            
            self.canvas.active_ngon_idx = 0
            self.canvas.selected_indices.clear()
            self.canvas.selected_segment_idx = -1
            
            self.ngon_list_combo.blockSignals(True)
            self.ngon_list_combo.clear()
            for i in range(len(self.canvas.ngons)):
                self.ngon_list_combo.addItem(tr("ngon_name", i=i) if hasattr(tr, '__call__') else f"Tvar {i}")
            self.ngon_list_combo.setCurrentIndex(0)
            self.ngon_list_combo.blockSignals(False)
            
            self.update_canvas_settings()
            self.update_ui(self.canvas.points)
            self.canvas.center_view(all_ngons=True)
            self.canvas.update()

    def action_save_project(self):
        save_project(self, self.canvas)
        
    def action_export_svg(self):
        export_ngon_to_svg(self, self.canvas.ngons)
        
    def action_fillet(self):
        if not self.canvas.selected_indices:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Informácia", "Vyberte aspoň jeden bod na zaoblenie (Klik na bod).")
            return
            
        dialog = FilletDialog(self)
        if dialog.exec():
            radius, segments = dialog.get_values()
            self.canvas.fillet_selected_points(radius, segments)
