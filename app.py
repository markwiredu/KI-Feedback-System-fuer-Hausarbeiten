from flask import Flask, render_template, request, jsonify, send_file
import os
import json
from datetime import datetime
import sys
import magic
import PyPDF2
from docx import Document
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import inch

# Import des bestehenden KI-Moduls aus dem Hauptskript
sys.path.append(os.path.dirname(__file__))

try:
    from main import analyze_hausarbeit  
    KI_VERFUEGBAR = True
    print("✅ KI-Modul erfolgreich importiert")
except ImportError as e:
    print(f"⚠️  KI-Modul nicht verfügbar: {e}")
    KI_VERFUEGBAR = False

# Flask App initialisieren
app = Flask(__name__)
# Maximale Dateigröße auf 16MB setzen
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Erforderliche Ordner für die Anwendung erstellen
os.makedirs('uploads', exist_ok=True)    # Für hochgeladene Dateien
os.makedirs('results', exist_ok=True)    # Für Analyseergebnisse
os.makedirs('exports', exist_ok=True)    # Für Export-Dateien

def extract_text_from_file(file):
    """
    Extrahiert Text aus einer Datei (TXT, PDF, DOCX).
    
    Die Funktion erkennt den Dateityp automatisch anhand des MIME-Typs
    und liest den Text je nach Format mit der passenden Bibliothek aus.
    
    Args:
        file: Dateiobjekt, das eingelesen werden soll
        
    Returns:
        str: Der extrahierte Text
        
    Raises:
        Exception: Wenn das Dateiformat nicht unterstützt wird oder
                   das Lesen fehlschlägt
    
    Note:
        Unterstützte Formate: TXT, PDF, DOCX, DOC
        Verwendet die 'magic'-Bibliothek zur MIME-Typ-Erkennung
    """
    file_type = magic.from_buffer(file.read(1024), mime=True)
    file.seek(0)
    
    if file_type == 'text/plain':
        return file.read().decode('utf-8')
    
    elif file_type == 'application/pdf':
        try:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            raise Exception(f"PDF konnte nicht gelesen werden: {str(e)}")
    
    elif file_type in [
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/msword'
    ]:
        try:
            doc = Document(file)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text
        except Exception as e:
            raise Exception(f"Word-Dokument konnte nicht gelesen werden: {str(e)}")
    
    else:
        raise Exception(f"Nicht unterstütztes Dateiformat: {file_type}")


def validate_text_content(text):
    """
    Prüft Text auf Mindestlänge, Maximallänge und ausreichenden Inhalt.
    
    Die Funktion kontrolliert:
        - Mindestlänge (50 Zeichen)
        - Maximallänge (20.000 Zeichen)
        - Mindestanzahl an Wörtern (10)
    
    Args:
        text (str): Der zu prüfende Text
        
    Returns:
        list: Liste gefundener Probleme. Leere Liste, wenn der Text gültig ist
    
    Example:
        >>> issues = validate_text_content("Kurzer Text")
        >>> print(issues)
        ['Text zu kurz (mindestens 50 Zeichen erforderlich)', 
         'Text enthält zu wenige Wörter für sinnvolle Analyse']
    """
    issues = []
    
    # Basis-Validierung
    if not text or len(text.strip()) < 50:
        issues.append("Text zu kurz (mindestens 50 Zeichen erforderlich)")
    
    if len(text) > 20000:
        issues.append("Text zu lang (maximal 20.000 Zeichen)")
    
    # Inhaltliche Validierung
    words = text.split()
    if len(words) < 10:
        issues.append("Text enthält zu wenige Wörter für sinnvolle Analyse")
    
    return issues


