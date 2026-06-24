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

