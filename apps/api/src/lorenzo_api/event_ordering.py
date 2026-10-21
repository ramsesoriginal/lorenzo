"""Deterministic order rebuilt only from explicit assertions (ADR 0312). No dates or IO."""

from __future__ import annotations

import heapq
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Literal

Kind = Literal["order", "causes"]


@dataclass(frozen=True)
class Edge:
    source: uuid.UUID
    target: uuid.UUID
    kind: Kind
    # Disclosure metadata does not change assertion identity or ordering semantics.
    is_shared: bool = field(default=False, compare=False)
    being_id: uuid.UUID | None = None
    being_name: str | None = field(default=None, compare=False)


class EventOrder:
    def __init__(self, nodes: set[uuid.UUID], edges: list[Edge]):
        self.edges = sorted(
            edges, key=lambda e: (e.source, e.target, e.kind, str(e.being_id or ""))
        )
        self.outgoing: dict[uuid.UUID, list[Edge]] = {n: [] for n in nodes}
        incoming = dict.fromkeys(nodes, 0)
        pairs = set()
        for edge in self.edges:
            self.outgoing[edge.source].append(edge)
            if (edge.source, edge.target) not in pairs:
                incoming[edge.target] += 1
                pairs.add((edge.source, edge.target))
        ready = [n for n, count in incoming.items() if count == 0]
        heapq.heapify(ready)
        order = []
        while ready:
            node = heapq.heappop(ready)
            order.append(node)
            for target in sorted({e.target for e in self.outgoing[node]}):
                incoming[target] -= 1
                if incoming[target] == 0:
                    heapq.heappush(ready, target)
        if len(order) != len(nodes):
            raise ValueError("Event relationships must be acyclic")
        self.positions = {n: i for i, n in enumerate(order)}

    def path(self, start: uuid.UUID, end: uuid.UUID, *, causes_only: bool) -> list[Edge]:
        parents: dict[uuid.UUID, Edge | None] = {start: None}
        queue = deque([start])
        while queue:
            node = queue.popleft()
            for edge in self.outgoing[node]:
                if causes_only and edge.kind != "causes":
                    continue
                if self.positions[edge.target] > self.positions[end] or edge.target in parents:
                    continue
                parents[edge.target] = edge
                if edge.target == end:
                    result = []
                    cursor = end
                    while (previous := parents[cursor]) is not None:
                        result.append(previous)
                        cursor = previous.source
                    return list(reversed(result))
                queue.append(edge.target)
        return []

    def compare(self, left: uuid.UUID, right: uuid.UUID) -> tuple[str, str, list[Edge]]:
        if left == right:
            return "same", "identity", []
        relation = "before" if self.positions[left] < self.positions[right] else "after"
        start, end = (left, right) if relation == "before" else (right, left)
        causal = self.path(start, end, causes_only=True)
        if causal:
            return relation, "causal", causal
        path = self.path(start, end, causes_only=False)
        return relation, "ruled" if path else "linearized", path
