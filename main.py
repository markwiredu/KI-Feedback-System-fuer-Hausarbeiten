"""
KI-Analysemodul für WriteWise - Hausarbeits-Feedback-System.

Dieses Modul implementiert eine KI-gestützte Analyse von Hausarbeiten unter Verwendung
von LangChain und OpenAI-kompatiblen LLMs. Es extrahiert strukturiertes Feedback
zu Sprache, Struktur und Argumentation.
"""

from dotenv import load_dotenv
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
import os
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from typing import List, Optional

# ---------------------------
# Umgebungsvariablen und Datenmodelle
# ---------------------------

"""
Lädt Umgebungsvariablen aus einer .env-Datei.

Diese Umgebungsvariablen werden typischerweise für API-Keys und Konfiguration
(OpenAI-kompatible Endpunkte) benötigt.
"""
load_dotenv()


class FeedbackResponse(BaseModel):
    """
    Pydantic-Modell für strukturiertes KI-Feedback.

    Dieses Modell definiert das strukturierte Ausgabeformat für die KI-Analyse,
    bestehend aus drei Feedback-Kategorien und einer optionalen Zusammenfassung.

    Attributes:
        language_feedback (List[str]):
            Feedback zu Sprache, Grammatik, Stil und Ausdruck.
            Jeder Eintrag sollte eine konkrete Textstelle referenzieren.

        structure_feedback (List[str]):
            Feedback zur Gliederung, Struktur und logischem Aufbau.
            Beinhaltet Verbesserungsvorschläge für die Organisation.

        argumentation_feedback (List[str]):
            Feedback zur Argumentationslogik, Belegen und Schlüssigkeit.

        overall_summary (Optional[str]):
            Zusammenfassende Bewertung der gesamten Arbeit.
            Optionales Feld für abschließende Einschätzung.
    """

    language_feedback: List[str]
    structure_feedback: List[str]
    argumentation_feedback: List[str]
    overall_summary: Optional[str] = None


"""
Stellt sicher, dass das Pydantic-Modell korrekt initialisiert wird.

Dies kann notwendig sein, um Forward-Refs/Modelle korrekt aufzubauen und eine
konsistente Typvalidierung sowie Serialisierung sicherzustellen.
"""
FeedbackResponse.model_rebuild()

# ---------------------------
# Hauptanalysefunktion
# ---------------------------


