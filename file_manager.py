import re
import json
from PySide6.QtWidgets import QFileDialog, QMessageBox
from PySide6.QtCore import QPointF
from translations import tr

def save_ngon_to_js(parent, all_ngons, filepath=None):
    """
    Uloží zoznam VŠETKÝCH n-uholníkov do JavaScript súboru vo formáte:
    const ngons = [
        [ { "x": 10.0, "y": 20.0 }, ... ],
        [ { "x": 30.0, "y": 40.0 }, ... ]
    ];
    """
    # Overíme, či aspoň jeden n-uholník obsahuje nejaké body
    has_points = any(len(ngon) > 0 for ngon in all_ngons) if all_ngons else False
    if not has_points:
        QMessageBox.warning(parent, tr("msg_warn_title"), tr("msg_warn_no_points"))
        return False

    if not filepath:
        filepath, _ = QFileDialog.getSaveFileName(
            parent,
            tr("msg_save_dialog"),
            "",
            tr("msg_file_filter")
        )
    
    if not filepath:
        return False

    try:
        # Transformujeme 2D pole QPointF objektov do čistého JSON formátu
        json_data = []
        for ngon in all_ngons:
            ngon_data = [{"x": round(pt.x(), 2), "y": round(pt.y(), 2)} for pt in ngon]
            json_data.append(ngon_data)

        # Uložíme ako pole polí (const ngons)
        js_content = f"const ngons = {json.dumps(json_data, indent=4)};\n"

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(js_content)
            
        QMessageBox.information(parent, tr("msg_success_title"), tr("msg_success_save", filepath=filepath))
        return True
    except Exception as e:
        QMessageBox.critical(parent, tr("msg_err_title"), tr("msg_err_save", e=str(e)))
        return False

def import_ngon_from_js(parent):
    """
    Otvorí dialóg, načíta dáta VŠETKÝCH n-uholníkov zo súboru a vráti 2D zoznam objektov QPointF.
    V prípade chyby alebo zrušenia vráti None.
    """
    filepath, _ = QFileDialog.getOpenFileName(
        parent,
        tr("msg_import_dialog"),
        "",
        tr("msg_file_filter")
    )

    if not filepath:
        return None

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Vyhľadá pole polí priradené do premennej (napr. const ngons = [ ... ])
        # Hľadá od prvého znaku '[' až po posledný znak ']'
        match = re.search(r'=\s*(\[.*\])', content, re.DOTALL)
        if not match:
            # Fallback, ak chýba priradenie cez "="
            match = re.search(r'(\[.*\])', content, re.DOTALL)

        if not match:
            raise ValueError("V súbore sa nenašlo validné JavaScript pole (formát: [[...], [...]]).")

        raw_json = match.group(1)
        
        # Ošetrenie chýbajúcich úvodzoviek pri kľúčoch (x:, y:) v JS
        raw_json = re.sub(r'(\s*?)(\w+)(\s*:\s*)', r'\1"\2"\3', raw_json)

        data = json.loads(raw_json)
        
        if not isinstance(data, list):
            raise ValueError("Dáta v súbore musia byť vo forme hlavného poľa.")

        all_ngons = []
        
        for ngon_idx, ngon_item in enumerate(data):
            # Ak by bol náhodou starý súbor exportovaný len ako 1D pole (kompatibilita),
            # alebo ak ide o správne vnorené pole:
            if isinstance(ngon_item, list):
                points = []
                for pt_idx, item in enumerate(ngon_item):
                    if "x" not in item or "y" not in item:
                        raise ValueError(f"Tvar {ngon_idx}, bod {pt_idx} neobsahuje súradnice 'x' a 'y'.")
                    points.append(QPointF(float(item["x"]), float(item["y"])))
                all_ngons.append(points)
            else:
                # Spätná kompatibilita: Ak importujeme starý súbor, kde bol len 1 tvar (nie pole polí)
                if ngon_idx == 0 and isinstance(ngon_item, dict) and "x" in ngon_item:
                    # Spracujeme súbor ako jeden jediný n-uholník
                    points = []
                    for item in data:
                        points.append(QPointF(float(item["x"]), float(item["y"])))
                    return [points]
                raise ValueError(f"Prvok na indexe {ngon_idx} nie je platné pole bodov tvaru.")

        return all_ngons

    except Exception as e:
        QMessageBox.critical(parent, tr("msg_err_title"), tr("msg_err_import", e=str(e)))
        return None