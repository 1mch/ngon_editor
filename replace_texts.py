import sys
import os

def replace_in_file(filepath, replacements):
    if not os.path.exists(filepath):
        print(f"File {filepath} not found.")
        return

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # insert import
    if 'from translations import tr' not in content:
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if not line.startswith('import ') and not line.startswith('from '):
                if i > 0 and (lines[i-1].startswith('import') or lines[i-1].startswith('from')):
                    lines.insert(i, 'from translations import tr')
                    break
        content = '\n'.join(lines)
        
    for old, new in replacements:
        if old not in content:
            print(f"Warning: Could not find '{old}' in {filepath}")
        content = content.replace(old, new)
        
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

mw_reps = [
    ('menubar.addMenu("Súbor")', 'menubar.addMenu(tr("menu_file"))'),
    ('menubar.addMenu("Upraviť")', 'menubar.addMenu(tr("menu_edit"))'),
    ('QAction("Otočiť o 90°", self)', 'QAction(tr("act_rotate_90"), self)'),
    ('QAction("Otočiť o 180°", self)', 'QAction(tr("act_rotate_180"), self)'),
    ('QAction("Prevrátiť horizontálne", self)', 'QAction(tr("act_flip_h"), self)'),
    ('QAction("Prevrátiť vertikálne", self)', 'QAction(tr("act_flip_v"), self)'),
    ('QToolBar("Hlavný panel nástrojov")', 'QToolBar(tr("toolbar_main"))'),
    ('QAction("⬆ Import", self)', 'QAction(tr("btn_import"), self)'),
    ('setToolTip("Importovať tvar zo súboru JS")', 'setToolTip(tr("tooltip_import"))'),
    ('QAction("💾 Uložiť", self)', 'QAction(tr("btn_save"), self)'),
    ('setToolTip("Uložiť tvar do súboru JS")', 'setToolTip(tr("tooltip_save"))'),
    ('QAction("🗡 Osi", self)', 'QAction(tr("act_axes"), self)'),
    ('setToolTip("Zobraziť / skryť hlavné osi")', 'setToolTip(tr("tooltip_axes"))'),
    ('QAction("⊞ Mriežka", self)', 'QAction(tr("act_grid"), self)'),
    ('setToolTip("Zobraziť / skryť mriežku")', 'setToolTip(tr("tooltip_grid"))'),
    ('QAction("🔢 Coords", self)', 'QAction(tr("act_coords"), self)'),
    ('setToolTip("Zobraziť / skryť súradnice bodov")', 'setToolTip(tr("tooltip_coords"))'),
    ('QAction("⤗ Mierka", self)', 'QAction(tr("act_scale_tool"), self)'),
    ('setToolTip("Aktivovať nástroj na zmenu veľkosti (Scale Tool)")', 'setToolTip(tr("tooltip_scale_tool"))'),
    ('QAction("⟲ Otočiť", self)', 'QAction(tr("act_rotate_tool"), self)'),
    ('setToolTip("Aktivovať nástroj na voľnú rotáciu")', 'setToolTip(tr("tooltip_rotate_tool"))'),
    ('addAction("〜 Smooth")', 'addAction(tr("act_smooth"))'),
    ('setToolTip("Vyhladiť tvar (Chaikin)")', 'setToolTip(tr("tooltip_smooth"))'),
    ('addAction("⊙ Centrovať")', 'addAction(tr("act_center"))'),
    ('setToolTip("Vycentrovať pohľad na aktuálny tvar")', 'setToolTip(tr("tooltip_center"))'),
    ('addAction("⊛ Centrovať všetko")', 'addAction(tr("act_center_all"))'),
    ('setToolTip("Vycentrovať pohľad na všetky tvary")', 'setToolTip(tr("tooltip_center_all"))'),
    ('addAction("▶ Náhľad")', 'addAction(tr("act_preview"))'),
    ('setToolTip("Zobraziť vyplnený náhľad tvaru")', 'setToolTip(tr("tooltip_preview"))'),
    ('addTab(self.canvas, "Návrhové plátno")', 'addTab(self.canvas, tr("tab_canvas"))'),
    ('addTab(self.json_view, "JavaScript výstup")', 'addTab(self.json_view, tr("tab_json"))'),
    ('QGroupBox("Prichytávanie (Snap)")', 'QGroupBox(tr("group_snap"))'),
    ('QCheckBox("Snap X")', 'QCheckBox(tr("snap_x"))'),
    ('QCheckBox("Snap Y")', 'QCheckBox(tr("snap_y"))'),
    ('QCheckBox("Snap X+Y")', 'QCheckBox(tr("snap_both"))'),
    ('QPushButton("Prichytiť na celé čísla")', 'QPushButton(tr("btn_snap_int"))'),
    ('QPushButton("Prichytiť na celé desiatky")', 'QPushButton(tr("btn_snap_ten"))'),
    ('QGroupBox("Bezpečná zóna")', 'QGroupBox(tr("group_safe"))'),
    ('QCheckBox("Povoliť")', 'QCheckBox(tr("chk_safe_enable"))'),
    ('QGroupBox("Správa tvarov")', 'QGroupBox(tr("group_ngon_manage"))'),
    ('QPushButton("+ Pridať tvar")', 'QPushButton(tr("btn_add_ngon"))'),
    ('QPushButton("✕ Zmazať tvar")', 'QPushButton(tr("btn_delete_ngon"))'),
    ('QLabel("Body (Outliner):")', 'QLabel(tr("label_outliner"))'),
    ('addItem(f"Tvar {new_idx}")', 'addItem(tr("ngon_name", i=new_idx))'),
    ('addItem(f"Tvar {i}")', 'addItem(tr("ngon_name", i=i))'),
    ('addItem(f"Bod {i}: [{pt.x():.1f}, {pt.y():.1f}]")', 'addItem(tr("outliner_item", i=i, x=pt.x(), y=pt.y()))'),
    ('setWindowTitle("NGon Editor")', 'setWindowTitle(tr("window_title"))')
]

