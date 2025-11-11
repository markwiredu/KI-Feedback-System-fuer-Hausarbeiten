from flask import Flask, render_template, request, jsonify
import os
import json
from datetime import datetime
import sys

# Deinen bestehenden KI-Code importieren
sys.path.append(os.path.dirname(__file__))

try:
    from main import analyze_hausarbeit  # Import deiner bestehenden Funktion
    KI_VERFUEGBAR = True
    print("✅ KI-Modul erfolgreich importiert")
except ImportError as e:
    print(f"⚠️  KI-Modul nicht verfügbar: {e}")
    KI_VERFUEGBAR = False

# Flask App initialisieren
app = Flask(__name__)

# Einfache Route für die Startseite
@app.route('/')
def index():
    return render_template('index.html')

# Route für Textanalyse (mit deiner echten KI wenn verfügbar)
@app.route('/analyze', methods=['POST'])
def analyze_text():
    try:
        # Daten vom Formular erhalten
        text = request.form.get('text', '')
        
        # Validierung
        if not text or len(text.strip()) < 10:
            return jsonify({
                'success': False,
                'error': 'Text zu kurz. Bitte mindestens 10 Zeichen eingeben.'
            })
        
        if len(text) > 10000:
            return jsonify({
                'success': False, 
                'error': 'Text zu lang. Maximal 10.000 Zeichen.'
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
        
        # Erfolgsmeldung zurückgeben
        return jsonify({
            'success': True,
            'feedback': feedback,
            'ki_verwendet': KI_VERFUEGBAR,
            'text_length': len(text),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Server Fehler: {str(e)}'
        })

def create_mock_feedback():
    """Fallback-Feedback falls KI nicht verfügbar"""
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
            'Verbessere mit echter KI in Woche 2'
        ],
        'overall_summary': 'Gute Grundlage! Aktuell mit Mock-Daten. Echte KI folgt in Woche 2.'
    }

# Health Check Route
@app.route('/health')
def health_check():
    return jsonify({
        'status': 'OK', 
        'message': 'WriteWise API läuft',
        'ki_verfuegbar': KI_VERFUEGBAR
    })

# Info Route
@app.route('/info')
def info():
    return jsonify({
        'name': 'WriteWise',
        'version': '1.0',
        'phase': 'Woche 1 - Flask Grundgerüst',
        'ki_verfuegbar': KI_VERFUEGBAR
    })

# App starten
if __name__ == '__main__':
    print("🚀 WriteWise Flask App starting...")
    print("📝 Öffne: http://localhost:5000")
    print("🔍 Health Check: http://localhost:5000/health")
    print("ℹ️  Info: http://localhost:5000/info")
    app.run(debug=True, host='0.0.0.0', port=5000)