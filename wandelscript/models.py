import pydantic
from nova.types.state import MotionState, RobotState


# TODO: should be removed but in a separate MR
class Path(pydantic.BaseModel):
    poses: list[RobotState] = []

    @classmethod
    def from_motion_states(cls, motion_states: list[MotionState]):
        return cls(
            poses=[
                RobotState(
                    pose=motion_state.state.pose,
                    joints=motion_state.state.joints if motion_state.state.joints is not None else None,
                )
                for motion_state in motion_states
            ]
        )
