from PySide6.QtWidgets import QDialog, QFormLayout, QDoubleSpinBox, QDialogButtonBox
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

