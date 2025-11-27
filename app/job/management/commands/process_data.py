"""
Management command to process existing JobPostings and Resumes using Celery tasks.

이 커맨드는 기존 데이터를 비동기적으로 처리하여 ChromaDB와 Neo4j에 저장합니다.
"""

import time

from celery import group
from django.core.management.base import BaseCommand
from job.models import JobPosting, Resume
from job.tasks import process_job_posting
from resume.tasks import process_resume


class Command(BaseCommand):
    help = "Processes existing data and saves it to vector and graph databases using Celery tasks."

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
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Number of tasks to submit in each batch (default: 100).",
        )
        parser.add_argument(
            "--wait",
            action="store_true",
            help="Wait for all tasks to complete and show progress.",
        )

    def handle(self, *args, **options):
        process_job_postings_flag = options["all"] or options["model"] == "jobposting"
        process_resumes_flag = options["all"] or options["model"] == "resume"
        batch_size = options["batch_size"]
        wait = options["wait"]

        if not process_job_postings_flag and not process_resumes_flag:
            self.stdout.write(
                self.style.WARNING(
                    "Please specify a model to process with --model or use --all."
                )
            )
            return

        if process_job_postings_flag:
            self.process_job_postings(batch_size, wait)

        if process_resumes_flag:
            self.process_resumes(batch_size, wait)

        self.stdout.write(
            self.style.SUCCESS("Finished submitting all tasks to Celery.")
        )

    def process_job_postings(self, batch_size, wait):
        """
        Process all JobPostings by submitting them to Celery queue.
        """
        self.stdout.write(self.style.SUCCESS("Fetching JobPostings..."))
        job_posting_ids = list(JobPosting.objects.values_list("posting_id", flat=True))
        total = len(job_posting_ids)

        if total == 0:
            self.stdout.write(self.style.WARNING("No JobPostings found."))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Submitting {total} JobPosting tasks to Celery queue..."
            )
        )

        # Submit tasks in batches
        tasks_submitted = 0
        for i in range(0, total, batch_size):
            batch = job_posting_ids[i : i + batch_size]
            task_group = group(
                process_job_posting.s(posting_id) for posting_id in batch
            )
            result = task_group.apply_async()

            tasks_submitted += len(batch)
            self.stdout.write(
                f"Submitted batch {i // batch_size + 1}: {tasks_submitted}/{total} tasks"
            )

            if wait:
                # Wait for current batch to complete
                result.get(timeout=600)  # 10 minutes timeout per batch
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Completed batch {i // batch_size + 1}: {tasks_submitted}/{total} tasks"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully submitted {total} JobPosting tasks. "
                f"Check Celery worker logs for progress."
            )
        )

    def process_resumes(self, batch_size, wait):
        """
        Process all Resumes by submitting them to Celery queue.
        """
        self.stdout.write(self.style.SUCCESS("Fetching Resumes..."))
        resume_ids = list(Resume.objects.values_list("id", flat=True))
        total = len(resume_ids)

        if total == 0:
            self.stdout.write(self.style.WARNING("No Resumes found."))
            return

        self.stdout.write(
            self.style.SUCCESS(f"Submitting {total} Resume tasks to Celery queue...")
        )

        # Submit tasks in batches
        tasks_submitted = 0
        for i in range(0, total, batch_size):
            batch = resume_ids[i : i + batch_size]
            task_group = group(process_resume.s(resume_id) for resume_id in batch)
            result = task_group.apply_async()

            tasks_submitted += len(batch)
            self.stdout.write(
                f"Submitted batch {i // batch_size + 1}: {tasks_submitted}/{total} tasks"
            )

            if wait:
                # Wait for current batch to complete
                result.get(
                    timeout=1200
                )  # 20 minutes timeout per batch (LLM calls take longer)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Completed batch {i // batch_size + 1}: {tasks_submitted}/{total} tasks"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully submitted {total} Resume tasks. "
                f"Check Celery worker logs for progress."
            )
        )
