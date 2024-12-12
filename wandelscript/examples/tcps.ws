controller = get_controller("controller")
flange = frame("flange")
tool = frame("tool")
other_tool = frame(to_string(3.0))
another_tool = frame(to_string(4))

tcp(flange)
move via p2p() to (0, 0, 0, 0, 0, 0)
move flange to (1, 2, 0)
sync
a = read(controller[0], "flange")

with tcp(tool):
    move tool to (10, 2, 0)
    move to (1, 24, 0)
    move to (1, 2, 0)
sync
b = read(controller[0], "flange")
c = read(controller[0], "tool")
