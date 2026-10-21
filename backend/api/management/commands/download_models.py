from django.core.management.base import BaseCommand

from api.rag import models


class Command(BaseCommand):
    help = "Download the local embedding and reranker models (run once at build time)."

    def handle(self, *args, **options):
        models.embed(["warm up"])
        models.rerank("warm up", ["warm up"])
        self.stdout.write(self.style.SUCCESS("Models downloaded."))