fm_reps = [
    ('QMessageBox.warning(parent, "Upozornenie", "Nie je čo uložiť. Žiadny n-uholník neobsahuje body.")',
     'QMessageBox.warning(parent, tr("msg_warn_title"), tr("msg_warn_no_points"))'),
    ('"Uložiť JavaScript výstup",', 'tr("msg_save_dialog"),'),
    ('"JavaScript súbory (*.js);;Všetky súbory (*)"', 'tr("msg_file_filter")'),
    ('QMessageBox.information(parent, "Úspech", f"Všetky tvary boli úspešne uložené do:\\n{filepath}")',
     'QMessageBox.information(parent, tr("msg_success_title"), tr("msg_success_save", filepath=filepath))'),
    ('QMessageBox.critical(parent, "Chyba", f"Nepodarilo sa uložiť súbor:\\n{str(e)}")',
     'QMessageBox.critical(parent, tr("msg_err_title"), tr("msg_err_save", e=str(e)))'),
    ('"Importovať JavaScript výstup",', 'tr("msg_import_dialog"),'),
    ('QMessageBox.critical(parent, "Chyba", "Súbor nemá podporovaný formát n-uholníkov.")',
     'QMessageBox.critical(parent, tr("msg_err_title"), tr("msg_err_format"))'),
    ('QMessageBox.critical(parent, "Chyba", f"Nepodarilo sa načítať súbor:\\n{str(e)}")',
     'QMessageBox.critical(parent, tr("msg_err_title"), tr("msg_err_import", e=str(e)))')
]

dl_reps = [
    ('setWindowTitle("Upraviť súradnice bodu")', 'setWindowTitle(tr("dialog_coord_title"))'),
    ('QLabel("Súradnica X:")', 'QLabel(tr("dialog_coord_x"))'),
    ('QLabel("Súradnica Y:")', 'QLabel(tr("dialog_coord_y"))')
]

replace_in_file(r"c:\0_dev\ngon_editor_app\main_window.py", mw_reps)
replace_in_file(r"c:\0_dev\ngon_editor_app\file_manager.py", fm_reps)
replace_in_file(r"c:\0_dev\ngon_editor_app\dialogs.py", dl_reps)
print("Replacement script finished.")
