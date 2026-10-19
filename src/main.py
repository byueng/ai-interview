import uvicorn

from pathlib import Path
from dotenv import load_dotenv

from runtime import run_time

def main():
    env_path = Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(env_path)
    uvicorn.run(
        "main:run_time",
        host = "127.0.0.1",
        port = 7022,
        reload=True,
        factory=True
    )
    

if __name__ == "__main__":
    main()