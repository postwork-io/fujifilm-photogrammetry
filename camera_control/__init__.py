from .lib import capture_image, capture_focus_bracket

__all__ = ["capture_focus_bracket", "capture_image"]


def start_server():
    from .app import app

    app.run(host=0.0.0.0, port=5000)
