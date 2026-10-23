import os

from dataclasses import dataclass

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
