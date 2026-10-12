import os
from pathlib import Path

from dataclasses import dataclass
from dotenv import load_dotenv

class ModelConfigError(ValueError):
    pass

@dataclass
class ModelConfig:
    api_key: str
    base_url: str
    model_name: str
    temperature: float
    
    @classmethod
    def validate_dotfile(cls):
        env_path = Path(__file__).resolve().parents[2] / ".env"
        load_dotenv(env_path)
        api_key = os.environ.get("API_KEY")
        base_url = os.environ.get("BASE_URL")
        model_name = os.environ.get("MODEL_NAME")
        try:
            temperature = float(os.environ.get("TEMPERATURE", "0.8"))
        except ValueError as exc:
            raise ModelConfigError("TEMPERATURE must be a number.") from exc

        if not api_key: 
            raise ModelConfigError("Missing api key in model config.")
        if not base_url:
            raise ModelConfigError("Missing base url in model config.")
        if not model_name:
            raise ModelConfigError("Missing model name in model config")
        
        return cls(api_key, base_url, model_name, temperature)
