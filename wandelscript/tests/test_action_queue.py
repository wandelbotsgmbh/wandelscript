# pylint: disable=protected-access
import asyncio

import pytest
from pyjectory import datatypes as dts
from pyjectory import serializer
from pyriphery.robotics.database import InMemoryDatabase
from pyriphery.robotics.robotcell import RobotCell
from pyriphery.robotics.simulation import SimulatedController

from wandelscript.action_queue import ActionQueue, Store
from wandelscript.runtime import ExecutionContext


def test_store_data_dict():
    store = Store()
    store["int"] = 4
    store["float"] = 10.0
    store["str"] = "string"
    store["pose"] = dts.Pose.from_tuple((0, 0, 0, 0, 0, 0))
    assert store.data_dict == {
        "int": 4,
        "float": 10.0,
        "str": "string",
        "pose": serializer.Pose(pose=(0, 0, 0, 0, 0, 0)),
    }


@pytest.mark.asyncio
async def test_trigger_actions():
    async def motion_iterator():
        yield dts.MotionState(path_parameter=0, state=dts.RobotState(pose=dts.Pose.from_tuple((0, 0, 0, 0, 0, 0))))
        yield dts.MotionState(path_parameter=1, state=dts.RobotState(pose=dts.Pose.from_tuple((0, 0, 0, 0, 0, 0))))
        yield dts.MotionState(path_parameter=2, state=dts.RobotState(pose=dts.Pose.from_tuple((0, 0, 0, 0, 0, 0))))
        yield dts.MotionState(path_parameter=3, state=dts.RobotState(pose=dts.Pose.from_tuple((0, 0, 0, 0, 0, 0))))
        yield dts.MotionState(path_parameter=4, state=dts.RobotState(pose=dts.Pose.from_tuple((0, 0, 0, 0, 0, 0))))
        yield dts.MotionState(path_parameter=5, state=dts.RobotState(pose=dts.Pose.from_tuple((0, 0, 0, 0, 0, 0))))

    actions = [
        dts.ActionContainer(path_parameter=0, action=dts.WriteAction(device_id="controller", key="some_io", value=0.5)),
        dts.ActionContainer(path_parameter=3, action=dts.WriteAction(device_id="controller", key="some_io", value=3.3)),
        dts.ActionContainer(
            path_parameter=5, action=dts.WriteAction(device_id="controller", key="some_io", value=5.71)
        ),
        dts.ActionContainer(
            path_parameter=5, action=dts.WriteAction(device_id="controller", key="some_other_io", value=11)
        ),
        dts.ActionContainer(
            path_parameter=19, action=dts.WriteAction(device_id="controller", key="some_io", value=190)
        ),
    ]

    cell = RobotCell(controller=SimulatedController(), database=InMemoryDatabase())
    queue = ActionQueue(ExecutionContext(cell, asyncio.Event()))
    motion_states_with_actions_triggered = [
        motion_state async for motion_state in queue.trigger_actions(motion_iterator(), actions)
    ]
    assert len(motion_states_with_actions_triggered) == 6
    assert await cell["controller"].read("some_io") == 5.71
    assert await cell["controller"].read("some_other_io") == 11


@pytest.mark.asyncio
async def test_run():
    # push first, or use WS
    controller = SimulatedController()
    robot = controller[0]
    cell = RobotCell(controller=controller)
    execution_context = ExecutionContext(cell, asyncio.Event())
    queue = ActionQueue(execution_context)
    motions = [dts.lin((400, 0, 0, 0, 0, 0)), dts.cir((500, 0, 0), (0, 0, 0)), dts.p2p((500, 0, 0))]
    for motion in motions:
        queue.push(motion, tool="flange", motion_group_id=robot.identifier)

    await queue._run()
    assert (await robot.get_state("flange")).pose == dts.Pose.from_tuple((500, 0, 0, 0, 0, 0))
    assert queue.last_pose(robot.identifier) == dts.Pose.from_tuple((500, 0, 0, 0, 0, 0))
    assert queue._last_motions[robot.identifier] == motions[-1]
    assert len(queue._record) == 0
