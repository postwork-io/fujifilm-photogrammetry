from pathlib import Path
import json
from flask import (
    Flask,
    request,
    jsonify,
)
from werkzeug.utils import secure_filename

from .worker import WorkerPool
from .logging_utils import logger

app = Flask(__name__)

app.config["UPLOAD_FOLDER"] = "/uploads"

WORKER_POOL = WorkerPool()
WORKER_POOL.start()


@app.route("/upload", methods=["POST", "GET"])
def create_capture():
    data = json.load(request.files["data"])
    job_name = data.get("job_name", "default_job")
    post_processes = data.get("post_processes")
    logger.info(f"Received upload request for {job_name}")
    files = request.files.getlist("files")
    local_paths = []
    for file in files:
        if not file.filename == "":
            filename = secure_filename(file.filename)
            file_path = Path(app.config["UPLOAD_FOLDER"], job_name, "source", filename)
            file_path.parent.mkdir(exist_ok=True, parents=True)
            file.save(file_path)
            local_paths.append(file_path.as_posix())

    WORKER_POOL.add_to_pool(
        {"job_name": job_name, "post_processes": post_processes, "files": local_paths}
    )
    return jsonify({})
