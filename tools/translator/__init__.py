"""tools/translator — Translation backend abstraction layer.

Submodules:
- backends/:     Provider implementations (openmodel, openrouter, dedicated)
- router.py:    Backend selection + session stickiness
- policy.py:    Fallback chains + config
- judge.py:     Quality judge (separate model from translator)
"""
from .router import RouterSession, RouterResult, new_session, route
from .policy import FALLBACK_CHAINS, get_chain, list_profiles, ProfileChain
from .judge import judge_chapter, JudgeConfig, JudgeResult

__all__ = [
    "RouterSession", "RouterResult", "new_session", "route",
    "FALLBACK_CHAINS", "get_chain", "list_profiles", "ProfileChain",
    "judge_chapter", "JudgeConfig", "JudgeResult",
]
