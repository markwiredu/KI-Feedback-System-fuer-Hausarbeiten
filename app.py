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
from flask import Flask, render_template, request, jsonify, send_file
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch


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


"""Initialisiert die Flask-Webanwendung."""
app = Flask(__name__)


"""
Definiert die maximale Dateigröße für Uploads.

Standard: 100 MB
"""
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024


"""
Erstellt alle notwendigen Verzeichnisse für die Anwendung.

Verzeichnisse:
    - uploads: temporäre Speicherung hochgeladener Dateien
    - results: Speicherung der Analyseergebnisse als JSON
    - exports: Exportierte Feedback-Dateien (TXT/PDF)
"""
os.makedirs('uploads', exist_ok=True)
os.makedirs('results', exist_ok=True)
os.makedirs('exports', exist_ok=True)

# ---------------------------
# Text-Extraktionsfunktionen
# ---------------------------


def extract_pdf_with_pages(file):
    """
    Extrahiert Text aus einer PDF-Datei und versieht ihn mit Seitenmarkierungen.

    Args:
        file (FileStorage): Hochgeladene PDF-Datei.

    Returns:
        str: Formatierter Text mit Seitenmarkierungen im Format: "[SEITE X]".

    Notes:
        - Entfernt Trennstriche am Zeilenende ("-\\n").
        - Komprimiert mehrere Leerzeichen zu einem.
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
    Strukturiert Text, indem Kapitelüberschriften automatisch erkannt werden.

    Args:
        text (str): Eingabetext als String.

    Returns:
        str: Text mit Kapitelmarkierungen im Format: "[KAPITEL: X.Y Titel]".

    Pattern:
        Erkennt numerische Kapitelstrukturen wie z.B. "1.2 Einleitung".
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
    Extrahiert Text aus verschiedenen Dateiformaten und strukturiert ihn.

    Args:
        file (FileStorage): Hochgeladene Datei.

    Returns:
        str: Extrahierter und strukturierter Text.

    Raises:
        Exception: Wenn ein nicht unterstütztes Dateiformat hochgeladen wird.

    Supported formats:
        - PDF: Text wird mit Seitenreferenzen extrahiert.
        - DOCX/DOC: Text wird extrahiert und mit Kapiteln strukturiert.
        - TXT: Text wird gelesen und mit Kapiteln strukturiert.
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
    Bereinigt Text für Anzeige und Analyse.

    Args:
        text (str): Eingabetext (Rohtext oder extrahierter Inhalt).

    Returns:
        str: Bereinigter Text.

    Operations:
        - Entfernt doppelte Leerzeichen und Tabs.
        - Korrigiert Abstände vor Satzzeichen.
        - Ersetzt Aufzählungszeichen (■▪•) durch "-".
        - Normalisiert Bindestriche.
    """
    if not text:
        return ""
    text = re.sub(r'[ \t]{2,}', ' ', text)
    text = re.sub(r'\s+([.,;:!?])', r'\1', text)
    text = re.sub(r'[■▪•]+', '-', text)
    text = re.sub(r'\s*-\s*', '-', text)

    return text.strip()


# ---------------------------
# Validierungsfunktionen
# ---------------------------

def validate_text_content(text):
    """
    Validiert den Eingabetext anhand Mindest- und Maximalgrenzen.

    Args:
        text (str): Zu prüfender Text.

    Returns:
        list[str]: Liste mit Validierungsfehlern (leer bei Erfolg).

    Validation rules:
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
        feedback (dict): KI- oder Mock-Feedback.
        text_preview (str): Vorschau des Textes (meist erste 200 Zeichen).
        file_used (bool): Flag ob eine Datei oder direkter Text genutzt wurde.

    Returns:
        str: Eindeutige Result-ID (Timestamp-basiert).

    File format:
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
    Erzeugt statisches Beispiel-Feedback für den Fallback-Modus.

    Returns:
        dict: Beispiel-Feedback in allen Kategorien.

    Notes:
        Wird verwendet, wenn das KI-Modul nicht importiert werden konnte.
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
    Liefert die Startseite der Webanwendung aus.

    Returns:
        Response: HTML-Template der Startseite (index.html).
    """
    return render_template('index.html')


