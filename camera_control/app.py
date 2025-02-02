from pathlib import Path
import random
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
from .lib import (  # noqa f401
    get_camera_setting,
    CameraContext,
    StoppableThread,
    bulk_capture_turntable,
    mock_bulk_capture,
)

app = Flask(__name__)
CURRENT_CAPTURE_THREAD = None


@app.route("/")
def home():
    Path(CAPTURE_ROOT).mkdir(exist_ok=True, parents=True)
    capture_paths = sorted([x.name for x in Path(CAPTURE_ROOT).iterdir() if x.is_dir()])
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

    return render_template("capture.html", capture_name=capture_name)


@app.route("/<capture_name>/gallery")
def gallery(capture_name="untitled"):
    images = [
        x.name
        for x in Path(CAPTURE_ROOT, capture_name).iterdir()
        if x.suffix in [".jpg", ".JPG", ".jpeg", ".JPEG"]
    ]

    return render_template("gallery.html", capture_name=capture_name, images=images)


@app.route("/camera/get_current_focus")
def camera_get_current_focus():
    with CameraContext() as camera:
        focus = get_camera_setting(camera, settings.FOCUS_DISTANCE)
    return jsonify({"focus": focus})


@app.route("/mock_camera/get_current_focus")
def mock_camera_get_current_focus():
    focus = random.randint(0, 1730)
    return jsonify({"focus": focus})


@app.route("/start_capture", methods=["POST"])
def start_capture():
    global CURRENT_CAPTURE_THREAD
    if CURRENT_CAPTURE_THREAD is not None:
        return redirect("capture_status")
    starting_number = request.form.get("starting_number")
    image_count = request.form.get("image_count")
    degree_per_capture = request.form.get("degree_per_capture")
    capture_name = request.form.get("capture_name")
    focus_bracketing = "focus_bracketing" in request.form
    focus_steps = request.form.get("focus_steps")
    focus_start = request.form.get("focus_start")
    focus_stop = request.form.get("focus_stop")
    if focus_bracketing:
        focus_kwargs = {
            "focus_start": int(focus_start),
            "focus_stop": int(focus_stop),
            "focus_steps": int(focus_steps),
        }
    else:
        focus_kwargs = None
    CURRENT_CAPTURE_THREAD = StoppableThread(
        target=bulk_capture_turntable,
        kwargs={
            "capture_root_dir": CAPTURE_ROOT,
            "capture_name": capture_name,
            "image_count": image_count,
            "start_number": starting_number,
            "focus_bracket_settings": focus_kwargs,
            "degree_per_capture": float(degree_per_capture),
        },
    )

    CURRENT_CAPTURE_THREAD.start()
    return redirect("capture_status")


@app.route("/stop_capture", methods=["POST"])
def stop_capture():
    global CURRENT_CAPTURE_THREAD
    if CURRENT_CAPTURE_THREAD:
        CURRENT_CAPTURE_THREAD.stop()
        CURRENT_CAPTURE_THREAD.join()
        CURRENT_CAPTURE_THREAD = None
    return redirect("capture_status")


@app.route("/progress")
def capture_status():
    global CURRENT_CAPTURE_THREAD

    if CURRENT_CAPTURE_THREAD is None:
        return jsonify({"message": "", "progress": 0.0, "running": False})
    elif not CURRENT_CAPTURE_THREAD.is_alive():
        CURRENT_CAPTURE_THREAD.join()
        CURRENT_CAPTURE_THREAD = None
        return jsonify({"message": "Complete", "progress": 100.0, "running": False})
    else:
        message, progress = CURRENT_CAPTURE_THREAD.get_status()
        return jsonify(
            {"message": message, "progress": round(progress * 100), "running": True}
        )
