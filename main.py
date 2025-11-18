from dotenv import load_dotenv
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
import os
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from typing import List, Optional  

load_dotenv()

class FeedbackResponse(BaseModel):
    language_feedback: List[str]
    structure_feedback: List[str]
    argumentation_feedback: List[str]
    overall_summary: Optional[str] = None


FeedbackResponse.model_rebuild()

def analyze_hausarbeit(text: str) -> dict:
    """Analysiert Hausarbeit und gibt strukturiertes Feedback zurück"""
    
    llm = ChatOpenAI(
        model="chat-default",  
        base_url=os.getenv("OPENAI_BASE_URL"),
        api_key=os.getenv("OPENAI_API_KEY")
    )
    
    parser = PydanticOutputParser(pydantic_object=FeedbackResponse)

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

    chain = prompt | llm | parser

    try:
        response = chain.invoke({"query": text})
        
        # Konvertiert Pydantic-Modell zu Dictionary für Flask
        return {
            'language_feedback': response.language_feedback,
            'structure_feedback': response.structure_feedback,
            'argumentation_feedback': response.argumentation_feedback,
            'overall_summary': response.overall_summary
        }
        
    except Exception as e:
        print(f"❌ Fehler bei KI-Analyse: {e}")
        # Fallback-Feedback
        return {
            'language_feedback': [f'Analyse fehlgeschlagen: {str(e)}'],
            'structure_feedback': [],
            'argumentation_feedback': [],
            'overall_summary': 'Fehler bei der Analyse'
        }

# Test-Code nur wenn direkt ausgeführt
if __name__ == "__main__":
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