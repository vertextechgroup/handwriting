from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import time

class JobStatus(Enum):
    PENDING = "pending"
    UPLOADED = "uploaded"
    EXTRACTED = "extracted"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class Job:
    session_id: str
    status: JobStatus = JobStatus.PENDING
    filename: Optional[str] = None
    file_path: Optional[str] = None
    text: str = ""
    pages_text: List[str] = field(default_factory=list)
    total_pages: int = 0
    current_page: int = 0
    progress: int = 0
    image_paths: List[str] = field(default_factory=list)
    thumb_paths: List[str] = field(default_factory=list)
    pdf_path: Optional[str] = None
    zip_path: Optional[str] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def update(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "status": self.status.value,
            "filename": self.filename,
            "total_pages": self.total_pages,
            "current_page": self.current_page,
            "progress": self.progress,
            "error": self.error,
            "page_count": len(self.image_paths),
            "preview_urls": [f"/preview-image/{self.session_id}/{os.path.basename(p)}" for p in self.image_paths],
            "thumb_urls": [f"/preview-image/{self.session_id}/thumb_{os.path.basename(p)}" for p in self.image_paths],
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

import os # Needed for os.path.basename in to_dict