def create_pdf_feedback(result_id, data):
    """
    Erstellt ein professionelles PDF-Feedback-Dokument.
    
    Die Funktion generiert ein formatiertes PDF mit allen Analyseergebnissen
    und Metadaten im WriteWise-Stil.
    
    Args:
        result_id (str): Eindeutige ID des Analyseergebnisses
        data (dict): Analyseergebnisse und Metadaten
        
    Returns:
        str: Pfad zur erstellten PDF-Datei
        
    Raises:
        Exception: Wenn die PDF-Erstellung fehlschlägt
        
    Note:
        Verwendet ReportLab für die PDF-Generierung mit benutzerdefinierten Stilen
        und Layouts im WriteWise-Design
    """
    try:
        export_path = f'exports/feedback_{result_id}.pdf'
        
        # PDF Dokument erstellen
        doc = SimpleDocTemplate(export_path, pagesize=letter)
        styles = getSampleStyleSheet()
        
        # Custom Styles für WriteWise-Design
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=30,
            textColor='#2c3e50'
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=12,
            spaceAfter=12,
            textColor='#3498db'
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=6,
            textColor='#2c3e50'
        )
        
        # Content zusammenbauen
        content = []
        
        # Titel
        content.append(Paragraph("WriteWise - Feedback Report", title_style))
        content.append(Spacer(1, 0.2*inch))
        
        # Metadaten
        content.append(Paragraph(f"<b>Analyse-Datum:</b> {data['timestamp']}", normal_style))
        content.append(Paragraph(f"<b>Textlänge:</b> {data['text_length']} Zeichen", normal_style))
        content.append(Spacer(1, 0.2*inch))
        
        # Textvorschau
        content.append(Paragraph("<b>Textvorschau:</b>", heading_style))
        content.append(Paragraph(data['text_preview'] + "...", normal_style))
        content.append(Spacer(1, 0.2*inch))
        
        feedback = data['feedback']
        
        # Sprachliches Feedback
        content.append(Paragraph("💬 <b>Sprachliches Feedback</b>", heading_style))
        for item in feedback.get('language_feedback', []):
            content.append(Paragraph(f"• {item}", normal_style))
        content.append(Spacer(1, 0.1*inch))
        
        # Struktur-Feedback
        content.append(Paragraph("📊 <b>Struktur und Aufbau</b>", heading_style))
        for item in feedback.get('structure_feedback', []):
            content.append(Paragraph(f"• {item}", normal_style))
        content.append(Spacer(1, 0.1*inch))
        
        # Argumentation
        content.append(Paragraph("🎯 <b>Argumentation</b>", heading_style))
        for item in feedback.get('argumentation_feedback', []):
            content.append(Paragraph(f"• {item}", normal_style))
        content.append(Spacer(1, 0.1*inch))
        
        # Zusammenfassung
        content.append(Paragraph("📋 <b>Zusammenfassung</b>", heading_style))
        content.append(Paragraph(feedback.get('overall_summary', 'Keine Zusammenfassung verfügbar'), normal_style))
        
        # PDF generieren
        doc.build(content)
        return export_path
        
    except Exception as e:
        raise Exception(f"PDF-Erstellung fehlgeschlagen: {str(e)}")


@app.route('/')
def index():
    """
    Hauptroute der Anwendung - Rendert die Startseite.
    
    Returns:
        str: Gerenderte HTML-Template 'index.html'
    """
    return render_template('index.html')


