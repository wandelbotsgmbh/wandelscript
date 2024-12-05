import pydantic
from pyjectory import datatypes as dts


# TODO: should be removed but in a separate MR
class Path(pydantic.BaseModel):
    poses: list[dts.RobotState] = []

    @classmethod
    def from_motion_states(cls, motion_states: list[dts.MotionState]):
        return cls(
            poses=[
                dts.RobotState(
                    pose=motion_state.state.pose,
                    joints=motion_state.state.joints if motion_state.state.joints is not None else None,
                )
                for motion_state in motion_states
            ]
        )
