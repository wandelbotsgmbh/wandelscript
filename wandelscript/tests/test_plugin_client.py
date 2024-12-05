import pytest
from pyriphery.clients import PluginServiceClient
from pyriphery.robotics import InMemoryDatabase, RobotCell, SimulatedRobot

import wandelscript


@pytest.mark.skip(reason="The mocked plugin service is required to run this test.")
def test_plugin_client():
    configuration = PluginServiceClient.Configuration(identifier="plugin_service", host="localhost", port=9001)
    plugin_service = PluginServiceClient(configuration=configuration)

    cell = RobotCell(robot=SimulatedRobot(), database=InMemoryDatabase(), plugin_service=plugin_service)
    code = """
### test /poses endpoint
poses = call(plugin_service, "/poses", 17)
for i in 0..<len(poses):
    move via p2p() to poses[i]

### test /poses/multiply endpoint
pose = call(plugin_service, "/poses/multiply", poses, True)
move via line() to pose

### test /pointcloud endpoint
pcd = call(plugin_service, "/pointcloud", 100)

### test /pointcloud/stitch endpoint
pcd_merged = call(plugin_service, "/pointcloud/stitch", {pcd, pcd, pcd})

### test /pointcloud/decompose endpoint
pcds_decomposed = call(plugin_service, "/pointcloud/decompose", pcd, 5)
for i in 0..<len(pcds_decomposed):
    label = pcds_decomposed[i][1]
"""
    runner = wandelscript.run(code, cell)
    assert len(runner._skill_run.store["poses"].array) == 17  # pylint: disable=protected-access
    assert runner._skill_run.store["label"] == "label1"  # pylint: disable=protected-access
