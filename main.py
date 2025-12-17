from dotenv import load_dotenv
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
import os
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from typing import List, Optional  

# Lädt Umgebungsvariablen aus einer .env Datei
load_dotenv()

class FeedbackResponse(BaseModel):
    """
    Pydantic-Modell für strukturiertes Feedback zu einer Hausarbeit.
    
    Attributes:
        language_feedback (List[str]): Feedback zur Sprache, Grammatik und Ausdruck
        structure_feedback (List[str]): Feedback zur Struktur und Gliederung
        argumentation_feedback (List[str]): Feedback zur Argumentation und Logik
        overall_summary (Optional[str]): Zusammenfassende Bewertung der Arbeit
    """
    language_feedback: List[str]
    structure_feedback: List[str]
    argumentation_feedback: List[str]
    overall_summary: Optional[str] = None

# Stellt sicher, dass das Modell korrekt initialisiert wird
FeedbackResponse.model_rebuild()

def analyze_hausarbeit(text: str) -> dict:
    """
    Analysiert eine Hausarbeit mittels KI und gibt strukturiertes Feedback zurück.
    
    Diese Funktion verwendet ein LLM (Large Language Model), um eine Hausarbeit
    in den Bereichen Sprache, Struktur und Argumentation zu bewerten und
    konstruktives Feedback zu generieren.
    
    Args:
        text (str): Der Text der zu analysierenden Hausarbeit
        
    Returns:
        dict: Ein Dictionary mit Feedback in folgenden Kategorien:
            - language_feedback: Liste mit sprachlichen Hinweisen
            - structure_feedback: Liste mit strukturellen Verbesserungsvorschlägen
            - argumentation_feedback: Liste mit Feedback zur Argumentation
            - overall_summary: Zusammenfassende Bewertung oder None
        
    Raises:
        Exception: Falls die KI-Analyse fehlschlägt, wird ein Fehler geloggt
                  und ein Fallback-Feedback zurückgegeben
        
    Example:
        >>> result = analyze_hausarbeit("Hier steht der Text der Hausarbeit...")
        >>> print(result['language_feedback'])
        ['Verbesserungsvorschlag 1', 'Verbesserungsvorschlag 2']
    """
    
    # Initialisiert das ChatOpenAI-Modell mit Konfiguration aus Umgebungsvariablen
    llm = ChatOpenAI(
        model="chat-default",  
        base_url=os.getenv("OPENAI_BASE_URL"),
        api_key=os.getenv("OPENAI_API_KEY")
    )
    
    # Erstellt einen Parser für die strukturierte Ausgabe im FeedbackResponse-Format
    parser = PydanticOutputParser(pydantic_object=FeedbackResponse)

    # Erstellt das Prompt-Template für die KI-Analyse
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
Du bist ein akademischer Assistent, der Hausarbeiten analysiert und konstruktives Feedback gibt. 
Deine Aufgabe ist es, dem Benutzer die Arbeit zu verbessern, indem du Feedback in den folgenden Bereichen gibst:

1. Struktur: Prüfe Einleitung, Hauptteil, Schluss und logischen Aufbau.
2. Argumentation: Bewerte die Nachvollziehbarkeit, Klarheit und Logik der Argumente.
3. Inhalt: Achte auf Relevanz, Richtigkeit und Tiefe.
4. Sprache: Gib Hinweise zu Grammatik, Stil, Ausdruck und Verständlichkeit.
5. Verbesserungsvorschläge: Formuliere konkrete, hilfreiche Tipps.

Systemanforderungen:
- Texte können als Eingabe oder Datei kommen.
- Prüfe Mindestlänge und Format.
- Gib professionelles, motivierendes Feedback.
- Antworte NUR bezogen auf den eingegebenen Text.

{format_instructions}
""",
            ),
            ("human", "{query}"),
        ]
    ).partial(format_instructions=parser.get_format_instructions())

    # Verkettet die Komponenten zu einer Pipeline: Prompt → LLM → Parser
    chain = prompt | llm | parser

    try:
        # Führt die Analyse mit dem bereitgestellten Text durch
        response = chain.invoke({"query": text})
        
        # Wandelt das Pydantic-Modell in ein Dictionary um
        return {
            'language_feedback': response.language_feedback,
            'structure_feedback': response.structure_feedback,
            'argumentation_feedback': response.argumentation_feedback,
            'overall_summary': response.overall_summary
        }
        
    except Exception as e:
        # Fehlerbehandlung bei Problemen mit der KI-Analyse
        print(f"❌ Fehler bei KI-Analyse: {e}")
        # Fallback-Feedback bei Fehlern
        return {
            'language_feedback': [f'Analyse fehlgeschlagen: {str(e)}'],
            'structure_feedback': [],
            'argumentation_feedback': [],
            'overall_summary': 'Fehler bei der Analyse'
        }

# Test-Code nur wenn direkt ausgeführt
if __name__ == "__main__":
    """
    Testfunktion für die Hausarbeitsanalyse.
    
    Wird nur ausgeführt, wenn die Datei direkt gestartet wird,
    nicht wenn sie als Modul importiert wird.
    """
    test_text = """
    In dieser Hausarbeit werde ich die Auswirkungen des Klimawandels auf die Landwirtschaft in Deutschland untersuchen. 
    Der Klimawandel ist ein wichtiges Thema und betrifft uns alle. Die Landwirtschaft muss sich anpassen 
    und neue Methoden finden. Es gibt viele Studien dazu, die verschiedene Aspekte beleuchten.
    """
    
    print("🧪 Teste KI-Analyse...")
    result = analyze_hausarbeit(test_text)
    print("✅ Analyse erfolgreich!")
    print(f"Sprache: {result['language_feedback']}")
    print(f"Struktur: {result['structure_feedback']}")
    print(f"Argumentation: {result['argumentation_feedback']}")
    print(f"Zusammenfassung: {result['overall_summary']}")