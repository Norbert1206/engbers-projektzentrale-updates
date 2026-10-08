# Ausgabearchitektur

Originalquelle: js/print.js, Funktion buildPdfHtml().

Originale Fachblattgruppen: 01 Projekt/KPIs; 02 System; 03 Stahl; 04 Holz; 05 Erddruck; 06 Bishop-Grafik; 07 Bishop-Nachweis; 08 Zusammenfassung.

Nächster Umbau: buildPdfHtml() öffentlich für den Viewer verfügbar machen, identische HTML-Quelle für PDF und Viewer; keine DOM-Heuristik. Skalierungsformel widthScale=718/srcWidth, heightScale=1047/h ist vor Layoutfreigabe zu prüfen. Keine Änderung an retaining_wall_core.js.
