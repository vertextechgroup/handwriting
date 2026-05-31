import os
import uuid
import shutil
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def make_session_id() -> str:
    """Generate a unique session ID."""
    return uuid.uuid4().hex

def make_session_dir(base_dir: str, session_id: str) -> str:
    """Create and return a session-specific directory."""
    path = os.path.join(base_dir, session_id)
    os.makedirs(path, exist_ok=True)
    return path

def cleanup_old_sessions(base_dirs: list[str], max_age_hours: int = 24):
    """Delete session directories older than max_age_hours."""
    now = datetime.now()
    for base_dir in base_dirs:
        if not os.path.exists(base_dir):
            continue
        for session_id in os.listdir(base_dir):
            session_path = os.path.join(base_dir, session_id)
            if not os.path.isdir(session_path):
                continue
            
            mtime = datetime.fromtimestamp(os.path.getmtime(session_path))
            if now - mtime > timedelta(hours=max_age_hours):
                try:
                    shutil.rmtree(session_path)
                    logger.info(f"Cleaned up old session directory: {session_path}")
                except Exception as e:
                    logger.error(f"Failed to cleanup {session_path}: {e}")
