from pathlib import Path
import shutil
from flask import (
    Flask,
    abort,
    send_from_directory,
    request,
    redirect,
    url_for,
    render_template,
    jsonify,
)
from slugify import slugify
from .settings import CAPTURE_ROOT
from .const import settings
from .lib import get_camera_setting, CameraContext

app = Flask(__name__)
CURRENT_CAPTURE_THREAD = None


@app.route("/")
def home():
    Path(CAPTURE_ROOT).mkdir(exist_ok=True, parents=True)
    capture_paths = [x.name for x in Path(CAPTURE_ROOT).iterdir() if x.is_dir()]
    captures = []
    for path in capture_paths:
        captures.append(f"{path}")
    return render_template("main.html", captures=captures)


@app.route("/data/<path:path>")
def data(path=None):
    if not path:
        return abort(404)
    return send_from_directory(CAPTURE_ROOT, path)


@app.route("/create_capture", methods=["POST"])
def create_capture():
    capture_name = request.form.get("capture_name")
    if not capture_name:
        return redirect(url_for("home"))
    capture_name = slugify(capture_name)
    capture_path = Path(CAPTURE_ROOT, capture_name)
    if not capture_path.exists():
        capture_path.mkdir(parents=True)
    return redirect(url_for("capture", capture_name=capture_name))


@app.route("/delete_capture", methods=["POST"])
def delete_capture():
    capture_name = request.form.get("capture_name")
    if not capture_name:
        return redirect(url_for("home"))
    capture_name = slugify(capture_name)
    capture_path = Path(CAPTURE_ROOT, capture_name)
    if capture_path.exists():
        for fp in capture_path.glob("**/*"):
            if fp.is_file():
                fp.unlink()
        shutil.rmtree(capture_path)
    return redirect(url_for("home"))


@app.route("/<capture_name>")
def capture(capture_name="untitled"):
    capture_path = Path(CAPTURE_ROOT, capture_name)

    return "\n".join(
        [
            x.name
            for x in capture_path.iterdir()
            if x.suffix in [".jpg", ".jpeg", ".JPG", ".JPEG"]
        ]
    )


@app.route("/camera/get_current_focus")
def camera_get_current_focus():
    with CameraContext() as camera:
        focus = get_camera_setting(camera, settings.FOCUS_DISTANCE)
    return jsonify({"focus": focus})


@app.route("/capture/status/<capture_name>")
def capture_status(capture_name="untitled"):
    pass
