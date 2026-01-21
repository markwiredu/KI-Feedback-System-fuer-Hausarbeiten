"""
Hauptmodul der WriteWise-Anwendung - KI-gestütztes Feedback-System für Hausarbeiten.
Dieses Flask-basierte Webinterface ermöglicht das Hochladen und Analysieren von Dokumenten
(PDF, DOCX, TXT) sowie direkte Texteingabe zur Bewertung durch ein KI-Modul.
"""

from flask import Flask, render_template, request, jsonify
import os
import json
from datetime import datetime
import sys
import re
from docx import Document
from PyPDF2 import PdfReader

# ---------------------------
# KI-Modul Import
# ---------------------------
"""
Versucht das KI-Analysemodul zu importieren.
Bei Erfolg wird die KI-Funktionalität aktiviert, andernfalls wird Mock-Feedback verwendet.
"""
sys.path.append(os.path.dirname(__file__))
try:
    from main import analyze_hausarbeit
    KI_VERFUEGBAR = True
    print("✅ KI-Modul erfolgreich importiert")
except ImportError as e:
    print(f"⚠️ KI-Modul nicht verfügbar: {e}")
    KI_VERFUEGBAR = False

# Flask App Initialisierung
app = Flask(__name__)
"""
Maximale Dateigröße für Uploads (100 MB).
"""
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

# Erstellen erforderlicher Verzeichnisse
"""
Stellt sicher, dass alle benötigten Verzeichnisse existieren:
- uploads: Temporäre Speicherung hochgeladener Dateien
- results: Speicherung der Analyseergebnisse als JSON
- exports: Für spätere Export-Funktionen
"""
os.makedirs('uploads', exist_ok=True)
os.makedirs('results', exist_ok=True)
os.makedirs('exports', exist_ok=True)

# ---------------------------
# Text-Extraktionsfunktionen
# ---------------------------

def extract_pdf_with_pages(file):
    """
    Extrahiert Text aus PDF-Dateien mit Seiteninformationen.
    
    Args:
        file (FileStorage): Hochgeladene PDF-Datei
        
    Returns:
        str: Formatierten Text mit Seitenmarkierungen [SEITE X]
        
    Note:
        - Entfernt ungültige Zeilenumbrüche (Bindestriche)
        - Komprimiert übermäßige Leerzeichen
    """
    reader = PdfReader(file)
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text()
        if text:
            text = re.sub(r'-\n', '', text)
            text = re.sub(r'\s+', ' ', text)
            pages.append(f"[SEITE {i}] {text.strip()}")
    return "\n\n".join(pages)

def extract_text_with_chapters(text):
    """
    Strukturiert Text durch Erkennung von Kapitelüberschriften.
    
    Args:
        text (str): Roher Eingabetext
        
    Returns:
        str: Text mit Kapitelmarkierungen [KAPITEL: X.Y Titel]
        
    Pattern:
        Erkennt numerische Kapitelstrukturen (z.B. "1.2 Einleitung")
    """
    lines = text.splitlines()
    output = []
    current_chapter = "Unbekannt"
    chapter_pattern = re.compile(r'^(\d+(\.\d+)*)\s+(.+)$')

    for line in lines:
        line = line.strip()
        if not line:
            continue
        match = chapter_pattern.match(line)
        if match:
            current_chapter = f"{match.group(1)} {match.group(3)}"
            output.append(f"[KAPITEL: {current_chapter}]")
        else:
            output.append(f"[KAPITEL: {current_chapter}] {line}")
    return "\n".join(output)

def extract_text_from_file(file):
    """
    Zentrale Funktion zur Textextraktion aus verschiedenen Dateiformaten.
    
    Args:
        file (FileStorage): Hochgeladene Datei
        
    Returns:
        str: Extrahierten und strukturierten Text
        
    Raises:
        Exception: Bei nicht unterstützten Dateiformaten
        
    Supported Formats:
        - PDF: Extrahiert mit Seiteninformationen
        - DOCX/DOC: Extrahiert Kapitelstruktur
        - TXT: Basistextextraktion
    """
    filename = file.filename.lower()
    ext = os.path.splitext(filename)[1]

    file.seek(0)
    if ext == ".pdf":
        return extract_pdf_with_pages(file)
    elif ext in [".docx", ".doc"]:
        doc = Document(file)
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        return extract_text_with_chapters(text)
    elif ext == ".txt":
        text = file.read().decode("utf-8", errors="ignore")
        return extract_text_with_chapters(text)
    else:
        raise Exception("Nicht unterstütztes Format")

# ---------------------------
# Textbereinigungsfunktionen
# ---------------------------

def clean_text_for_display(text):
    """
    Bereinigt Text für die Anzeige und Analyse.
    
    Args:
        text (str): Roh- oder Extraktionstext
        
    Returns:
        str: Bereinigter Text
        
    Operations:
        - Entfernt überflüssige Leerzeichen/Tabs
        - Korrigiert Satzzeichen-Abstand
    """
    if not text:
        return ""
    text = re.sub(r'[ \t]{2,}', ' ', text)
    text = re.sub(r'\s+([.,;:!?])', r'\1', text)
    return text.strip()

# ---------------------------
# Validierungsfunktionen
# ---------------------------

