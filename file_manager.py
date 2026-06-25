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

def export_ngon_to_svg(parent, all_ngons, filepath=None):
    if not any(len(ngon) > 0 for ngon in all_ngons):
        QMessageBox.warning(parent, tr("msg_warn_title"), "Nemáte žiadne body pre export.")
        return False

    if not filepath:
        filepath, _ = QFileDialog.getSaveFileName(parent, "Exportovať do SVG", "", "SVG Image (*.svg)")
    
    if not filepath:
        return False

    try:
        # Determine bounding box
        min_x = min_y = float('inf')
        max_x = max_y = float('-inf')
        for ngon in all_ngons:
            for pt in ngon:
                min_x = min(min_x, pt.x())
                min_y = min(min_y, pt.y())
                max_x = max(max_x, pt.x())
                max_y = max(max_y, pt.y())
        
        # Add padding
        padding = 20
        width = max_x - min_x + padding * 2
        height = max_y - min_y + padding * 2
        
        svg_content = f'<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
        svg_content += f'<svg viewBox="{min_x - padding} {min_y - padding} {width} {height}" xmlns="http://www.w3.org/2000/svg">\n'
        
        colors = ["#ff5555", "#55ff55", "#5555ff", "#ffff55", "#ff55ff", "#55ffff"]
        
        for i, ngon in enumerate(all_ngons):
            if not ngon: continue
            points_str = " ".join([f"{pt.x()},{pt.y()}" for pt in ngon])
            color = colors[i % len(colors)]
            svg_content += f'  <polygon points="{points_str}" fill="{color}" fill-opacity="0.5" stroke="{color}" stroke-width="2"/>\n'
            
        svg_content += '</svg>'
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(svg_content)
            
        QMessageBox.information(parent, "Úspech", f"SVG úspešne uložené do:\n{filepath}")
        return True
    except Exception as e:
        QMessageBox.critical(parent, "Chyba", f"Nepodarilo sa exportovať do SVG:\n{str(e)}")
        return False

def save_project(parent, canvas, filepath=None):
    if not filepath:
        filepath, _ = QFileDialog.getSaveFileName(parent, "Uložiť projekt", "", "NGon Project (*.ngon *.json)")
        
    if not filepath:
        return False
        
    try:
        # Build JSON data
        data = {
            "version": 1.0,
            "ngons": [
                [{"x": pt.x(), "y": pt.y()} for pt in ngon] for ngon in canvas.ngons
            ],
            "canvas": {
                "bg_opacity": canvas.bg_opacity,
                "bg_width_auto": canvas.bg_width_auto,
                "bg_width": canvas.bg_width,
                "bg_height_auto": canvas.bg_height_auto,
                "bg_height": canvas.bg_height,
                "bg_center_x": canvas.bg_center_x,
                "bg_center_y": canvas.bg_center_y,
                "bg_offset": {"x": canvas.bg_offset.x(), "y": canvas.bg_offset.y()},
                "safe_enabled": canvas.safe_enabled,
                "safe_l": canvas.safe_l,
                "safe_r": canvas.safe_r,
                "safe_u": canvas.safe_u,
                "safe_d": canvas.safe_d,
                "snap_x": canvas.snap_x,
                "snap_y": canvas.snap_y,
                "show_grid": canvas.show_grid,
                "show_axes": canvas.show_axes,
                "show_coords": canvas.show_coords
            }
        }
        
        # Save image as absolute path if exists
        if canvas.bg_image:
            # We would need original path. Since we didn't store it, we'll skip image path saving or we would have to store base64.
            # Let's use base64 since it's robust and QImage supports it.
            import io
            from PySide6.QtCore import QByteArray, QBuffer, QIODevice
            ba = QByteArray()
            buffer = QBuffer(ba)
            buffer.open(QIODevice.WriteOnly)
            canvas.bg_image.save(buffer, "PNG")
            data["canvas"]["bg_image_base64"] = ba.toBase64().data().decode('utf-8')
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
            
        QMessageBox.information(parent, "Úspech", f"Projekt úspešne uložený do:\n{filepath}")
        return True
    except Exception as e:
        QMessageBox.critical(parent, "Chyba", f"Nepodarilo sa uložiť projekt:\n{str(e)}")
        return False

def load_project(parent, filepath=None):
    if not filepath:
        filepath, _ = QFileDialog.getOpenFileName(parent, "Načítať projekt", "", "NGon Project (*.ngon *.json)")
        
    if not filepath:
        return None
        
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        if "version" not in data or "ngons" not in data:
            raise ValueError("Neplatný formát projektového súboru.")
            
        # Parse ngons
        all_ngons = []
        for ngon_data in data["ngons"]:
            points = [QPointF(float(pt["x"]), float(pt["y"])) for pt in ngon_data]
            all_ngons.append(points)
            
        canvas_data = data.get("canvas", {})
        
        # Check base64 image
        bg_image = None
        if "bg_image_base64" in canvas_data:
            from PySide6.QtGui import QImage
            from PySide6.QtCore import QByteArray
            ba = QByteArray.fromBase64(canvas_data["bg_image_base64"].encode('utf-8'))
            bg_image = QImage.fromData(ba, "PNG")
            
        return {
            "ngons": all_ngons,
            "canvas_data": canvas_data,
            "bg_image": bg_image
        }
        
    except Exception as e:
        QMessageBox.critical(parent, "Chyba", f"Nepodarilo sa načítať projekt:\n{str(e)}")
        return None