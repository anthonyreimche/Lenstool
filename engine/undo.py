"""Undo/redo manager using snapshot-based command buffer.

Each entry is a deep copy of the entire LensSystem state.  This is
robust against every possible edit path (cell edits, surface
insert/delete, optimization, element reorder, system settings, etc.)
and the state is small enough (~KB) that even hundreds of snapshots
are negligible in memory.
"""

import copy
from typing import Optional
from .surface import LensSystem


class UndoManager:
    """Manages an undo/redo stack of LensSystem snapshots.

    Parameters
    ----------
    max_depth : int
        Maximum number of undo states to keep.  Oldest states are
        discarded when the buffer is full.
    """

    def __init__(self, max_depth: int = 100):
        self.max_depth = max(1, max_depth)
        self._undo_stack: list = []   # list of (label, LensSystem snapshot)
        self._redo_stack: list = []   # same format
        self._last_snapshot: Optional[LensSystem] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save_state(self, system: LensSystem, label: str = ""):
        """Snapshot *system* and push it onto the undo stack.

        Takes a fresh deep-copy of *system*.  Use ``save_state_snapshot``
        when the caller has already made the copy (avoids a double-copy).
        """
        self.save_state_snapshot(self._deep_copy(system), label)

    def save_state_snapshot(self, snapshot: LensSystem, label: str = ""):
        """Push an already-copied snapshot onto the undo stack.

        The caller is responsible for ensuring *snapshot* is a fully
        independent copy (e.g. produced by ``_deep_copy``).
        """
        self._undo_stack.append((label, snapshot))

        # Trim oldest entries if over capacity
        while len(self._undo_stack) > self.max_depth:
            self._undo_stack.pop(0)

        # New edit branch — clear redo
        self._redo_stack.clear()

    def undo(self, current_system: LensSystem) -> Optional[LensSystem]:
        """Undo the last change.

        Returns a new LensSystem to replace the current one, or None if
        there is nothing to undo.
        """
        if not self._undo_stack:
            return None

        # Save the *current* state onto the redo stack first
        self._redo_stack.append(("", self._deep_copy(current_system)))

        # Pop the most recent saved state
        _label, snapshot = self._undo_stack.pop()
        return self._deep_copy(snapshot)

    def redo(self, current_system: LensSystem) -> Optional[LensSystem]:
        """Redo the last undone change.

        Returns a new LensSystem, or None if there is nothing to redo.
        """
        if not self._redo_stack:
            return None

        # Push current state onto undo stack
        self._undo_stack.append(("", self._deep_copy(current_system)))

        _label, snapshot = self._redo_stack.pop()
        return self._deep_copy(snapshot)

    def clear(self):
        """Clear all undo/redo history (e.g. when loading a new file)."""
        self._undo_stack.clear()
        self._redo_stack.clear()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    @property
    def undo_depth(self) -> int:
        return len(self._undo_stack)

    @property
    def redo_depth(self) -> int:
        return len(self._redo_stack)

    @property
    def undo_label(self) -> str:
        if self._undo_stack:
            return self._undo_stack[-1][0]
        return ""

    @property
    def redo_label(self) -> str:
        if self._redo_stack:
            return self._redo_stack[-1][0]
        return ""

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _deep_copy(system: LensSystem) -> LensSystem:
        """Create an independent deep copy of the system."""
        return copy.deepcopy(system)
