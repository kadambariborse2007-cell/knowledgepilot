from django.db import models


class Document(models.Model):
    name = models.CharField(max_length=255)
    stored_name = models.CharField(max_length=255, unique=True)
    size = models.BigIntegerField()
    pages = models.IntegerField(default=0)
    chunks = models.IntegerField(default=0)
    flagged_chunks = models.IntegerField(default=0)
    status = models.CharField(max_length=20, default="processing")
    error = models.TextField(blank=True)
    summary = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]


class ChatSession(models.Model):
    title = models.CharField(max_length=200, default="New chat")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]


class ChatMessage(models.Model):
    session = models.ForeignKey(ChatSession, related_name="messages", on_delete=models.CASCADE)
    role = models.CharField(max_length=10)
    content = models.TextField()
    sources = models.JSONField(default=list, blank=True)
    warnings = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
