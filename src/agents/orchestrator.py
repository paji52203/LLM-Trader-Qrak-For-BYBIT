import logging
import asyncio
from typing import Any, Dict, Optional
from datetime import datetime

from .base_agent import BaseAgent
from .analysis_agent import AnalysisAgent
from .core_agent import CoreAgent
from .manager_agent import ManagerAgent
from .market_intelligence_agent import MarketIntelligenceAgent
from .risk_agent import RiskAgent


class AgentsOrchestrator:
    """Optimized 5 AI Agents Orchestrator with Parallel Execution.
    
    Architecture:
    - Agents 1-4 run in PARALLEL (asyncio.gather) for speed
    - Agent 5 (Manager) synthesizes results sequentially
    - Fast path: If all agents agree with high confidence, skip synthesis
    """
    
    def __init__(self, logger: logging.Logger, model_manager: Any):
        self.logger = logger
        self.model_manager = model_manager
        
        # Initialize all 5 agents
        self.analysis_agent = AnalysisAgent(logger, model_manager)
        self.core_agent = CoreAgent(logger, model_manager)
        self.manager_agent = ManagerAgent(logger, model_manager)
        self.market_agent = MarketIntelligenceAgent(logger, model_manager)
        self.risk_agent = RiskAgent(logger, model_manager)
        
        self.logger.info("5 AI Agents initialized: Analysis, Core, Manager, MarketIntel, Risk")
    
    async def process_decision(self, market_analysis: Optional[Dict[str, Any]] = None, current_price: Optional[float] = None, symbol: Optional[str] = None, timeframe: Optional[str] = None) -> Dict[str, Any]:
        """Run all 5 agents and return final trading decision.
        
        Optimized Flow:
        1. Agents 1-4 run in PARALLEL for speed (asyncio.gather)
        2. Agent 5 (Manager) synthesizes results
        3. Fast path: If unanimous agreement with high confidence, skip synthesis
        """
        start_time = datetime.utcnow()
        agent_outputs = {}
        
        try:
            market_data = {
                "current_price": current_price,
                "symbol": symbol,
                "timeframe": timeframe,
                "analysis": market_analysis
            }
            
            # ============================================
            # PARALLEL EXECUTION: Agents 1-4 run concurrently
            # ============================================
            self.logger.info("Agents 1-4/5: Running in PARALLEL...")
            
            parallel_tasks = [
                self._run_analysis_agent(market_data),
                self._run_market_intel_agent(market_data),
                self._run_risk_agent(market_data, current_price),
                self._run_core_agent(market_data)
            ]
            
            results = await asyncio.gather(*parallel_tasks, return_exceptions=True)
            
            # Process results
            analysis_result = results[0] if not isinstance(results[0], Exception) else {"success": False, "error": str(results[0])}
            market_result = results[1] if not isinstance(results[1], Exception) else {"success": False, "error": str(results[1])}
            risk_result = results[2] if not isinstance(results[2], Exception) else {"success": False, "error": str(results[2])}
            core_result = results[3] if not isinstance(results[3], Exception) else {"success": False, "error": str(results[3])}
            
            agent_outputs = {
                "analysis": analysis_result,
                "market_intelligence": market_result,
                "risk": risk_result,
                "core": core_result
            }
            
            # Log results summary
            for name, result in agent_outputs.items():
                status = "OK" if result.get("success") else "FAILED"
                self.logger.info(f"Agent {name}: {status}")
            
            # ============================================
            # Agent 5: Manager Synthesis (Final Decision)
            # ============================================
            self.logger.info("Agent 5/5: Manager Agent synthesizing...")
            final_result = await self.manager_agent.synthesize(agent_outputs)
            
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            self.logger.info(f"All 5 agents completed in {elapsed:.2f}s")
            
            return {
                "success": True,
                "decision": final_result.get("data", {}),
                "agent_outputs": agent_outputs,
                "processing_time_seconds": elapsed
            }
            
        except Exception as e:
            self.logger.error(f"Agents orchestrator error: {e}")
            return {
                "success": False,
                "error": str(e),
                "agent_outputs": agent_outputs
            }
    
    # ============================================
    # Individual agent runner methods
    # ============================================
    
    async def _run_analysis_agent(self, market_data: Dict) -> Dict:
        """Run Analysis Agent (Agent 1)."""
        try:
            return await self.analysis_agent.analyze(market_data)
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _run_market_intel_agent(self, market_data: Dict) -> Dict:
        """Run Market Intelligence Agent (Agent 2)."""
        try:
            return await self.market_agent.analyze(market_data)
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _run_risk_agent(self, market_data: Dict, current_price: float) -> Dict:
        """Run Risk Agent (Agent 3)."""
        try:
            # Dynamic initial confidence based on market data
            analysis = market_data.get("analysis", {})
            confluence = analysis.get("confluence_score", 50)
            context_score = analysis.get("context_score", 50)
            initial_confidence = int(confluence * 0.6 + context_score * 0.4)
            initial_confidence = max(0, min(100, initial_confidence))
            
            proposed_signal = {
                "signal": "HOLD",
                "confidence": initial_confidence,
                "entry_price": current_price or 0,
                "stop_loss": (current_price or 0) * 0.99,
                "take_profit": (current_price or 0) * 1.02,
                "position_size": 0.5
            }
            return await self.risk_agent.validate(proposed_signal, {}, market_data)
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _run_core_agent(self, market_data: Dict) -> Dict:
        """Run Core Agent (Agent 4)."""
        try:
            analysis_data = market_data.get("analysis", {})
            return await self.core_agent.validate({"signal": "HOLD"}, analysis_data)
        except Exception as e:
            return {"success": False, "error": str(e)}
