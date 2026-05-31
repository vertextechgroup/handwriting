import os
import logging
from flask import Blueprint, request, jsonify, send_file, abort, current_app
from app.utils.file_utils import is_allowed_file, secure_filename
from app.utils.session_utils import make_session_id, make_session_dir
from app.services.extractor_service import extract_text
from app.services.splitter_service import split_text_into_pages, get_page_stats
from app.models.job import JobStatus

api_bp = Blueprint("api", __name__)
logger = logging.getLogger(__name__)

@api_bp.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files["file"]
    if not file or not file.filename:
        return jsonify({"error": "No file selected"}), 400
    
    if not is_allowed_file(file.filename):
        return jsonify({"error": "File type not supported"}), 400

    session_id = make_session_id()
    upload_dir = make_session_dir(current_app.config["UPLOAD_DIR"], session_id)
    
    filename = secure_filename(file.filename)
    file_path = os.path.join(upload_dir, filename)
    file.save(file_path)

    job = current_app.job_manager.create_job(session_id)
    job.update(status=JobStatus.UPLOADED, filename=filename, file_path=file_path)

    return jsonify({
        "session_id": session_id,
        "filename": filename,
        "size": os.path.getsize(file_path)
    })

@api_bp.route("/extract-text", methods=["POST"])
def extract():
    data = request.json
    session_id = data.get("session_id")
    job = current_app.job_manager.get_job(session_id)
    
    if not job or not job.file_path:
        return jsonify({"error": "Job not found"}), 404

    try:
        text = extract_text(job.file_path)
        job.update(text=text, status=JobStatus.EXTRACTED)
        
        # Default stats
        pages = split_text_into_pages(text)
        stats = get_page_stats(pages)
        
        return jsonify({
            "text": text,
            "word_count": len(text.split()),
            "char_count": len(text),
            "page_count": stats["page_count"]
        })
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        return jsonify({"error": str(e)}), 500

@api_bp.route("/generate", methods=["POST"])
def generate():
    data = request.json
    session_id = data.get("session_id")
    text_override = data.get("text")
    
    # New parameters
    font_name = data.get("font_name", "default.ttf")
    ink_color = data.get("ink_color", "#000080")
    paper_type = data.get("paper_type", "ruled")
    pen_style = data.get("pen_style", "gel")
    realism = float(data.get("realism", 1.0))
    dpi = int(data.get("dpi", 300))
    
    job = current_app.job_manager.get_job(session_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    text = text_override or job.text
    if not text:
        return jsonify({"error": "No text to generate"}), 400

    current_app.job_manager.start_generation(
        session_id, 
        text, 
        font_name=font_name,
        ink_color=ink_color,
        paper_type=paper_type,
        pen_style=pen_style,
        realism=realism,
        dpi=dpi
    )

    return jsonify({"session_id": session_id})

@api_bp.route("/status/<session_id>", methods=["GET"])
def status(session_id):
    job = current_app.job_manager.get_job(session_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    
    return jsonify(job.to_dict())

@api_bp.route("/preview-image/<session_id>/<filename>", methods=["GET"])
def preview(session_id, filename):
    if ".." in session_id or ".." in filename:
        abort(400)
    
    # Check generated first, then previews
    for base in [current_app.config["GENERATED_DIR"], current_app.config["PREVIEW_DIR"]]:
        path = os.path.join(base, session_id, filename)
        if os.path.isfile(path):
            try:
                return send_file(os.path.abspath(path))
            except Exception as e:
                logger.error(f"Error sending file {path}: {e}")
                abort(500)
    
    abort(404)

@api_bp.route("/download-pdf/<session_id>", methods=["GET"])
def download_pdf(session_id):
    job = current_app.job_manager.get_job(session_id)
    if not job or not job.pdf_path or not os.path.isfile(job.pdf_path):
        abort(404)
    return send_file(job.pdf_path, as_attachment=True, download_name="handwriting.pdf")

@api_bp.route("/download-zip/<session_id>", methods=["GET"])
def download_zip(session_id):
    job = current_app.job_manager.get_job(session_id)
    if not job or not job.zip_path or not os.path.isfile(job.zip_path):
        abort(404)
    return send_file(job.zip_path, as_attachment=True, download_name="handwriting_pages.zip")
