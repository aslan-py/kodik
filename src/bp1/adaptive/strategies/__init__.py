"""
Слой стратегий обхода источников.

Содержит классификацию источников, оркестрацию стратегий с деградацией
и реальные движки обхода:
- ``SourceClassifier`` — классификация источников.
- ``AgenticOrchestrator`` / ``BaseStrategy`` — оркестрация с деградацией.
- ``engines`` — реальные стратегии (Crawl4AI, Stealth, HITL).
- ``HITLManager`` / ``ProfileManager`` — Human-in-the-Loop для CAPTCHA.
"""
