def start_server():
    from .app import app

    app.run(host="0.0.0.0", port=5000)


start_server()