@app.route('/analyze', methods=['POST'])
def analyze_text():
    """
    Analysiert Text oder Datei und gibt Feedback zurück.
    
    Diese Route akzeptiert entweder direkt eingegebenen Text oder eine hochgeladene
    Datei (TXT, PDF, DOCX), extrahiert den Text, führt eine Validierung durch
    und startet die KI-Analyse oder verwendet Mock-Daten.
    
    Request:
        POST mit Form-Daten:
            - text: Direkter Textinput (optional)
            - file: Datei-Upload (optional)
        
    Returns:
        JSON: Erfolg/Misserfolg mit Analyseergebnissen oder Fehlermeldung
        
        Bei Erfolg:
            {
                'success': True,
                'feedback': { ... },
                'ki_verwendet': bool,
                'result_id': str,
                'file_used': bool,
                'text_length': int,
                'timestamp': str
            }
        
        Bei Fehler:
            {
                'success': False,
                'error': str
            }
            
    Raises:
        413: Wenn die Datei zu groß ist (>16MB)
        400: Bei Validierungsfehlern oder nicht unterstützten Dateiformaten
    """
    try:
        text = ""
        file = request.files.get('file')
        file_used = False
        
        # Text aus Datei oder direkter Eingabe
        if file and file.filename:
            if file.filename == '':
                return jsonify({'success': False, 'error': 'Keine Datei ausgewählt'})
            
            # Dateityp validieren
            allowed_extensions = {'.txt', '.pdf', '.docx', '.doc'}
            file_ext = os.path.splitext(file.filename)[1].lower()
            if file_ext not in allowed_extensions:
                return jsonify({
                    'success': False, 
                    'error': f'Nicht unterstütztes Dateiformat. Erlaubt: {", ".join(allowed_extensions)}'
                })
            
            # Text aus Datei extrahieren
            try:
                text = extract_text_from_file(file)
                file_used = True
                
                # Temporär speichern für Referenz
                file.seek(0)
                filename = f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}{file_ext}"
                file.save(os.path.join('uploads', filename))
                
            except Exception as e:
                return jsonify({'success': False, 'error': f'Datei-Verarbeitung fehlgeschlagen: {str(e)}'})
                
        else:
            # Text aus Formular-Feld
            text = request.form.get('text', '')
        
        # Erweiterte Validierung
        validation_issues = validate_text_content(text)
        if validation_issues:
            return jsonify({
                'success': False,
                'error': 'Textvalidierung fehlgeschlagen: ' + '; '.join(validation_issues)
            })
        
        # KI-Analyse oder Mock-Feedback
        if KI_VERFUEGBAR:
            try:
                print("🔄 Starte KI-Analyse...")
                feedback = analyze_hausarbeit(text)
                print("✅ KI-Analyse erfolgreich")
            except Exception as e:
                print(f"❌ KI-Fehler: {e}")
                feedback = create_mock_feedback()
        else:
            print("ℹ️ Verwende Mock-Feedback")
            feedback = create_mock_feedback()
        
        # Ergebnis speichern
        result_id = save_feedback(feedback, text[:200], file_used)
        
        # Erfolgsmeldung zurückgeben
        return jsonify({
            'success': True,
            'feedback': feedback,
            'ki_verwendet': KI_VERFUEGBAR,
            'result_id': result_id,
            'file_used': file_used,
            'text_length': len(text),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Server Fehler: {str(e)}'
        })


def save_feedback(feedback, text_preview, file_used=False):
    """
    Speichert Feedback als JSON-Datei.
    
    Die Funktion erzeugt eine eindeutige ID, sammelt Metadaten
    (Zeitstempel, Textlänge, Kategorien) und speichert alles formatiert
    im Ordner "results/".
    
    Args:
        feedback (dict): Analyseergebnisse als Kategorien und Inhalte
        text_preview (str): Kurzer Auszug des analysierten Textes (max 200 Zeichen)
        file_used (bool): Ob die Analyse aus einer Datei stammt
        
    Returns:
        str: Die erzeugte Ergebnis-ID (gleichzeitig Dateiname ohne Erweiterung)
        
    Note:
        Dateiname: YYYYMMDD_HHMMSS.json im 'results/' Ordner
        Strukturierte JSON-Daten mit UTF-8 Kodierung
    """
    result_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    result_data = {
        'id': result_id,
        'timestamp': datetime.now().isoformat(),
        'text_preview': text_preview,
        'text_length': len(text_preview),
        'file_used': file_used,
        'feedback': feedback,
        'analysis_categories': list(feedback.keys())
    }

    with open(f'results/{result_id}.json', 'w', encoding='utf-8') as f:
        json.dump(result_data, f, indent=2, ensure_ascii=False)

    return result_id