def validate_text_content(text):
    """
    Validiert den Eingabetext auf Mindest- und Maximalanforderungen.
    
    Args:
        text (str): Zu validierender Text
        
    Returns:
        list: Liste mit Validierungsfehlern (leer bei Erfolg)
        
    Validation Rules:
        - Mindestens 50 Zeichen
        - Maximal 100.000 Zeichen
        - Mindestens 10 Wörter
    """
    issues = []
    if not text or len(text.strip()) < 50:
        issues.append("Text zu kurz (mindestens 50 Zeichen erforderlich)")
    if len(text) > 100000:
        issues.append("Text zu lang (maximal 100.000 Zeichen)")
    if len(text.split()) < 10:
        issues.append("Zu wenige Wörter für sinnvolle Analyse")
    return issues

# ---------------------------
# Speicherfunktionen
# ---------------------------

def save_feedback(feedback, text_preview, file_used):
    """
    Speichert Analyseergebnisse persistent als JSON-Datei.
    
    Args:
        feedback (dict): KI- oder Mock-Feedback
        text_preview (str): Vorschau des analysierten Texts (erste 200 Zeichen)
        file_used (bool): Flag ob Datei hochgeladen wurde
        
    Returns:
        str: Eindeutige Result-ID (Timestamp-basiert)
        
    File Format:
        results/YYYYMMDD_HHMMSS.json
    """
    result_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    data = {
        'id': result_id,
        'timestamp': datetime.now().isoformat(),
        'text_preview': text_preview,
        'text_length': len(text_preview),
        'file_used': file_used,
        'feedback': feedback
    }
    with open(f'results/{result_id}.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return result_id

# ---------------------------
# Mock-Feedback (Fallback)
# ---------------------------

def create_mock_feedback():
    """
    Generiert Beispiel-Feedback für Testzwecke bei fehlendem KI-Modul.
    
    Returns:
        dict: Strukturiertes Mock-Feedback mit Beispielkapiteln/Seiten
        
    Structure:
        Enthält alle Feedback-Kategorien mit Beispielreferenzen
    """
    return {
        'language_feedback': ['[KAPITEL: 1 Einleitung] Sprache verständlich'],
        'structure_feedback': ['[KAPITEL: 2 Methodik] Struktur solide'],
        'argumentation_feedback': ['[SEITE 3] Argumente nachvollziehbar'],
        'overall_summary': '[KAPITEL: Zusammenfassung] Mock-Zusammenfassung'
    }

# ---------------------------
# Flask Routes
# ---------------------------

@app.route('/')
def index():
    """
    Rendert die Hauptseite der Anwendung.
    
    Returns:
        Response: HTML-Seite des Frontends
    """
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze_text():
    """
    Hauptanalyse-Endpoint: Verarbeitet Text/Dokument und generiert Feedback.
    
    Request Types:
        - Multipart/form-data mit Dateiupload
        - Form-encoded mit direktem Text
        
    Returns:
        JSON Response: Analyseergebnisse oder Fehlermeldungen
        
    Process Flow:
        1. Extraktion aus Datei oder direkter Text
        2. Validierung
        3. Textbereinigung
        4. KI- oder Mock-Feedback
        5. Persistente Speicherung
        6. JSON-Antwort
        
    Error Handling:
        - Fehlende Eingabe
        - Validierungsfehler
        - Allgemeine Serverfehler
    """
    try:
        text = ""
        file_used = False
        file = request.files.get('file')

        # Validierung: Mindestens eine Eingabequelle
        if not file and not request.form.get('text', '').strip():
            return jsonify({'success': False, 'error': 'Bitte Text oder Datei angeben'})

        # Textextraktion aus Datei oder direkter Eingabe
        if file and file.filename:
            text = extract_text_from_file(file)
            file_used = True
        else:
            text = request.form.get('text', '').strip()
            text = extract_text_with_chapters(text)

        # Inhaltliche Validierung
        validation_issues = validate_text_content(text)
        if validation_issues:
            return jsonify({'success': False, 'error': "; ".join(validation_issues)})

        cleaned_text = clean_text_for_display(text)

        # KI-Feedback oder Fallback
        if KI_VERFUEGBAR:
            prompt_text = f"""
Bitte analysiere folgenden Text und gib Feedback. 
Jeder Punkt MUSS eine Referenz enthalten:
• [SEITE X] oder [KAPITEL: ...]
TEXT:
{cleaned_text}
"""
            feedback = analyze_hausarbeit(prompt_text)
            ki_verwendet = True
        else:
            feedback = create_mock_feedback()
            ki_verwendet = False

        # Ergebnisse speichern
        result_id = save_feedback(feedback, cleaned_text[:200], file_used)

        return jsonify({
            'success': True,
            'feedback': feedback,
            'ki_verwendet': ki_verwendet,
            'result_id': result_id,
            'text_length': len(text),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ---------------------------
# Anwendungsstart
# ---------------------------

if __name__ == '__main__':
    """
    Startet den Flask-Entwicklungsserver mit Konfiguration.
    
    Configuration:
        - Debug-Modus aktiv
        - Host: Alle Interfaces (0.0.0.0)
        - Port: 5000
        
    Console Output:
        - Anwendungsbanner
        - Server-URL
        - Import-Status des KI-Moduls
    """
    print("=" * 60)
    print("  WRITEWISE - KI-FEEDBACK FÜR HAUSARBEITEN")
    print("=" * 60)
    print(" STARTE ANWENDUNG...")
    print(f" Server: http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)