@app.route('/analyze', methods=['POST'])
def analyze_text():
    """
    Haupt-API-Endpunkt für die Analyse von Text oder Dateien.

    Request types:
        - Multipart/form-data (Dateiupload)
        - Form-data / Textfeld (Direkteingabe)

    Returns:
        Response: JSON-Response mit Feedback oder Fehlermeldungen.

    Process:
        1. Extraktion aus Datei oder Textfeld
        2. Validierung des Inhalts
        3. Bereinigung für Anzeige/Analyse
        4. Auswertung durch KI oder Fallback (Mock)
        5. Speichern des Ergebnisses
        6. Ausgabe per JSON

    Error handling:
        - Fehlende Eingabe
        - Validierungsfehler
        - Allgemeine Exceptions
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


@app.route('/export/txt/<result_id>')
def export_txt(result_id):
    """
    Exportiert gespeichertes Feedback als TXT-Datei.

    Args:
        result_id (str): ID des gespeicherten Analyseergebnisses.

    Returns:
        Response: TXT-Datei als Download oder JSON-Fehlerantwort.
    """
    try:
        path = f"results/{result_id}.json"

        if not os.path.exists(path):
            return jsonify({'success': False, 'error': 'Ergebnis nicht gefunden'})

        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        feedback = data.get('feedback', {})

        txt = []
        txt.append("WriteWise – Feedback\n")
        txt.append(f"Analysezeitpunkt: {data.get('timestamp')}\n\n")

        txt.append("SPRACHLICHES FEEDBACK:\n")
        for item in feedback.get('language_feedback', []):
            txt.append(f"- {item}\n")

        txt.append("\nSTRUKTUR-FEEDBACK:\n")
        for item in feedback.get('structure_feedback', []):
            txt.append(f"- {item}\n")

        txt.append("\nARGUMENTATION:\n")
        for item in feedback.get('argumentation_feedback', []):
            txt.append(f"- {item}\n")

        txt.append("\nZUSAMMENFASSUNG:\n")
        txt.append(feedback.get('overall_summary', ''))

        export_path = f"exports/feedback_{result_id}.txt"
        with open(export_path, 'w', encoding='utf-8') as f:
            f.writelines(txt)

        return send_file(
            export_path,
            as_attachment=True,
            download_name=f"writewise_feedback_{result_id}.txt"
        )

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/export/pdf/<result_id>', methods=['GET'])
def export_pdf(result_id):
    """
    Exportiert gespeichertes Feedback als PDF-Datei.

    Args:
        result_id (str): ID des gespeicherten Analyseergebnisses.

    Returns:
        Response: PDF-Datei als Download oder JSON-Fehlerantwort.
    """
    result_path = f"results/{result_id}.json"

    if not os.path.exists(result_path):
        return jsonify({'success': False, 'error': 'Ergebnis nicht gefunden'}), 404

    with open(result_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    pdf_path = f"exports/{result_id}.pdf"

    doc = SimpleDocTemplate(pdf_path, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("WriteWise – Analyseergebnis", styles['Title']))
    story.append(Spacer(1, 0.3 * inch))

    feedback = data.get("feedback", {})

    for section, content in feedback.items():
        story.append(Paragraph(section.replace("_", " ").title(), styles['Heading2']))
        if isinstance(content, list):
            for item in content:
                story.append(Paragraph(item, styles['Normal']))
        elif isinstance(content, str):
            story.append(Paragraph(content, styles['Normal']))
        story.append(Spacer(1, 0.2 * inch))

    doc.build(story)

    return send_file(pdf_path, as_attachment=True)


# ---------------------------
# Anwendungsstart
# ---------------------------

if __name__ == '__main__':
    """
    Startet die Anwendung im Entwicklungsmodus.

    Konfiguration:
        - Debug-Modus: aktiv
        - Host: 0.0.0.0 (alle Interfaces)
        - Port: 5000

    Ausgabe:
        - Banner & Statusmeldungen
        - Server-URL
        - Import-Status des KI-Moduls
    """
    print("=" * 60)
    print("  WRITEWISE - KI-FEEDBACK FÜR HAUSARBEITEN")
    print("=" * 60)
    print(" STARTE ANWENDUNG...")
    print(f" Server: http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
