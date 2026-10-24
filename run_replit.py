"""Start the opt-in web demo; the desktop launcher remains run.py."""
import os


def main():
    try:
        port = int(os.environ.get("PORT", "8000"))
    except ValueError:
        raise SystemExit("PORT must be an integer from 1 to 65535") from None
    if not 1 <= port <= 65535:
        raise SystemExit("PORT must be an integer from 1 to 65535")
    from backend.replit import create_replit_app
    app = create_replit_app()
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port, workers=1)


if __name__ == "__main__":
    main()
