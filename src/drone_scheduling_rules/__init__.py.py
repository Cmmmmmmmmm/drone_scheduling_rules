"""
Drone Scheduling Rules Library

A comprehensive library of constraint rules for drone scheduling optimization,
including airport capabilities, aircraft capabilities, task characteristics,
geographical constraints, and efficiency optimization rules.
"""

from .__version__ import __version__, __author__, __email__, __license__
from .rules import (
    AirportCapabilityRules,
    AircraftCapabilityRules,
    TaskCharacteristicRules,
    GeographicalConstraintRules,
    EfficiencyOptimizationRules
)

__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "__license__",
    "AirportCapabilityRules",
    "AircraftCapabilityRules",
    "TaskCharacteristicRules",
    "GeographicalConstraintRules",
    "EfficiencyOptimizationRules"
]