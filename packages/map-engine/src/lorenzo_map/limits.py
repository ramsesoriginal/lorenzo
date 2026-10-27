"""The limits of ADR 0337, in one place. They begin strict and are loosened by ADR."""

MAX_PLACEMENT_BYTES = 64 * 1024
MAX_VERTICES = 2_000
MAX_PARTS = 256
MAX_COORDINATE = 10_000_000
MAX_VALUE = 1_000_000_000_000
MAX_DECIMALS = 6
MAX_UNIT_LENGTH = 32
MAX_PLACEMENTS_PER_MAP = 5_000
MAX_MAPS_PER_LIBRARY = 500
MIN_Z = -100
MAX_Z = 100
# Segment-pair tests a simplicity check may spend before the polygon is called too complex.
SIMPLICITY_BUDGET = 4_000_000
MAX_THEME_NAME = 32
# A grid's cells (those whose centre is in the sheet) and what one can be divided into (ADR 0354).
MAX_CELLS = 250_000
MAX_SUB_DIVISIONS = 16
# Operations in one batch of placement writes (ADR 0351).
MAX_BATCH_OPERATIONS = 100
