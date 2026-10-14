"""Mutation state manager for Mock API."""

from pydantic import BaseModel


class MutationState(BaseModel):
    """Holds the 5 mutation switches."""

    rename: bool = False
    type_int: bool = False
    nest_target: bool = False
    require_header: bool = False
    wrap_envelope: bool = False

    def reset(self) -> None:
        self.rename = False
        self.type_int = False
        self.nest_target = False
        self.require_header = False
        self.wrap_envelope = False

    def is_v1(self) -> bool:
        return not any([
            self.rename,
            self.type_int,
            self.nest_target,
            self.require_header,
            self.wrap_envelope,
        ])


active_mutations = MutationState()
