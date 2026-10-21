import json
import uuid

from django.conf import settings
from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.response import Response

from .models import ChatMessage, ChatSession, Document
from .rag import evaluation, llm, qa, store
from .rag.ingest import ingest_document
from .rag.summary import summarize

ALLOWED_EXTENSIONS = {".pdf", ".txt"}


def serialize_document(doc):
    return {
        "id": doc.id,
        "name": doc.name,
        "size": doc.size,
        "pages": doc.pages,
        "chunks": doc.chunks,
        "flagged_chunks": doc.flagged_chunks,
        "status": doc.status,
        "error": doc.error,
        "has_summary": bool(doc.summary),
        "uploaded_at": doc.uploaded_at.isoformat(),
    }


def serialize_message(msg):
    return {
        "id": msg.id,
        "role": msg.role,
        "content": msg.content,
        "sources": msg.sources,
        "warnings": msg.warnings,
        "created_at": msg.created_at.isoformat(),
    }


def parse_document_ids(value):
    if not value:
        return None
    ids = [int(v) for v in value if str(v).isdigit()]
    return ids or None


@api_view(["GET"])
def health(request):
    return Response({"status": "ok", "gemini_configured": bool(settings.GEMINI_API_KEY)})


@api_view(["POST"])
@parser_classes([MultiPartParser])
def upload(request):
    files = request.FILES.getlist("files")
    if not files:
        return Response({"error": "No files received. Use the form field 'files'."}, status=400)
    if len(files) > settings.MAX_UPLOAD_FILES:
        return Response({"error": f"You can upload at most {settings.MAX_UPLOAD_FILES} files at once."}, status=400)
    for f in files:
        suffix = ("." + f.name.rsplit(".", 1)[-1].lower()) if "." in f.name else ""
        if suffix not in ALLOWED_EXTENSIONS:
            return Response({"error": f'"{f.name}" is not allowed. Only PDF and TXT files are supported.'}, status=400)
        if f.size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            return Response({"error": f'"{f.name}" is larger than {settings.MAX_UPLOAD_SIZE_MB} MB.'}, status=400)

    results = []
    for f in files:
        suffix = "." + f.name.rsplit(".", 1)[-1].lower()
        stored_name = f"{uuid.uuid4().hex}{suffix}"
        path = settings.UPLOAD_DIR / stored_name
        with open(path, "wb") as out:
            for chunk in f.chunks():
                out.write(chunk)
        doc = Document.objects.create(name=f.name, stored_name=stored_name, size=f.size)
        try:
            ingest_document(doc, path)
        except Exception as error:  # noqa: BLE001
            doc.status = "error"
            doc.error = f"Could not process file: {error}"
            doc.save()
        results.append(serialize_document(doc))
    return Response({"uploaded": results}, status=201)


@api_view(["GET"])
def files(request):
    return Response({"files": [serialize_document(d) for d in Document.objects.all()]})


@api_view(["DELETE"])
def file_detail(request, pk):
    doc = Document.objects.filter(pk=pk).first()
    if not doc:
        return Response({"error": "File not found."}, status=404)
    store.delete_document(doc.id)
    (settings.UPLOAD_DIR / doc.stored_name).unlink(missing_ok=True)
    doc.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
def file_flagged(request, pk):
    chunks = [c for c in store.all_chunks([pk]) if c["flagged"]]
    return Response({"flagged": [qa.warning_payload(c) for c in chunks]})


@api_view(["POST"])
@parser_classes([JSONParser])
def summary(request, pk):
    doc = Document.objects.filter(pk=pk).first()
    if not doc:
        return Response({"error": "File not found."}, status=404)
    if doc.summary and not request.data.get("refresh"):
        return Response({"document_id": doc.id, "summary": doc.summary, "cached": True})
    try:
        result = summarize(doc.id)
    except llm.LLMError as error:
        return Response({"error": str(error)}, status=502)
    doc.summary = result["summary"]
    doc.save(update_fields=["summary"])
    return Response({"document_id": doc.id, "summary": doc.summary, "map_calls": result["map_calls"], "cached": False})


@api_view(["GET"])
def sessions(request):
    return Response(
        {"sessions": [{"id": s.id, "title": s.title, "updated_at": s.updated_at.isoformat()} for s in ChatSession.objects.all()]}
    )


@api_view(["GET", "DELETE"])
def session_detail(request, pk):
    session = ChatSession.objects.filter(pk=pk).first()
    if not session:
        return Response({"error": "Chat not found."}, status=404)
    if request.method == "DELETE":
        session.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    return Response(
        {"id": session.id, "title": session.title, "messages": [serialize_message(m) for m in session.messages.all()]}
    )


def _event(payload):
    return json.dumps(payload, ensure_ascii=False) + "\n"


@api_view(["POST"])
@parser_classes([JSONParser])
def chat(request):
    question = str(request.data.get("question", "")).strip()
    if not question:
        return Response({"error": "Please type a question."}, status=400)
    if len(question) > 2000:
        return Response({"error": "Question is too long (max 2000 characters)."}, status=400)
    document_ids = parse_document_ids(request.data.get("document_ids"))

    session = ChatSession.objects.filter(pk=request.data.get("session_id") or 0).first()
    if not session:
        session = ChatSession.objects.create(title=question[:80])
    history = [{"role": m.role, "content": m.content} for m in session.messages.all()]
    ChatMessage.objects.create(session=session, role="user", content=question)

    def generate():
        yield _event({"type": "session", "session_id": session.id, "title": session.title})
        try:
            clean, flagged = qa.retrieve(question, history, document_ids)
        except Exception as error:  # noqa: BLE001
            yield _event({"type": "error", "message": f"Search failed: {error}"})
            return
        warnings = [qa.warning_payload(c) for c in flagged]
        if warnings:
            yield _event({"type": "warnings", "warnings": warnings})

        if not clean:
            text, sources = qa.NOT_FOUND, []
            yield _event({"type": "token", "text": text})
        else:
            parts = []
            try:
                for piece in llm.stream(qa.build_prompt(question, clean, history), qa.SYSTEM_PROMPT):
                    parts.append(piece)
                    yield _event({"type": "token", "text": piece})
            except llm.LLMError as error:
                yield _event({"type": "error", "message": str(error)})
                if not parts:
                    return
            text = "".join(parts).strip()
            sources = qa.cited_sources(text, clean)

        ChatMessage.objects.create(session=session, role="assistant", content=text, sources=sources, warnings=warnings)
        session.save(update_fields=["updated_at"])
        yield _event({"type": "sources", "sources": sources})
        yield _event({"type": "done"})

    response = StreamingHttpResponse(generate(), content_type="application/x-ndjson")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@api_view(["GET", "PUT"])
@parser_classes([JSONParser])
def eval_testset(request):
    if request.method == "PUT":
        items = request.data.get("items")
        if not isinstance(items, list):
            return Response({"error": "Send {\"items\": [{\"question\": ..., \"ground_truth\": ...}]}"}, status=400)
        return Response({"items": evaluation.save_testset(items)})
    return Response({"items": evaluation.load_testset()})


@api_view(["POST"])
def eval_run(request):
    if not settings.GEMINI_API_KEY:
        return Response({"error": "GEMINI_API_KEY is not set on the server."}, status=400)
    if not evaluation.start():
        return Response({"error": "An evaluation is already running."}, status=409)
    return Response({"started": True}, status=202)


@api_view(["GET"])
def eval_status(request):
    return Response(evaluation.status())
