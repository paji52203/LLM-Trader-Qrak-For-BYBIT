import logging
from .config_loader import config
from typing import Any, Dict, Optional
import json


class BaseAgent:
    """Base class for all trading agents."""
    
    def __init__(self, logger: logging.Logger, name: str, model_manager: Any):
        self.logger = logger
        self.name = name
        self.model_manager = model_manager
    
    async def call_model(self, prompt: str, system_prompt: str = "") -> Dict[str, Any]:
        """Call the AI model with the given prompt using config settings."""
        try:
            # Get agent-specific settings from config
            agent_config = config.get_agent_config(self.name)
            model = agent_config.get("model", "deepseek/deepseek-v3.2") if agent_config else "deepseek/deepseek-v3.2"
            temperature = agent_config.get("temperature", 0.1) if agent_config else 0.1
            max_tokens = agent_config.get("max_tokens", 4096) if agent_config else 4096
            
            response = await self.model_manager.query_async(
                prompt=prompt,
                system_prompt=system_prompt,
            )
            return {"success": True, "response": response}
        except Exception as e:
            self.logger.error(f"{self.name} model call failed: {e}")
            return {"success": False, "error": str(e)}
    
    def parse_json_response(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse JSON from model response."""
        try:
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            return json.loads(text)
        except (json.JSONDecodeError, IndexError) as e:
            self.logger.error(f"{self.name} JSON parse error: {e}")
            return None