def analyze_hausarbeit(text: str) -> dict:
    """
    Analysiert eine Hausarbeit mittels KI und generiert strukturiertes Feedback.

    Kernfunktion des Moduls, die ein Large Language Model (LLM) verwendet, um
    akademische Texte in mehreren Kategorien zu bewerten. Die Funktion kombiniert
    LangChain-Komponenten für Prompt-Engineering und strukturierte Ausgabe.

    Args:
        text (str):
            Der zu analysierende Text der Hausarbeit.
            Sollte bereits bereinigt und vorstrukturiert sein (z.B. mit Kapitel-/Seiten-Markierungen).

    Returns:
        dict: Strukturiertes Feedback-Dictionary mit folgenden Keys:
            - 'language_feedback' (List[str]): Sprachliche Verbesserungsvorschläge
            - 'structure_feedback' (List[str]): Strukturelle Hinweise
            - 'argumentation_feedback' (List[str]): Argumentations-Feedback
            - 'overall_summary' (Optional[str]): Gesamteinschätzung

    Raises:
        Exception:
            Bei Fehlern in der KI-Verarbeitung wird der Fehler geloggt und
            konsistentes Fallback-Feedback zurückgegeben.

    Workflow:
        1. Initialisierung des LLM mit Konfiguration aus .env
        2. Erstellung eines strukturierten Output-Parsers (Pydantic)
        3. Definition des Prompt-Templates (System- und Human-Prompt)
        4. Ausführung der Analyse-Kette (Prompt → LLM → Parser)
        5. Umwandlung in Dictionary-Format

    Example:
        >>> feedback = analyze_hausarbeit("In dieser Arbeit untersuche ich...")
        >>> print(feedback["structure_feedback"])
        ["Die Einleitung könnte prägnanter formuliert werden..."]

    Notes:
        - Verwendet OpenAI-kompatible APIs (via base_url Konfiguration).
        - Berücksichtigt mögliche Extraktionsartefakte bei der Analyse.
        - Liefert konstruktives, motivierendes Feedback.
    """
    # ---------------------------
    # LLM Initialisierung
    # ---------------------------

    """
    Initialisiert das ChatOpenAI-Modell mit benutzerdefinierter Konfiguration.

    Configuration:
        model (str):
            "chat-default" als Standard-Chat-Modell.
        base_url (str | None):
            Wert aus der Umgebungsvariable OPENAI_BASE_URL.
        api_key (str | None):
            Wert aus der Umgebungsvariable OPENAI_API_KEY.

    Note:
        Der base_url-Parameter ermöglicht die Nutzung von OpenAI-kompatiblen APIs,
        z.B. lokalen LLM-Servern oder alternativen Anbietern.
    """
    llm = ChatOpenAI(
        model="chat-default",
        base_url=os.getenv("OPENAI_BASE_URL"),
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    # ---------------------------
    # Output-Parser Initialisierung
    # ---------------------------

    """
    Erstellt einen Parser für strukturierte Ausgaben.

    Wandelt die LLM-Antwort in das definierte FeedbackResponse-Modell um.
    Dies erzwingt eine konsistente Ausgabestruktur und ermöglicht Typvalidierung.
    """
    parser = PydanticOutputParser(pydantic_object=FeedbackResponse)

    # ---------------------------
    # Prompt-Template Definition
    # ---------------------------

    """
    Definiert das zweiteilige Prompt-Template für die KI-Analyse.

    Struktur:
        1) System-Prompt:
           Rolle, Aufgabenstellung, Regeln und Formatierungsanweisungen.
        2) Human-Prompt:
           Platzhalter für den tatsächlichen Hausarbeitstext.

    System-Prompt enthält u.a.:
        - Rollendefinition (akademischer Assistent)
        - Analysebereiche (Struktur, Argumentation, Inhalt, Sprache)
        - Einschränkungen (Extraktionsartefakte berücksichtigen)
        - Feedback-Stilrichtlinien (konstruktiv, sachlich, motivierend)
        - Ausgabeformat via format_instructions

    Human-Prompt:
        {query}: Wird mit dem tatsächlichen Text der Hausarbeit befüllt.
    """
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
                Du bist ein akademischer Assistent, der schriftliche Hausarbeiten analysiert
                und konstruktives, fachlich korrektes Feedback gibt.

                Ziel deiner Analyse ist es, Studierenden bei der inhaltlichen und sprachlichen
                Verbesserung ihrer Arbeit zu helfen. Beurteile ausschließlich den vorliegenden Text.

                Analysiere die Arbeit in folgenden Bereichen:

                1. Struktur:
                   - Aufbau von Einleitung, Hauptteil und Schluss
                   - logische Gliederung und Nachvollziehbarkeit
                   - roter Faden und Übergänge zwischen Abschnitten

                2. Argumentation:
                   - Klarheit und Schlüssigkeit der Argumente
                   - Begründungen, Beispiele und Folgerungen
                   - innere Logik und Konsistenz

                3. Inhalt:
                   - thematische Relevanz
                   - inhaltliche Tiefe und Präzision
                   - sachliche Angemessenheit (ohne Fakten zu erfinden oder zu überprüfen)

                4. Sprache und Stil:
                   - Verständlichkeit und Lesefluss
                   - akademischer Stil und Ausdruck
                   - Wortwahl und Satzstruktur

                Wichtige Einschränkungen und Regeln:
                - Der Text kann aus einer Datei (z. B. PDF oder DOCX) stammen und automatisch extrahiert worden sein.
                - Kritisiere daher keine möglichen Fehler bei Leerzeichen, Worttrennungen, Interpunktion
                  oder offensichtliche Formatierungsartefakte, wenn diese plausibel technisch bedingt sind.
                - Gib keine Rechtschreib- oder Grammatikhinweise, die eindeutig auf Dateiextraktion
                  oder automatische Textverarbeitung zurückzuführen sein könnten.
                - Verweise bei Kritik oder Verbesserungsvorschlägen möglichst präzise auf Textstellen,
                  z. B. durch Absatzinhalt, Satzanfang oder inhaltliche Beschreibung,
                  jedoch nur, sofern dies anhand des gegebenen Textes zuverlässig möglich ist.
                - Erfinde keine Seitenzahlen, Absätze oder Textstellen.

                Feedback-Stil:
                - Beginne jede Kategorie mit mindestens einem positiven Aspekt.
                - Formuliere konstruktiv, sachlich und motivierend.
                - Keine pauschalen Urteile, sondern konkrete, nachvollziehbare Hinweise.
                - Antworte ausschließlich bezogen auf den eingegebenen Text.
                - Jeder Feedbackpunkt soll maximal 2–3 Sätze enthalten.

                Gib dein Feedback ausschließlich im vorgegebenen strukturierten Ausgabeformat aus.

                {format_instructions}
                """,
            ),
            ("human", "{query}"),
        ]
    ).partial(format_instructions=parser.get_format_instructions())

    # ---------------------------
    # Analyse-Kette aufbauen
    # ---------------------------

    """
    Kombiniert die Komponenten zu einer Verarbeitungskette.

    Chain sequence:
        1) Prompt: Wendet das Template auf Input an
        2) LLM: Verarbeitet den formatierten Prompt
        3) Parser: Konvertiert die LLM-Antwort in ein strukturiertes Pydantic-Modell

    Pipeline:
        Input → Prompt Template → LLM → Parser → Strukturierte Ausgabe
    """
    chain = prompt | llm | parser

    try:
        # ---------------------------
        # Ausführung der Analyse
        # ---------------------------

        """
        Führt die Analyse-Kette mit dem bereitgestellten Text aus.

        Prozess:
            1) Verpackt den Text in ein Dictionary unter dem Key "query"
            2) Übergibt an die LangChain-Pipeline
            3) Erhält ein FeedbackResponse-Objekt

        Error handling:
            Fehler werden als Exception ausgelöst und im except-Block behandelt.
        """
        response = chain.invoke({"query": text})

        # ---------------------------
        # Umwandlung und Rückgabe
        # ---------------------------

        """
        Konvertiert das Pydantic-Modell in ein Python-Dictionary.

        Dadurch wird JSON-Serialisierung erleichtert und Kompatibilität mit
        anderen Systemkomponenten (z.B. Flask-API) sichergestellt.
        """
        return {
            "language_feedback": response.language_feedback,
            "structure_feedback": response.structure_feedback,
            "argumentation_feedback": response.argumentation_feedback,
            "overall_summary": response.overall_summary,
        }

    except Exception as e:
        """
        Fehlerbehandlung bei gescheiterter KI-Analyse.

        Loggt den Fehler und gibt konsistentes Fallback-Feedback zurück,
        um Systemstabilität zu gewährleisten.

        Fallback-Feedback:
            - Enthält Fehlermeldung in language_feedback
            - Leere Listen für andere Kategorien
            - Klare Fehlerkennzeichnung in overall_summary
        """
        print(f"❌ Fehler bei KI-Analyse: {e}")
        return {
            "language_feedback": [f"Analyse fehlgeschlagen: {str(e)}"],
            "structure_feedback": [],
            "argumentation_feedback": [],
            "overall_summary": "Fehler bei der Analyse",
        }


# ---------------------------
# Test- und Entwicklungsbereich
# ---------------------------

if __name__ == "__main__":
    """
    Entwicklungs-/Integrationstest für die Analysefunktion.

    Wird nur ausgeführt, wenn das Modul direkt gestartet wird (nicht bei Import).
    Dient zur Verifikation der grundlegenden Funktionalität und als Beispiel
    für die Verwendung.

    Test case:
        - Kurzer Beispieltext zum Klimawandel
        - Ausgabe aller Feedback-Kategorien
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
