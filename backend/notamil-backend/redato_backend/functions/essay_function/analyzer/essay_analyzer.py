import os
import json
from typing import Any, Dict

import spacy
from redato_backend.functions.essay_function.analyzer.llm_agent import LLMAgent
from redato_backend.functions.essay_function.analyzer.system_prompts import (
    SYSTEM_PROMPT,
)
from redato_backend.functions.essay_function.analyzer.prompts import (
    PROMPT_ANALYSIS_COMPETENCY_1,
    PROMPT_ANALYSIS_COMPETENCY_2,
    PROMPT_ANALYSIS_COMPETENCY_3,
    PROMPT_ANALYSIS_COMPETENCY_4,
    PROMPT_ANALYSIS_COMPETENCY_5,
    PROMPT_CRITERIA_GRADES,
    PROMPT_GRADES,
    GRADING_CRITERIA,
)

from redato_backend.shared.constants import (
    COMPETENCIES,
)
from redato_backend.shared.logger import logger
from redato_backend.shared.models import AnalysisResultsModel


# Mapping from competency number to competency ID
COMPETENCY_NUMBER_TO_ID = {
    1: "d7d30def-7f7f-4cc4-ae92-b41228a9855e",  # Domínio da Norma Culta
    2: "a7c812b2-fefd-4757-8774-e08bcdba82cc",  # Compreensão do Tema
    3: "3334fd6a-adf0-4c43-8e83-630270c17f86",  # Seleção e Organização das Informações
    4: "5467abb2-bd17-44be-90bd-a5065d1e6ee0",  # Conhecimento dos Mecanismos Linguísticos
    5: "fd207ce5-b400-475b-a136-ce9c4d5cd00d",  # Proposta de Intervenção
}

# Reverse mapping for compatibility
COMPETENCY_ID_TO_NUMBER = {v: k for k, v in COMPETENCY_NUMBER_TO_ID.items()}