def create_mock_feedback():
    """
    Erstellt Fallback-Feedback falls KI nicht verfügbar.
    
    Returns:
        dict: Mock-Feedback-Struktur mit Platzhalterdaten
        
    Note:
        Wird verwendet, wenn das KI-Modul nicht importiert werden kann
        oder die KI-Analyse fehlschlägt
    """
    return {
        'language_feedback': [
            'Text ist verständlich geschrieben',
            'Gute Satzstruktur erkennbar',
            '⚠️ Echte KI-Analyse nicht verfügbar - dies ist Mock-Daten'
        ],
        'structure_feedback': [
            'Klare Einleitung vorhanden',
            'Logischer Aufbau erkennbar',
            'Mock-Daten für Testing'
        ],
        'argumentation_feedback': [
            'Argumente sind nachvollziehbar',
            'Belege könnten stärker sein',
            'Verbessere mit echter KI'
        ],
        'overall_summary': 'Gute Grundlage! Aktuell mit Mock-Daten. Echte KI folgt in der nächsten Version.'
    }


@app.route('/export/txt/<result_id>')
def export_txt(result_id):
    """
    Exportiert Feedback als TXT Datei.
    
    Args:
        result_id (str): ID des zu exportierenden Ergebnisses
        
    Returns:
        File: TXT-Datei als Download oder JSON-Fehler
        
    Raises:
        404: Wenn das Ergebnis nicht gefunden wird
    """
    try:
        filepath = f'results/{result_id}.json'
        if not os.path.exists(filepath):
            return jsonify({'success': False, 'error': 'Ergebnis nicht gefunden'})
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # TXT Format erstellen
        txt_content = f"WriteWise Feedback - {data['timestamp']}\n"
        txt_content += "=" * 50 + "\n\n"
        txt_content += f"Textvorschau: {data['text_preview']}\n\n"
        
        feedback = data['feedback']
        txt_content += "SPRACHLICHES FEEDBACK:\n"
        for item in feedback.get('language_feedback', []):
            txt_content += f"• {item}\n"
        
        txt_content += "\nSTRUKTUR-FEEDBACK:\n"
        for item in feedback.get('structure_feedback', []):
            txt_content += f"• {item}\n"
        
        txt_content += "\nARGUMENTATION:\n"
        for item in feedback.get('argumentation_feedback', []):
            txt_content += f"• {item}\n"
        
        txt_content += f"\nZUSAMMENFASSUNG:\n{feedback.get('overall_summary', '')}\n"
        
        # TXT Datei erstellen
        export_path = f'exports/feedback_{result_id}.txt'
        with open(export_path, 'w', encoding='utf-8') as f:
            f.write(txt_content)
        
        return send_file(export_path, as_attachment=True, download_name=f'writewise_feedback_{result_id}.txt')
    
    except Exception as e:
        return jsonify({'success': False, 'error': f'Export fehlgeschlagen: {str(e)}'})


@app.route('/export/pdf/<result_id>')
def export_pdf(result_id):
    """
    Exportiert Feedback als PDF Datei.
    
    Args:
        result_id (str): ID des zu exportierenden Ergebnisses
        
    Returns:
        File: PDF-Datei als Download oder JSON-Fehler
        
    Raises:
        404: Wenn das Ergebnis nicht gefunden wird
    """
    try:
        filepath = f'results/{result_id}.json'
        if not os.path.exists(filepath):
            return jsonify({'success': False, 'error': 'Ergebnis nicht gefunden'})
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # PDF erstellen
        pdf_path = create_pdf_feedback(result_id, data)
        
        return send_file(pdf_path, as_attachment=True, download_name=f'writewise_feedback_{result_id}.pdf')
    
    except Exception as e:
        return jsonify({'success': False, 'error': f'PDF-Export fehlgeschlagen: {str(e)}'})


@app.route('/health')
def health_check():
    """
    Health Check Endpoint für Monitoring.
    
    Returns:
        JSON: Statusinformationen der Anwendung
        
    Note:
        Wird für Load Balancer, Monitoring-Tools und Systemchecks verwendet
    """
    return jsonify({
        'status': 'OK', 
        'message': 'WriteWise API läuft',
        'ki_verfuegbar': KI_VERFUEGBAR,
        'phase': 'Woche 2 - Erweiterte Funktionen',
        'features': ['Datei-Upload', 'TXT-Export', 'PDF-Export', 'Erweiterte Validierung']
    })


