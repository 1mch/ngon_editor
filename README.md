================================================================================
                                  NGon Editor
================================================================================

NGon Editor je špecializovaný vizuálny nástroj napísaný v jazyku Python 
(PySide6), určený na presné definovanie bodov n-uholníkov (polygonov). Aplikácia 
poskytuje intuitívne grafické rozhranie s matematickým súradnicovým systémom, 
mriežkou a exportom do JavaScriptu v reálnom čase.


🚀 POŽIADAVKY A INŠTALÁCIA
--------------------------------------------------------------------------------
Pre spustenie aplikácie potrebujete mať nainštalovaný Python 3.7+ a knižnicu PySide6.

1. Nainštalujte závislosti:
   pip install PySide6

2. Spustite aplikáciu:
   python ngon_editor.py


🛠 OVLÁDANIE A KLÁVESOVÉ SKRATKY
--------------------------------------------------------------------------------
Aplikácia je navrhnutá pre rýchlu prácu pomocou myši a klávesnice.

[ Manipulácia s bodmi a hranami ]
* Pridanie nového bodu     -> Ctrl + Ľavé tlačidlo myši na prázdne miesto
* Vloženie bodu do čiary   -> Ctrl + Ľavé tlačidlo myši na zvýraznenú čiaru
* Výber bodu / čiary       -> Ľavé tlačidlo myši
* Presun bodu / čiary      -> Kliknúť a ťahať Ľavým tlačidlom myši
* Odstránenie bodu         -> Vybrať bod a stlačiť klávesu Delete

[ Pohyb po plátne (Canvas) ]
* Zoom (Priblíženie)       -> Koliesko myši (centruje sa na kurzor)
* Panning (Posun plochy)   -> Stredné tlačidlo myši ALEBO Alt + Ľavé tlačidlo myši


📐 FUNKCIE EDITORA
--------------------------------------------------------------------------------

1. Dynamická mriežka a Snapping
   - Súradnice: Bod [0, 0] sa nachádza presne v strede plátna.
   - Vizuálne vrstvy: Mriežka je rozdelená na 1-jednotkovú (svetlá), 
     5-jednotkovú a 10-jednotkovú (tmavšia).
   - Auto-skrývanie: Pri veľkom oddialení (Zoom Out) sa husté mriežky 
     (1x a 5x) automaticky skryjú, aby zostal obraz prehľadný.
   - Prichytávanie (Snap): Body môžete prichytávať k celočíselnej mriežke 
     nezávisle pre os X a Y.

2. Vizuálna spätná väzba
   - Žltá farba: Indikuje prvok (bod alebo hranu) pod kurzorom (Hover).
   - Oranžová farba: Indikuje aktuálne vybraný prvok (Selection).
   - Farebný prechod (Gradient): Posledná čiara, ktorá uzatvára n-gon, 
     prechádza do červenej farby, aby bol jasný smer cesty.

3. Bezpečná zóna (Safe Region)
   - V pravom paneli môžete aktivovať "Safe Region". Po zadaní hodnôt 
     pre Left, Right, Up a Down sa na plátne vykreslí pomocný oranžový 
     obdĺžnik, ktorý slúži ako vizuálne vodítko pre vaše limity.

4. Outliner a Export
   - Outliner: Zoznam bodov na pravej strane umožňuje rýchlu navigáciu. 
     Kliknutím v zozname vyberiete bod na plátne.
   - JS Výstup: Druhá záložka (Tab) obsahuje automaticky generovaný kód 
     JavaScriptu, ktorý môžete priamo skopírovať do svojho projektu.


⚙️ KONFIGURÁCIA (V KÓDE)
--------------------------------------------------------------------------------
V triede `NGonCanvas` v premennej `self.CONFIG` môžete upraviť:

* MAX_ZOOM_IN: Maximálne povolené priblíženie.
* MAX_ZOOM_OUT: Maximálne povolené oddialenie.
* GRID_SUB_THRESHOLD: Hladina zoomu, pod ktorou zmizne jemná mriežka.

--------------------------------------------------------------------------------
Vytvorené pre efektívny workflow pri vývoji webových a herných aplikácií.