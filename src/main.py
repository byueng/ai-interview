import uvicorn

from runtime import run_time

def main():
    uvicorn.run(
        "main:run_time",
        host = "127.0.0.1",
        port = 7022,
        reload=True,
        factory=True
    )
    

if __name__ == "__main__":
    main()