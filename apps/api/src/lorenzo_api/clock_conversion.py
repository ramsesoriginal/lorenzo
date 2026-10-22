"""Bounded exact affine clock conversion; dates and ordering are never consulted."""

from __future__ import annotations

import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from lorenzo_api.clock_values import Rational, ReadingRange

MAX_CLOCKS = 200
MAX_RELATIONS = 1000
MAX_STEPS = 20000


class RelationDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ratio: Rational
    clock_anchor: Rational | None = None
    reference_anchor: Rational | None = None

    @model_validator(mode="after")
    def valid(self) -> Self:
        if Fraction(self.ratio) == 0:
            raise ValueError("A clock ratio cannot be zero")
        if (self.clock_anchor is None) != (self.reference_anchor is None):
            raise ValueError("Enter both anchor readings, or neither")
        return self

    def inverse(self) -> RelationDefinition:
        return RelationDefinition(
            ratio=str(1 / Fraction(self.ratio)),
            clock_anchor=self.reference_anchor,
            reference_anchor=self.clock_anchor,
        )


def canonical(
    first: uuid.UUID, second: uuid.UUID, value: RelationDefinition
) -> tuple[uuid.UUID, uuid.UUID, RelationDefinition]:
    return (first, second, value) if first < second else (second, first, value.inverse())


class ConversionLimit(Exception):
    """Work or rational growth exceeded the declared conversion bounds."""


def bounded(value: Fraction) -> Fraction:
    if abs(value.numerator) >= 10**38 or value.denominator >= 10**38:
        raise ConversionLimit
    return value


def affine(reading: ReadingRange, scale: Fraction, offset: Fraction) -> ReadingRange:
    first = bounded(Fraction(reading.lo) * scale + offset)
    last = bounded(Fraction(reading.hi) * scale + offset)
    if scale > 0:
        return ReadingRange(
            lo=str(first),
            hi=str(last),
            lo_inclusive=reading.lo_inclusive,
            hi_inclusive=reading.hi_inclusive,
        )
    return ReadingRange(
        lo=str(last),
        hi=str(first),
        lo_inclusive=reading.hi_inclusive,
        hi_inclusive=reading.lo_inclusive,
    )


def overlap(first: ReadingRange, second: ReadingRange) -> bool:
    if Fraction(first.hi) < Fraction(second.lo) or Fraction(second.hi) < Fraction(first.lo):
        return False
    if first.hi == second.lo:
        return first.hi_inclusive and second.lo_inclusive
    if second.hi == first.lo:
        return second.hi_inclusive and first.lo_inclusive
    return True


@dataclass(frozen=True)
class Relation:
    clock: uuid.UUID
    reference: uuid.UUID
    definition: RelationDefinition


@dataclass(frozen=True)
class Step:
    source: uuid.UUID
    target: uuid.UUID
    ratio: str
    offset: str


@dataclass
class Work:
    remaining: int = MAX_STEPS

    def tick(self) -> None:
        self.remaining -= 1
        if self.remaining < 0:
            raise ConversionLimit


@dataclass
class Resolution:
    reading: ReadingRange | None = None
    path: list[Step] = field(default_factory=list)
    conflicts: list[list[Step]] = field(default_factory=list)


def resolve(
    relations: list[Relation],
    source: uuid.UUID,
    target: uuid.UUID,
    reading: ReadingRange,
    *,
    duration: bool,
    work: Work,
) -> Resolution:
    if len(relations) > MAX_RELATIONS:
        raise ConversionLimit
    adjacency: dict[uuid.UUID, list[tuple[uuid.UUID, Fraction, Fraction]]] = defaultdict(list)
    for relation in relations:
        value = relation.definition
        ratio = Fraction(value.ratio)
        if not duration and value.clock_anchor is None:
            continue
        offset = (
            Fraction(0)
            if duration
            else bounded(
                Fraction(value.clock_anchor or "0")
                - ratio * Fraction(value.reference_anchor or "0")
            )
        )
        adjacency[relation.reference].append((relation.clock, ratio, offset))
        adjacency[relation.clock].append(
            (relation.reference, bounded(1 / ratio), bounded(-offset / ratio))
        )
    potentials: dict[uuid.UUID, tuple[Fraction, Fraction, list[Step]]] = {
        source: (Fraction(1), Fraction(0), [])
    }
    queue = deque([source])
    conflicts: list[list[Step]] = []
    while queue:
        current = queue.popleft()
        scale, offset, path = potentials[current]
        for neighbor, rate, shift in adjacency[current]:
            work.tick()
            next_scale, next_offset = bounded(rate * scale), bounded(rate * offset + shift)
            next_path = [*path, Step(current, neighbor, str(rate), str(shift))]
            if neighbor in potentials:
                known_scale, known_offset, known_path = potentials[neighbor]
                if (known_scale, known_offset) != (next_scale, next_offset) and len(conflicts) < 2:
                    conflicts.extend([known_path, next_path])
            else:
                if len(potentials) >= MAX_CLOCKS:
                    raise ConversionLimit
                potentials[neighbor] = (next_scale, next_offset, next_path)
                queue.append(neighbor)
    if target not in potentials:
        return Resolution()
    scale, offset, path = potentials[target]
    return Resolution(affine(reading, scale, offset), path, conflicts)
