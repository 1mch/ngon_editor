import re
import json
from PySide6.QtWidgets import QFileDialog, QMessageBox
from PySide6.QtCore import QPointF

def save_ngon_to_js(parent, points, filepath=None):
    """
    Uloží zoznam bodov (QPointF) do JavaScript súboru vo formáte:
    const ngon = [
        { "x": 10.0, "y": 20.0 },
        ...
    ];
    
    Ak 'filepath' nie je definovaný, otvorí sa štandardný ukladací dialóg.
    """
    if not points:
        QMessageBox.warning(parent, "Upozornenie", "Nie je čo uložiť. N-uholník neobsahuje žiadne body.")
        return False

    if not filepath:
        filepath, _ = QFileDialog.getSaveFileName(
            parent,
            "Uložiť JavaScript výstup",
            "",
            "JavaScript súbory (*.js);;Všetky súbory (*)"
        )
    
    if not filepath:
        return False  # Používateľ zrušil dialóg

    try:
        # Príprava dát do formátu JSON kompatibilného s JS
        json_data = [{"x": round(pt.x(), 2), "y": round(pt.y(), 2)} for pt in points]
        js_content = f"const ngon = {json.dumps(json_data, indent=4)};\n"

        # Zápis do súboru
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(js_content)
            
        QMessageBox.information(parent, "Úspech", f"N-uholník bol úspešne uložený do:\n{filepath}")
        return True
    except Exception as e:
        QMessageBox.critical(parent, "Chyba", f"Nepodarilo sa uložiť súbor:\n{str(e)}")
        return False

def import_ngon_from_js(parent):
    """
    Otvorí dialóg na výber JS súboru, načíta dáta n-uholníka a vráti zoznam objektov QPointF.
    Podporuje flexibilný import pomocou regulárnych výrazov na extrakciu JSON/JS poľa.
    V prípade chyby alebo zrušenia vráti None.
    """
    filepath, _ = QFileDialog.getOpenFileName(
        parent,
        "Importovať n-uholník z JavaScriptu",
        "",
        "JavaScript súbory (*.js);;Všetky súbory (*)"
    )

    if not filepath:
        return None

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Regulárny výraz vyhľadá pole objektov [ ... ] v súbore.
        # Odstráni priradenie "const ngon =" a vyextrahuje čistú textovú reprezentáciu poľa.
        match = re.search(r'=\s*(\[\s*\{.*?\}\s*\])', content, re.DOTALL)
        if not match:
            # Ak chýba "const ngon =", skúsime vyhľadať akékoľvek pole objektov
            match = re.search(r'(\[\s*\{.*?\}\s*\])', content, re.DOTALL)

        if not match:
            raise ValueError("V súbore sa nenašlo validné JavaScript pole s bodmi (formát: [{...}, {...}]).")

        raw_json = match.group(1)
        
        # Ošetrenie prípadných drobných rozdielov v JS zápise (napr. chýbajúce úvodzovky pri kľúčoch)
        # Prevedieme kľúče bez úvodzoviek na štandardný JSON formát
        raw_json = re.sub(r'(\s*?)(\w+)(\s*:\s*)', r'\1"\2"\3', raw_json)

        data = json.loads(raw_json)
        
        if not isinstance(data, list):
            raise ValueError("Dáta v súbore musia byť vo forme poľa.")

        points = []
        for i, item in enumerate(data):
            if "x" not in item or "y" not in item:
                raise ValueError(f"Bod na indexe {i} neobsahuje povinné súradnice 'x' a 'y'.")
            points.append(QPointF(float(item["x"]), float(item["y"])))

        return points

    except Exception as e:
        QMessageBox.critical(parent, "Chyba pri importe", f"Nepodarilo sa načítať body zo súboru:\n{str(e)}")
        return None