import subprocess


def handle_launch_app(params: dict) -> dict:
    try:
        subprocess.Popen(params["path"])
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
