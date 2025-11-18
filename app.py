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

# Deinen bestehenden KI-Code importieren
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
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ordner für Woche 2 erstellen
os.makedirs('uploads', exist_ok=True)
os.makedirs('results', exist_ok=True)
os.makedirs('exports', exist_ok=True)

def extract_text_from_file(file):
    """Extrahiert Text aus verschiedenen Dateiformaten"""
    file_type = magic.from_buffer(file.read(1024), mime=True)
    file.seek(0)  # Zurück zum Dateianfang
    
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
    
    elif file_type in ['application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/msword']:
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
    """Erweiterte Textvalidierung für Woche 2"""
    issues = []
    
    # Basis-Validierung
    if not text or len(text.strip()) < 50:  # Erhöht auf 50 Zeichen
        issues.append("Text zu kurz (mindestens 50 Zeichen erforderlich)")
    
    if len(text) > 20000:  # Erhöhtes Limit für Dateien
        issues.append("Text zu lang (maximal 20.000 Zeichen)")
    
    # Inhaltliche Validierung
    words = text.split()
    if len(words) < 10:
        issues.append("Text enthält zu wenige Wörter für sinnvolle Analyse")
    
    return issues

def create_pdf_feedback(result_id, data):
    """Erstellt ein professionelles PDF-Feedback"""
    try:
        export_path = f'exports/feedback_{result_id}.pdf'
        
        # PDF Dokument erstellen
        doc = SimpleDocTemplate(export_path, pagesize=letter)
        styles = getSampleStyleSheet()
        
        # Custom Styles
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

# Einfache Route für die Startseite
@app.route('/')
def index():
    return render_template('index.html')

# Route für Textanalyse (erweitert für Woche 2)
@app.route('/analyze', methods=['POST'])
def analyze_text():
    try:
        text = ""
        file = request.files.get('file')
        file_used = False
        
        # Text aus Datei oder direkter Eingabe (NEU)
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
        
        # Erweiterte Validierung (NEU)
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
        
        # Ergebnis speichern (NEU für Woche 2)
        result_id = save_feedback(feedback, text[:200], file_used)
        
        # Erfolgsmeldung zurückgeben
        return jsonify({
            'success': True,
            'feedback': feedback,
            'ki_verwendet': KI_VERFUEGBAR,
            'result_id': result_id,  # NEU
            'file_used': file_used,  # NEU
            'text_length': len(text),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Server Fehler: {str(e)}'
        })

def save_feedback(feedback, text_preview, file_used=False):
    """Speichert Feedback als JSON mit erweiterter Struktur (NEU)"""
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
    """Fallback-Feedback falls KI nicht verfügbar"""
    return {
        'language_feedback': [
            'Text ist verständlich geschrieben',
            'Gute Satzstruktur erkennable',
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

# Export-Routen
@app.route('/export/txt/<result_id>')
def export_txt(result_id):
    """Exportiert Feedback als TXT Datei"""
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
    """Exportiert Feedback als PDF Datei"""
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

# Health Check Route (aktualisiert)
@app.route('/health')
def health_check():
    return jsonify({
        'status': 'OK', 
        'message': 'WriteWise API läuft',
        'ki_verfuegbar': KI_VERFUEGBAR,
        'phase': 'Woche 2 - Erweiterte Funktionen',
        'features': ['Datei-Upload', 'TXT-Export', 'PDF-Export', 'Erweiterte Validierung']
    })

# Info Route (aktualisiert)
@app.route('/info')
def info():
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
    print("🚀 WriteWise Woche 2 gestartet!")
    print("📝 Öffne: http://localhost:5000")
    print("📁 Datei-Upload: TXT, PDF, DOCX unterstützt")
    print("📤 Export: TXT und PDF verfügbar")
    print("🔍 Health Check: http://localhost:5000/health")
    print("ℹ️  Info: http://localhost:5000/info")
    app.run(debug=True, host='0.0.0.0', port=5000)