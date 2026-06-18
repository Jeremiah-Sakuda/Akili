"""
Canonical typed objects: Unit, Bijection, Grid.

Only validated, coordinate-grounded facts enter the truth store.
"""

from akili.canonical.models import BBox, Bijection, ConditionalUnit, Grid, Point, Range, Unit

__all__ = ["Unit", "Bijection", "Grid", "Point", "BBox", "Range", "ConditionalUnit"]
