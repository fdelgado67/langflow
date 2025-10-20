"""Event-based graph recorder using pure observer pattern.

This recorder observes graph mutation events instead of wrapping build_vertex.
"""

# ruff: noqa: T201

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lfx.debug.events import GraphMutationEvent

__all__ = ["EventBasedRecording", "EventRecorder"]

# Display constants
MAX_TIMELINE_EVENTS = 30
MAX_COMPONENT_EVENTS = 20


@dataclass
class EventBasedRecording:
    """Recording built from mutation events (pure observer pattern)."""

    flow_name: str
    events: list[Any] = field(default_factory=list)  # GraphMutationEvent list
    component_executions: list[str] = field(default_factory=list)  # Vertex IDs

    def save(self, file_path: str | Any) -> None:
        """Save recording to file.

        Args:
            file_path: Path to save the recording
        """
        import pickle
        from pathlib import Path

        with Path(file_path).open("wb") as f:
            pickle.dump(self, f)
        print(f"✅ Saved {len(self.events)} events to {file_path}")

    @classmethod
    def load(cls, file_path: str | Any) -> EventBasedRecording:
        """Load a saved recording.

        Args:
            file_path: Path to the saved recording

        Returns:
            EventBasedRecording instance
        """
        import pickle
        from pathlib import Path

        with Path(file_path).open("rb") as f:
            recording = pickle.load(f)  # noqa: S301
        print(f"✅ Loaded {len(recording.events)} events from {file_path}")
        return recording

    def get_events_for_vertex(self, vertex_id: str) -> list[Any]:
        """Get all events related to a specific vertex."""
        return [e for e in self.events if e.vertex_id == vertex_id]

    def get_events_by_type(self, event_type: str) -> list[Any]:
        """Get all events of a specific type."""
        return [e for e in self.events if e.event_type == event_type]

    def get_events_by_component(self, component_name: str) -> list[Any]:
        """Get events for components matching name.

        Args:
            component_name: Component name to search for

        Returns:
            List of events where vertex_id contains component_name
        """
        return [e for e in self.events if e.vertex_id and component_name in e.vertex_id]

    def get_queue_evolution(self) -> list[dict[str, Any]]:
        """Get how queue changed over time."""
        queue_events = self.get_events_by_type("queue_extended") + self.get_events_by_type("queue_dequeued")
        queue_events.sort(key=lambda e: e.step)

        return [
            {
                "step": event.step,
                "event": event.event_type,
                "queue": event.state_after.get("queue", []),
                "changes": event.changes,
            }
            for event in queue_events
            if event.timing == "after"
        ]

    def get_dependency_changes(self) -> list[dict[str, Any]]:
        """Get all dependency modifications."""
        dep_events = self.get_events_by_type("dependency_added")

        return [
            {
                "step": event.step,
                "vertex": event.vertex_id,
                "predecessor": event.changes.get("predecessor"),
                "run_predecessors_changed": event.changes.get("run_predecessors_changed"),
                "run_map_changed": event.changes.get("run_map_changed"),
            }
            for event in dep_events
            if event.timing == "after"
        ]

    def show_summary(self) -> None:
        """Display summary of recording."""
        print(f"\n{'=' * 80}")
        print(f"Event Recording: {self.flow_name}")
        print(f"{'=' * 80}\n")
        print(f"Total events: {len(self.events)}")
        print(f"Components executed: {len(set(self.component_executions))}")

        # Count by type
        by_type = {}
        for event in self.events:
            by_type[event.event_type] = by_type.get(event.event_type, 0) + 1

        print("\nEvent types:")
        for event_type, count in sorted(by_type.items()):
            print(f"  {event_type}: {count}")

    def show_timeline(self) -> None:
        """Display event timeline."""
        print(f"\n{'=' * 80}")
        print(f"Event Timeline: {self.flow_name}")
        print(f"{'=' * 80}\n")
        print(f"Total events: {len(self.events)}\n")

        print("Timeline (after events only):")
        after_events = [e for e in self.events if e.timing == "after"]

        for i, event in enumerate(after_events[:MAX_TIMELINE_EVENTS]):
            vertex = event.vertex_id.split("-")[0] if event.vertex_id else "Graph"
            print(f"[{i:3d}] {event.event_type:20s} {vertex}")

        if len(after_events) > MAX_TIMELINE_EVENTS:
            print(f"\n... and {len(after_events) - MAX_TIMELINE_EVENTS} more events")

    def get_events_at_step(self, step: int) -> list[Any]:
        """Get all events at a specific step (usually 2: before + after).

        Args:
            step: Step number

        Returns:
            List of events at that step
        """
        return [e for e in self.events if e.step == step]

    def show_events_for_component(self, component_name: str) -> None:
        """Show all events for a specific component.

        Args:
            component_name: Component name to filter by
        """
        comp_events = self.get_events_by_component(component_name)

        print(f"\nEvents for {component_name}: {len(comp_events)}\n")

        for event in comp_events[:MAX_COMPONENT_EVENTS]:
            print(f"[{event.step:3d}] {event.timing:6s} {event.event_type}")
            if event.timing == "after" and event.changes:
                print(f"      Changes: {list(event.changes.keys())}")

        if len(comp_events) > MAX_COMPONENT_EVENTS:
            print(f"\n... and {len(comp_events) - MAX_COMPONENT_EVENTS} more")


class EventRecorder:
    """Records graph execution by observing mutation events (pure observer)."""

    def __init__(self, flow_name: str = "Recording"):
        self.flow_name = flow_name
        self.events: list[GraphMutationEvent] = []
        self.component_executions: list[str] = []

    async def on_event(self, event: GraphMutationEvent) -> None:
        """Observer callback - receives all graph mutations.

        Args:
            event: GraphMutationEvent from graph
        """
        self.events.append(event)

        # Track component executions
        if event.vertex_id and event.vertex_id not in self.component_executions:
            self.component_executions.append(event.vertex_id)

    def get_recording(self) -> EventBasedRecording:
        """Build recording from collected events.

        Returns:
            EventBasedRecording with all events
        """
        return EventBasedRecording(
            flow_name=self.flow_name, events=self.events, component_executions=self.component_executions
        )


async def record_graph_with_events(graph: Any, flow_name: str = "Recording") -> EventBasedRecording:
    """Record graph execution using pure observer pattern.

    Args:
        graph: Graph instance to record
        flow_name: Name for the recording

    Returns:
        EventBasedRecording with complete event log

    Example:
        from lfx.graph.graph.base import Graph
        from lfx.debug.event_recorder import record_graph_with_events

        graph = Graph(...)
        recording = await record_graph_with_events(graph, "My Flow")

        # Analyze events
        print(f"Total events: {len(recording.events)}")
        recording.show_summary()
    """
    recorder = EventRecorder(flow_name)
    graph.register_observer(recorder.on_event)

    try:
        # Execute graph
        from lfx.graph.graph.constants import Finish

        async for result in graph.async_start():
            if isinstance(result, Finish):
                break

    finally:
        graph.unregister_observer(recorder.on_event)

    return recorder.get_recording()
