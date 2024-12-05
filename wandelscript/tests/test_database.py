from pyriphery.robotics import InMemoryDatabase, RobotCell

from wandelscript import run


def test_database_access():
    a = RobotCell(database=InMemoryDatabase())
    code = """
write(database, "foo", "value_bar")
result = read(database, "foo")
"""
    runner = run(code, a)
    assert runner.execution_context.store["result"] == "value_bar"
