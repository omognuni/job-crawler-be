from common.vector_db import vector_db_client
from django.core.management.base import BaseCommand
from job.models import JobPosting, Resume
from tqdm import tqdm


class Command(BaseCommand):
    help = "Processes existing data and saves it to vector and graph databases."

    def add_arguments(self, parser):
        parser.add_argument(
            "--model",
            type=str,
            help="Specify the model to process: 'jobposting' or 'resume'.",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Process all models.",
        )

    def handle(self, *args, **options):
        process_job_postings = options["all"] or options["model"] == "jobposting"
        process_resumes = options["all"] or options["model"] == "resume"

        if not process_job_postings and not process_resumes:
            self.stdout.write(
                self.style.WARNING(
                    "Please specify a model to process with --model or use --all."
                )
            )
            return

        if process_job_postings:
            self.process_job_postings()

        if process_resumes:
            self.process_resumes()

        self.stdout.write(self.style.SUCCESS("Finished processing existing data."))

    def process_job_postings(self):
        self.stdout.write("Processing existing JobPostings...")
        job_postings = JobPosting.objects.all()
        for job_posting in tqdm(job_postings, desc="JobPostings"):
            # Calling .save() triggers the post_save signal in signals.py
            job_posting.save()
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully processed {job_postings.count()} JobPostings."
            )
        )

    def process_resumes(self):
        self.stdout.write("Processing and embedding existing Resumes...")
        resumes = Resume.objects.all()
        collection = vector_db_client.get_or_create_collection("resumes")

        documents = []
        ids = []
        metadatas = []
        for resume in tqdm(resumes, desc="Resumes"):
            documents.append(resume.content)
            ids.append(str(resume.user_id))
            metadatas.append({"user_id": resume.user_id})

        if documents:
            vector_db_client.upsert_documents(
                collection=collection,
                documents=documents,
                metadatas=metadatas,
                ids=ids,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully processed and embedded {len(documents)} Resumes."
            )
        )