class EssayAnalyzer:
    """
    Classe principal para análise da redação.
    Agora a LLM retorna tudo em JSON, evitando parsing de texto.
    """

    def __init__(self):
        self.nlp = self._import_spacy_module()
        self.llm = LLMAgent(SYSTEM_PROMPT)

    @staticmethod
    def _import_spacy_module() -> spacy:
        model_path = os.getenv("SPACY_MODEL_PATH", "models/pt_core_news_sm/")
        try:
            if os.path.exists(model_path):
                return spacy.load(model_path)
            return spacy.load("pt_core_news_sm")
        except OSError as e:
            logger.error(f"Error loading spaCy model: {e}")
            raise

    def analyze_with_cohmetrix(self, text_content: str) -> Dict[str, Any]:
        doc = self.nlp(text_content)
        word_count = 0
        total_word_length = 0
        unique_words_set = set()
        verb_phrases = 0
        connectives = 0

        for token in doc:
            if not token.is_punct:
                word_count += 1
                total_word_length += len(token.text)
                unique_words_set.add(token.lemma_.lower())
            if token.pos_ == "VERB":
                verb_phrases += 1
            if token.dep_ in ["cc", "prep"]:
                connectives += 1

        sentence_count = len(list(doc.sents)) or 1
        avg_word_length = (total_word_length / word_count) if word_count > 0 else 0
        unique_words = len(unique_words_set)
        lexical_diversity = (unique_words / word_count) if word_count > 0 else 0
        noun_phrases = len(list(doc.noun_chunks))
        paragraphs = text_content.split("\n\n")
        paragraph_count = len([p for p in paragraphs if p.strip()])

        return {
            "word_count": word_count,
            "sentence_count": sentence_count,
            "average_word_length": round(avg_word_length, 2),
            "unique_words": unique_words,
            "lexical_diversity": round(lexical_diversity, 2),
            "noun_phrases": noun_phrases,
            "verb_phrases": verb_phrases,
            "connectives": connectives,
            "paragraph_count": paragraph_count,
            "sentences_per_paragraph": round(sentence_count / max(1, paragraph_count), 2),
            "words_per_sentence": round(word_count / max(1, sentence_count), 2),
        }

    # ============== Competency Analysis ==============
    def analyze_competency(
        self,
        competency_number: int,
        essay_text: str,
        essay_theme: str,
        cohmetrix_results: Dict[str, Any],
        retroactive_analysis: AnalysisResultsModel = None,
    ) -> Dict[str, Any]:
        """
        Generic method to analyze a given competency using the corresponding prompt.
        """
        prompt_template = {
            1: PROMPT_ANALYSIS_COMPETENCY_1,
            2: PROMPT_ANALYSIS_COMPETENCY_2,
            3: PROMPT_ANALYSIS_COMPETENCY_3,
            4: PROMPT_ANALYSIS_COMPETENCY_4,
            5: PROMPT_ANALYSIS_COMPETENCY_5,
        }.get(competency_number)

        if not prompt_template:
            logger.error(f"No prompt found for competency {competency_number}")
            return {"error": f"No prompt found for competency {competency_number}"}

        prompt = prompt_template.format(
            essay_text=essay_text,
            essay_theme=essay_theme,
            word_count=cohmetrix_results.get("word_count", 0),
            sentence_count=cohmetrix_results.get("sentence_count", 0),
            average_word_length=cohmetrix_results.get("average_word_length", 0),
            lexical_diversity=cohmetrix_results.get("lexical_diversity", 0),
            unique_words=cohmetrix_results.get("unique_words", 0),
            paragraph_count=cohmetrix_results.get("paragraph_count", 0),
            sentences_per_paragraph=cohmetrix_results.get("sentences_per_paragraph", 0),
            connectives=cohmetrix_results.get("connectives", 0),
            noun_phrases=cohmetrix_results.get("noun_phrases", 0),
            verb_phrases=cohmetrix_results.get("verb_phrases", 0),
            words_per_sentence=cohmetrix_results.get("words_per_sentence", 0),
            retroactive_analysis=(
                retroactive_analysis.__dict__ if retroactive_analysis else {}
            ),
        )

        return self.llm.generate_response(prompt)

    # ============== Grading Method ==============
    def grade_competency(
        self, competency_analysis: Dict[str, Any], competency: str
    ) -> Dict[str, Any]:
        """
        Grades a competency based on its analysis.

        The competency parameter can be either the internal key
        (competency1, competency2, etc.)
        or the external ID from the BigQuery table.
        """
        # Map internal competency keys to external IDs if needed
        if competency.startswith("competency"):
            comp_num = int(competency.replace("competency", ""))
            competency_id = COMPETENCY_NUMBER_TO_ID.get(comp_num)
        else:
            competency_id = competency

        competency_name = COMPETENCIES.get(competency_id, "Unknown Competency")

        analysis_prompt = PROMPT_CRITERIA_GRADES.format(
            competency_name=competency_name,
            competency_analysis=json.dumps(competency_analysis, ensure_ascii=False),
            grading_criteria=GRADING_CRITERIA.get(competency_id),
        )

        analysis_criteria_grade = self.llm.generate_response(analysis_prompt)

        grades_prompt = PROMPT_GRADES.format(
            competency_name=competency_name,
            competency_analysis=json.dumps(competency_analysis, ensure_ascii=False),
            grading_criteria_analysis=json.dumps(
                analysis_criteria_grade, ensure_ascii=False
            ),
        )

        competency_grade = self.llm.generate_response(grades_prompt)

        return competency_grade

    def process_complete_essay(  # noqa: C901
        self, essay_text: str, essay_theme: str
    ) -> AnalysisResultsModel:
        """
        Processes the entire essay_function,
        performing linguistic analysis and competency evaluations.
        """
        cohmetrix_results = self.analyze_with_cohmetrix(essay_text)
        results = AnalysisResultsModel()

        for comp_number in range(1, 6):
            competency_id = COMPETENCY_NUMBER_TO_ID[comp_number]
            logger.info(f"Analyzing competency {comp_number} (ID: {competency_id})")

            analysis_result = self.analyze_competency(
                competency_number=comp_number,
                essay_text=essay_text,
                essay_theme=essay_theme,
                cohmetrix_results=cohmetrix_results,
                retroactive_analysis=results,
            )

            grade_result = self.grade_competency(analysis_result, competency_id)

            try:
                # Store the results using the competency ID instead of the numbered key
                if "analysis" not in analysis_result:
                    logger.warning(
                        f"Missing 'analysis' key for competency {competency_id} in analysis_result: {analysis_result}"  # noqa: E501
                    )
                else:
                    results.detailed_analysis[competency_id] = analysis_result["analysis"]

                if "grade" not in grade_result:
                    logger.warning(
                        f"Missing 'grade' key for competency {competency_id} in grade_result: {grade_result}"  # noqa: E501
                    )
                elif "justification" not in grade_result:
                    logger.warning(
                        f"Missing 'justification' key for competency {competency_id} in grade_result: {grade_result}"  # noqa: E501
                    )
                else:
                    results.grades[competency_id] = int(grade_result["grade"])
                    results.justifications[competency_id] = grade_result["justification"]

                # Verificar se há erros válidos
                erros_validos = []
                if "errors" in analysis_result:
                    for error in analysis_result.get("errors", []):
                        trecho = error.get("snippet", "").lower()
                        # Ensure snippet is valid and present in the text before adding
                        if trecho and trecho in essay_text.lower():
                            erros_validos.append(error)
                else:
                    logger.warning(
                        f"Missing 'errors' key for competency {competency_id} in analysis_result: {analysis_result}"  # noqa: E501
                    )

                results.errors[competency_id] = erros_validos
            except Exception as e:
                # Use f-strings for proper logging format
                logger.error(
                    f"Error processing results for competency {competency_id}: {e}"
                )
                logger.error(f"analysis_result: {analysis_result}")
                logger.error(f"grade_result: {grade_result}")

        # Soma das notas
        results.overall_grade = sum(results.grades.values())
        logger.info(f"Essay analyzed, overall grade: {results.overall_grade}")

        return results
