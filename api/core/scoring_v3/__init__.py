"""
Scoring V3 - Multi-Agent AI Değerlendirme Sistemi

Bu modül, CV değerlendirmesi için çoklu AI model kullanır:
- Gemini 2.5 Pro + Hermes 4 70B paralel çalışır
- Puan farkı > 15 veya eligible uyumsuzluğu varsa Claude hakim olur

Kullanım:
    from api.core.scoring_v3 import evaluate_candidate_sync

    result = evaluate_candidate_sync(
        candidate_id=444,
        position_id=7807,
        candidate_data={...},
        position_data={...}
    )

    if result.success:
        print(f"Score: {result.total_score}")
    else:
        print(f"Hata: {result.error_message}")
"""

from .smart_prompt_builder import SmartPromptBuilder
from .ai_evaluator import AIEvaluator, FinalEvaluation, EvaluationResult
from .evaluate_candidate import (
    CandidateEvaluator,
    CandidateEvaluationRequest,
    CandidateEvaluationResponse,
    evaluate_candidate,
    evaluate_candidate_sync
)

__all__ = [
    # Prompt Builder
    "SmartPromptBuilder",

    # AI Evaluator
    "AIEvaluator",
    "FinalEvaluation",
    "EvaluationResult",

    # Candidate Evaluator (Orchestrator)
    "CandidateEvaluator",
    "CandidateEvaluationRequest",
    "CandidateEvaluationResponse",

    # Convenience Functions
    "evaluate_candidate",
    "evaluate_candidate_sync"
]

__version__ = "3.0.0"
