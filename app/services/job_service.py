import threading
import logging
import os
from typing import Dict, List, Optional
from app.models.job import Job, JobStatus
from app.renderer.engine import HandwritingRenderer
from app.services.pdf_service import build_pdf, build_zip
from app.utils.file_utils import generate_thumbnail
from app.utils.session_utils import make_session_dir

logger = logging.getLogger(__name__)

class JobManager:
    def __init__(self, generated_dir: str, preview_dir: str):
        self.jobs: Dict[str, Job] = {}
        self.lock = threading.Lock()
        self.generated_dir = generated_dir
        self.preview_dir = preview_dir

    def create_job(self, session_id: str) -> Job:
        with self.lock:
            job = Job(session_id=session_id)
            self.jobs[session_id] = job
            return job

    def get_job(self, session_id: str) -> Optional[Job]:
        with self.lock:
            return self.jobs.get(session_id)

    def update_job(self, session_id: str, **kwargs):
        with self.lock:
            if session_id in self.jobs:
                self.jobs[session_id].update(**kwargs)

    def start_generation(self, session_id: str, text: str, 
                         font_name: str = "default.ttf", 
                         ink_color: str = "#000080", 
                         paper_type: str = "ruled",
                         pen_style: str = "gel",
                         realism: float = 1.0,
                         dpi: int = 300):
        job = self.get_job(session_id)
        if not job:
            return

        job.update(
            status=JobStatus.GENERATING,
            progress=0,
            current_page=0
        )

        thread = threading.Thread(
            target=self._run_job,
            args=(session_id, text, font_name, ink_color, paper_type, pen_style, realism, dpi),
            daemon=True
        )
        thread.start()

    def _run_job(self, session_id: str, text: str, font_name: str, 
                 ink_color: str, paper_type: str, pen_style: str, 
                 realism: float, dpi: int):
        output_dir = make_session_dir(self.generated_dir, session_id)
        thumb_dir = make_session_dir(self.preview_dir, session_id)
        
        # Path to font
        font_path = os.path.join("static", "fonts", font_name)
        if not os.path.exists(font_path):
            # Fallback to a system handwriting-like font if default doesn't exist
            # Prefer Ink Free, then Segoe Script, then Segoe Print, then Comic Sans
            fallbacks = [
                "C:\\Windows\\Fonts\\Inkfree.ttf",
                "C:\\Windows\\Fonts\\segoesc.ttf",
                "C:\\Windows\\Fonts\\segoepr.ttf",
                "C:\\Windows\\Fonts\\comic.ttf",
                "C:\\Windows\\Fonts\\arial.ttf"
            ]
            font_path = next((f for f in fallbacks if os.path.exists(f)), "C:\\Windows\\Fonts\\arial.ttf")

        try:
            renderer = HandwritingRenderer(
                dpi=dpi,
                pen_style=pen_style,
                ink_color=ink_color,
                paper_type=paper_type,
                realism_intensity=realism
            )
            
            def progress_hook(current, total):
                progress = int((current / total) * 100)
                self.update_job(session_id, current_page=current, total_pages=total, progress=progress)

            image_paths = renderer.render(
                text=text,
                font_path=font_path,
                output_dir=output_dir,
                progress_callback=progress_hook
            )
            
            # Generate thumbnails
            thumb_paths = []
            for img in image_paths:
                thumb = generate_thumbnail(img, thumb_dir)
                if thumb:
                    thumb_paths.append(thumb)

            # Build PDF and ZIP
            pdf_path = os.path.join(output_dir, "handwriting_output.pdf")
            build_pdf(image_paths, pdf_path)
            
            zip_path = os.path.join(output_dir, "handwriting_pages.zip")
            build_zip(image_paths, zip_path)

            self.update_job(
                session_id,
                status=JobStatus.COMPLETED,
                progress=100,
                image_paths=image_paths,
                thumb_paths=thumb_paths,
                pdf_path=pdf_path,
                zip_path=zip_path
            )
            logger.info(f"Job {session_id} completed successfully.")

        except Exception as e:
            logger.error(f"Job {session_id} failed: {e}", exc_info=True)
            self.update_job(session_id, status=JobStatus.FAILED, error=str(e))

