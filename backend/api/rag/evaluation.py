"""RAGAS evaluation on a manually prepared test set.

Each metric is reported separately (never merged into one "accuracy" score):
faithfulness, answer relevancy, context precision and context recall.
"""
import json
import math
import threading
import traceback
from datetime import datetime, timezone

from django.conf import settings

from . import models as local_models
from . import qa

METRICS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
TESTSET_PATH = settings.DATA_DIR / "testset.json"
RESULTS_PATH = settings.DATA_DIR / "eval_results.json"
DEFAULT_TESTSET = settings.BASE_DIR / "api" / "default_testset.json"

_state = {"running": False, "progress": "", "error": ""}
_lock = threading.Lock()


def load_testset() -> list[dict]:
    path = TESTSET_PATH if TESTSET_PATH.exists() else DEFAULT_TESTSET
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_testset(items: list[dict]):
    clean = [
        {"question": str(i.get("question", "")).strip(), "ground_truth": str(i.get("ground_truth", "")).strip()}
        for i in items
        if str(i.get("question", "")).strip() and str(i.get("ground_truth", "")).strip()
    ]
    TESTSET_PATH.write_text(json.dumps(clean, indent=2, ensure_ascii=False), encoding="utf-8")
    return clean


def load_results():
    if RESULTS_PATH.exists():
        return json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    return None


def status() -> dict:
    return {**_state, "results": load_results()}


def _ragas_components():
    from langchain_core.rate_limiters import InMemoryRateLimiter
    from langchain_google_genai import ChatGoogleGenerativeAI
    from ragas.embeddings import BaseRagasEmbeddings
    from ragas.llms import LangchainLLMWrapper

    class LocalEmbeddings(BaseRagasEmbeddings):
        def embed_query(self, text):
            return local_models.embed([text])[0]

        def embed_documents(self, texts):
            return local_models.embed(texts)

        async def aembed_query(self, text):
            return self.embed_query(text)

        async def aembed_documents(self, texts):
            return self.embed_documents(texts)

    chat = ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0,
        thinking_budget=0,
        max_retries=6,
        rate_limiter=InMemoryRateLimiter(requests_per_second=0.15, check_every_n_seconds=0.5),
    )
    return LangchainLLMWrapper(chat), LocalEmbeddings()


def _number(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(value) else round(value, 4)


def _run():
    try:
        from ragas import EvaluationDataset, RunConfig, evaluate
        from ragas.metrics import AnswerRelevancy, Faithfulness, LLMContextPrecisionWithReference, LLMContextRecall

        testset = load_testset()
        if not testset:
            raise ValueError("The test set is empty. Add questions with expected answers first.")

        rows = []
        for i, item in enumerate(testset, start=1):
            _state["progress"] = f"Answering question {i}/{len(testset)}"
            result = qa.answer(item["question"])
            rows.append(
                {
                    "user_input": item["question"],
                    "response": result["answer"],
                    "retrieved_contexts": result["contexts"] or [""],
                    "reference": item["ground_truth"],
                }
            )

        _state["progress"] = "Scoring with RAGAS (this can take a few minutes on the free tier)"
        llm, embeddings = _ragas_components()
        metrics = [
            Faithfulness(),
            AnswerRelevancy(strictness=1),
            LLMContextPrecisionWithReference(),
            LLMContextRecall(),
        ]
        scored = evaluate(
            EvaluationDataset.from_list(rows),
            metrics=metrics,
            llm=llm,
            embeddings=embeddings,
            run_config=RunConfig(max_workers=2, timeout=240, max_retries=6, max_wait=60),
            show_progress=False,
            raise_exceptions=False,
        )
        frame = scored.to_pandas()
        rename = {"llm_context_precision_with_reference": "context_precision"}
        frame = frame.rename(columns=rename)

        per_question = []
        for row, item in zip(frame.to_dict(orient="records"), testset):
            per_question.append(
                {
                    "question": item["question"],
                    "ground_truth": item["ground_truth"],
                    "answer": row.get("response", ""),
                    "contexts": row.get("retrieved_contexts", []),
                    **{m: _number(row.get(m)) for m in METRICS},
                }
            )

        averages = {}
        for metric in METRICS:
            values = [q[metric] for q in per_question if q[metric] is not None]
            averages[metric] = round(sum(values) / len(values), 4) if values else None

        RESULTS_PATH.write_text(
            json.dumps(
                {
                    "run_at": datetime.now(timezone.utc).isoformat(),
                    "model": settings.GEMINI_MODEL,
                    "num_questions": len(per_question),
                    "metrics": averages,
                    "per_question": per_question,
                },
                indent=2,
                ensure_ascii=False,
                default=str,
            ),
            encoding="utf-8",
        )
        _state["progress"] = "Finished"
    except Exception as error:  # noqa: BLE001
        traceback.print_exc()
        _state["error"] = str(error)
        _state["progress"] = "Failed"
    finally:
        _state["running"] = False


def start() -> bool:
    with _lock:
        if _state["running"]:
            return False
        _state.update(running=True, progress="Starting", error="")
    threading.Thread(target=_run, daemon=True).start()
    return True
