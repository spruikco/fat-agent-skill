from abc import ABC, abstractmethod
from typing import Any


class AuditModule(ABC):
    MODULE_ID: str = ""
    DISPLAY_NAME: str = ""
    ALWAYS_ENABLED: bool = False

    def __init__(self):
        self.findings: list[dict] = []
        self.score_data: dict[str, Any] = {}

    @abstractmethod
    def analyse(
        self, html: str, url: str = "", headers: dict = None, **kwargs
    ) -> dict: ...

    @abstractmethod
    def score(self, analysis: dict) -> dict: ...

    @classmethod
    def detect(cls, html: str) -> bool:
        return cls.ALWAYS_ENABLED

    def add_finding(
        self,
        priority: str,
        title: str,
        description: str,
        fix: str = "",
        effort: str = "",
    ):
        self.findings.append(
            {
                "priority": priority,
                "title": title,
                "description": description,
                "fix": fix,
                "effort": effort,
                "module": self.MODULE_ID,
            }
        )
