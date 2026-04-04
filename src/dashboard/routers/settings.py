"""Router for manual trade overrides and configuration."""
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

class ManualOverrides(BaseModel):
    stop_loss_pct: Optional[float] = 0.0
    take_profit_pct: Optional[float] = 0.0
    min_allocation_pct: Optional[float] = 0.0
    max_allocation_pct: Optional[float] = 0.0
    manual_coin: Optional[str] = ""
    timeframe: Optional[str] = ""
    initial_capital: Optional[float] = 0.0
    check_interval_mins: Optional[int] = 0

class SettingsRouter:
    """Handles manual overrides for trading parameters."""
    def __init__(self, config, logger):
        self.router = APIRouter(prefix="/api/settings", tags=["settings"])
        self.config = config
        self.logger = logger
        self.overrides_path = Path(self.config.DATA_DIR) / "manual_overrides.json"
        
        # Callback to trigger bot reload/force analysis
        self.reload_callback = None

        # Register routes
        self.router.add_api_route("/overrides", self.get_overrides, methods=["GET"])
        self.router.add_api_route("/overrides", self.update_overrides, methods=["POST"])

    def _ensure_data_dir(self):
        """Ensure data directory exists."""
        os.makedirs(os.path.dirname(self.overrides_path), exist_ok=True)

    async def get_overrides(self) -> Dict[str, Any]:
        """Fetch current manual overrides from disk."""
        if not self.overrides_path.exists():
            return {
                "stop_loss_pct": 0,
                "take_profit_pct": 0,
                "min_allocation_pct": 0,
                "max_allocation_pct": 0,
                "manual_coin": "",
                "timeframe": "",
                "initial_capital": 0,
                "check_interval_mins": 0
            }
        try:
            with open(self.overrides_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            self.logger.error("Failed to load overrides: %s", e)
            return {}

    async def update_overrides(self, overrides: Dict[str, Any]) -> Dict[str, Any]:
        """Save manual overrides to disk with merging to prevent nulls."""
        try:
            self._ensure_data_dir()
            
            # 1. Load existing data
            current_data = await self.get_overrides()
            
            # 2. Merge with new data (only update provided fields)
            # Remove keys with None values to avoid overwriting with null
            filtered_new = {k: v for k, v in overrides.items() if v is not None}
            current_data.update(filtered_new)
            
            # 3. Save merged data
            with open(self.overrides_path, "w", encoding="utf-8") as f:
                json.dump(current_data, f, indent=4)
            
            self.logger.info("Manual overrides merged and saved: %s", filtered_new)
            
            # 4. Trigger bot reload if callback is set
            if self.reload_callback:
                self.logger.info("Triggering bot reload via callback...")
                if hasattr(self.reload_callback, '__call__'):
                    import asyncio
                    if asyncio.iscoroutinefunction(self.reload_callback):
                        await self.reload_callback()
                    else:
                        self.reload_callback()

            return {"status": "success", "message": "Overrides applied", "data": current_data}
        except Exception as e:
            self.logger.error("Failed to update overrides: %s", e)
            raise HTTPException(status_code=500, detail=str(e))
