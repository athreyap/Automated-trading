from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    initial_capital: float = float(os.getenv("INITIAL_CAPITAL", "1000"))
    trading_allocation: float = float(os.getenv("TRADING_ALLOCATION", "900"))
    protected_reserve: float = float(os.getenv("PROTECTED_RESERVE", "100"))
    trading_mode: str = os.getenv("TRADING_MODE", "paper").lower()
    live_trading_enabled: bool = os.getenv("LIVE_TRADING_ENABLED", "false").lower() == "true"
    groww_enabled: bool = os.getenv("GROWW_ENABLED", "false").lower() == "true"
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def validate(self):
        if self.initial_capital <= 0:
            raise ValueError("Initial capital must be positive.")
        if self.trading_allocation < 0 or self.protected_reserve < 0:
            raise ValueError("Allocation and reserve cannot be negative.")
        if self.trading_allocation + self.protected_reserve > self.initial_capital:
            raise ValueError("Allocation plus reserve cannot exceed initial capital.")
        if self.trading_mode != "paper" or self.live_trading_enabled:
            raise ValueError("V1 supports paper mode only; live trading is disabled.")
        if self.groww_enabled:
            raise ValueError("Groww integration is a disabled placeholder in V1.")

settings = Settings()