@app.route('/info')
def info():
    """
    Informationsendpunkt mit Anwendungsdetails.
    
    Returns:
        JSON: Technische Informationen und unterstützte Features
    """
    return jsonify({
        'name': 'WriteWise',
        'version': '2.0',
        'phase': 'Woche 2 - Erweiterte Funktionen',
        'ki_verfuegbar': KI_VERFUEGBAR,
        'supported_files': ['TXT', 'PDF', 'DOCX', 'DOC'],
        'export_formats': ['TXT', 'PDF']  
    })


# App starten
if __name__ == '__main__':
    """
    Hauptausführungspunkt der WriteWise-Anwendung.
    
    Startet den Flask-Entwicklungsserver mit folgenden Konfigurationen:
    - Debug-Modus für detaillierte Fehlerinformationen während der Entwicklung
    - Netzwerkzugriff auf allen Schnittstellen (0.0.0.0) für lokales Testing
    - Standard-Port 5000 für HTTP-Kommunikation
    
    Technische Entscheidung:
    Verwendung des integrierten Flask-Entwicklungsservers statt
    Produktions-Server (wie Gunicorn oder uWSGI), da WriteWise aktuell
    als Prototyp/Entwicklungsumgebung dient.
    """
    
    print("=" * 60)
    print("🤖 WRITEWISE - KI-FEEDBACK FÜR HAUSARBEITEN")
    print("=" * 60)
    print("\n📋 SYSTEMÜBERSICHT")
    print("-" * 40)
    print("✅ Backend:        Flask Web Framework")
    print("✅ KI-Integration: LangChain mit OpenAI API")
    print("✅ Frontend:       Responsive Web-Oberfläche")
    print("\n🚀 STARTE ANWENDUNG...")
    print("-" * 40)
    print(f"📡 Server:         http://localhost:5000")
    print(f"🌐 Netzwerk:       http://192.168.x.x:5000")
    print(f"⚡ Debug-Modus:    AKTIV (für Entwicklung)")
    
    print("\n🔧 FUNKTIONALITÄTEN")
    print("-" * 40)
    print("📝 Texteingabe:    Manuelle Eingabe oder Datei-Upload")
    print("📁 Dateiformate:   TXT, PDF, DOCX, DOC")
    print("🤖 KI-Analyse:     Sprache • Struktur • Argumentation")
    print("📤 Export:         TXT und PDF Download")
    print("🛡️  Sicherheit:     Validierung + Error-Handling")
    
    print("\n🔗 DIAGNOSE-LINKS")
    print("-" * 40)
    print("🏥 Health Check:   http://localhost:5000/health")
    print("ℹ️  System-Info:    http://localhost:5000/info")
    print("📊 API-Testing:    Thunder Client / Postman empfohlen")
    
    print("\n⚠️  HINWEISE")
    print("-" * 40)
    print("• Entwicklungs-Server - nicht für Produktion geeignet")
    print("• Bei Änderungen: Server automatischer Neustart (Hot Reload)")
    print("• Für Produktion: Gunicorn oder Docker verwenden")
    print("• API-Keys werden aus .env Datei geladen")
    print("=" * 60)
    
    try:
        # Starte Flask-Entwicklungsserver
        app.run(
            debug=True,           # Debug-Modus für Entwickler-Features
            host='0.0.0.0',       # Erlaube Zugriff von allen Netzwerk-Interfaces
            port=5000,            # Standard HTTP-Port für Entwicklung
            threaded=True         # Bessere Performance für gleichzeitige Anfragen
        )
    except KeyboardInterrupt:
        print("\n\n👋 WriteWise wurde ordnungsgemäß beendet.")
        print("Danke für die Nutzung!")
    except Exception as e:
        print(f"\n❌ FEHLER BEIM STARTEN: {str(e)}")
        print("Überprüfe:")
        print("1. Ist Port 5000 bereits belegt?")
        print("2. Sind alle Abhängigkeiten installiert?")
        print("3. Enthält .env die korrekten API-Keys?")