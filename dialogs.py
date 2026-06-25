from PySide6.QtWidgets import QDialog, QFormLayout, QDoubleSpinBox, QDialogButtonBox, QCheckBox, QPushButton, QLabel, QHBoxLayout, QFileDialog
from translations import tr

class CoordinateDialog(QDialog):
    def __init__(self, x, y, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("dialog_coord_title"))
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

        layout.addRow(tr("dialog_coord_x"), self.spn_x)
        layout.addRow(tr("dialog_coord_y"), self.spn_y)

        # Štandardné tlačidlá OK a Zrušiť
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addRow(self.buttons)

    def get_values(self):
        """Vráti nastavené hodnoty X a Y."""
        return self.spn_x.value(), self.spn_y.value()


class SafeZoneDialog(QDialog):
    def __init__(self, enabled, l, r, u, d, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("group_safe") if hasattr(tr, '__call__') else "Bezpečná zóna")
        self.setMinimumWidth(250)
        
        from PySide6.QtWidgets import QCheckBox
        layout = QFormLayout(self)

        self.chk_enable = QCheckBox(tr("chk_safe_enable") if hasattr(tr, '__call__') else "Zobraziť bezpečnú zónu")
        self.chk_enable.setChecked(enabled)
        layout.addRow(self.chk_enable)

        self.spn_l = QDoubleSpinBox()
        self.spn_l.setRange(-10000, 10000)
        self.spn_l.setValue(l)
        
        self.spn_r = QDoubleSpinBox()
        self.spn_r.setRange(-10000, 10000)
        self.spn_r.setValue(r)
        
        self.spn_u = QDoubleSpinBox()
        self.spn_u.setRange(-10000, 10000)
        self.spn_u.setValue(u)
        
        self.spn_d = QDoubleSpinBox()
        self.spn_d.setRange(-10000, 10000)
        self.spn_d.setValue(d)

        layout.addRow("L:", self.spn_l)
        layout.addRow("R:", self.spn_r)
        layout.addRow("U:", self.spn_u)
        layout.addRow("D:", self.spn_d)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addRow(self.buttons)

    def get_values(self):
        return self.chk_enable.isChecked(), self.spn_l.value(), self.spn_r.value(), self.spn_u.value(), self.spn_d.value()

class BackgroundDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("group_bg") if hasattr(tr, '__call__') else "Referenčný obrázok")
        self.setMinimumWidth(300)
        
        self.canvas = parent.canvas if parent else None
        layout = QFormLayout(self)
        
        btn_layout = QHBoxLayout()
        self.btn_load = QPushButton(tr("btn_load_bg") if hasattr(tr, '__call__') else "Načítať obrázok")
        self.btn_clear = QPushButton(tr("btn_clear_bg") if hasattr(tr, '__call__') else "Vyčistiť obrázok")
        btn_layout.addWidget(self.btn_load)
        btn_layout.addWidget(self.btn_clear)
        layout.addRow(btn_layout)
        
        self.lbl_status = QLabel("Obrázok: Nenačítaný" if not (self.canvas and self.canvas.bg_image) else "Obrázok: Načítaný")
        layout.addRow(self.lbl_status)
        
        self.spn_opacity = QDoubleSpinBox()
        self.spn_opacity.setRange(0.0, 1.0)
        self.spn_opacity.setSingleStep(0.1)
        self.spn_opacity.setValue(self.canvas.bg_opacity if self.canvas else 0.5)
        layout.addRow("Priehľadnosť:", self.spn_opacity)
        
        w_layout = QHBoxLayout()
        self.spn_w = QDoubleSpinBox()
        self.spn_w.setRange(1.0, 10000.0)
        self.spn_w.setValue(self.canvas.bg_width if self.canvas else 500.0)
        self.chk_w_auto = QCheckBox("Auto")
        self.chk_w_auto.setChecked(self.canvas.bg_width_auto if self.canvas else True)
        self.spn_w.setEnabled(not self.chk_w_auto.isChecked())
        self.chk_w_auto.stateChanged.connect(lambda: self.spn_w.setEnabled(not self.chk_w_auto.isChecked()))
        w_layout.addWidget(self.spn_w)
        w_layout.addWidget(self.chk_w_auto)
        layout.addRow("Šírka (px):", w_layout)
        
        h_layout = QHBoxLayout()
        self.spn_h = QDoubleSpinBox()
        self.spn_h.setRange(1.0, 10000.0)
        self.spn_h.setValue(self.canvas.bg_height if self.canvas else 500.0)
        self.chk_h_auto = QCheckBox("Auto")
        self.chk_h_auto.setChecked(self.canvas.bg_height_auto if self.canvas else True)
        self.spn_h.setEnabled(not self.chk_h_auto.isChecked())
        self.chk_h_auto.stateChanged.connect(lambda: self.spn_h.setEnabled(not self.chk_h_auto.isChecked()))
        h_layout.addWidget(self.spn_h)
        h_layout.addWidget(self.chk_h_auto)
        layout.addRow("Výška (px):", h_layout)
        
        self.chk_center_x = QCheckBox("Vycentrovať horizontálne")
        self.chk_center_x.setChecked(self.canvas.bg_center_x if self.canvas else True)
        self.chk_center_y = QCheckBox("Vycentrovať vertikálne")
        self.chk_center_y.setChecked(self.canvas.bg_center_y if self.canvas else True)
        layout.addRow(self.chk_center_x)
        layout.addRow(self.chk_center_y)
        
        self.spn_off_x = QDoubleSpinBox()
        self.spn_off_x.setRange(-10000.0, 10000.0)
        self.spn_off_x.setValue(self.canvas.bg_offset.x() if self.canvas else 0.0)
        self.spn_off_y = QDoubleSpinBox()
        self.spn_off_y.setRange(-10000.0, 10000.0)
        self.spn_off_y.setValue(self.canvas.bg_offset.y() if self.canvas else 0.0)
        layout.addRow("Offset X:", self.spn_off_x)
        layout.addRow("Offset Y:", self.spn_off_y)

        self.btn_load.clicked.connect(self.load_image)
        self.btn_clear.clicked.connect(self.clear_image)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addRow(self.buttons)

    def load_image(self):
        from PySide6.QtGui import QImage
        filepath, _ = QFileDialog.getOpenFileName(self, "Načítať obrázok", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if filepath and self.canvas:
            img = QImage(filepath)
            if not img.isNull():
                self.canvas.bg_image = img
                self.lbl_status.setText("Obrázok: Načítaný")
                self.canvas.update()

    def clear_image(self):
        if self.canvas:
            self.canvas.bg_image = None
            self.lbl_status.setText("Obrázok: Nenačítaný")
            self.canvas.update()

    def accept(self):
        if self.canvas:
            self.canvas.bg_opacity = self.spn_opacity.value()
            self.canvas.bg_width_auto = self.chk_w_auto.isChecked()
            self.canvas.bg_width = self.spn_w.value()
            self.canvas.bg_height_auto = self.chk_h_auto.isChecked()
            self.canvas.bg_height = self.spn_h.value()
            self.canvas.bg_center_x = self.chk_center_x.isChecked()
            self.canvas.bg_center_y = self.chk_center_y.isChecked()
            
            from PySide6.QtCore import QPointF
            self.canvas.bg_offset = QPointF(self.spn_off_x.value(), self.spn_off_y.value())
            self.canvas.update()
            
        super().accept()


class FilletDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("dialog_fillet_title") if hasattr(tr, '__call__') else "Zaobliť rohy")
        self.setMinimumWidth(250)
        
        layout = QFormLayout(self)
        
        self.spn_radius = QDoubleSpinBox()
        self.spn_radius.setRange(0.1, 1000.0)
        self.spn_radius.setValue(10.0)
        self.spn_radius.setDecimals(1)
        self.spn_radius.setSingleStep(1.0)
        
        self.spn_segments = QDoubleSpinBox()
        self.spn_segments.setRange(2, 64)
        self.spn_segments.setValue(5)
        self.spn_segments.setDecimals(0)
        
        layout.addRow("Polomer (vzdialenosť):", self.spn_radius)
        layout.addRow("Počet segmentov:", self.spn_segments)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addRow(self.buttons)

    def get_values(self):
        return self.spn_radius.value(), int(self.spn_segments.value())
