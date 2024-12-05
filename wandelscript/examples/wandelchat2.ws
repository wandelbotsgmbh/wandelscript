world2desk = ~(-140.7, -707.4, 888.1, 0, 0, 0)

disk_diameter = 100
disk_height = 8

def top_of(pose):
    return (0, 0, disk_height, 0, 0, 0) :: pose
def get_position_right_of(pos):
    return (disk_diameter, 0, 0, 0, 0, 0) :: pos
def get_position_left_of(pos):
    return (-disk_diameter, 0, 0, 0, 0, 0) :: pos
def get_position_front_of(pos):
    return (0, - disk_diameter, 0, 0, 0, 0) :: pos
def get_position_behind_of(pos):
    return (0, disk_diameter, 0, 0, 0, 0) :: pos

table = frame("table")
red_disk = frame("red_disk")
yellow_disk = frame("yellow_disk")
blue_disk = frame("blue_disk")
white_disk = frame("white_disk")
green_disk = frame("green_disk")

def read_all():
    [table | red_disk] = (300, 100, 0, 0, 0, 0)
    [table | yellow_disk] = (100, 100, 0, 0, 0, 0)
    [table | white_disk] = (0, 0, 0, 0, 0, 0)
    [table | blue_disk] = (100, 0, 0, 0, 0, 0)
    [table | green_disk] = (0, 100, 0, 0, 0, 0)
read_all()

robot2workspace = (-140.7, -707.39, -170, 0.000, 3.142, 0.000)

def set_gripper(close):
    sync
    controller = get_controller("controller")
    write(controller, "tool_out[0]", close == False)
    write(controller, "tool_out[1]", close)
    wait(200)

def action(position, close):
    move via p2p() to (position) :: robot2workspace :: (0, 0, -100, 0, 0, 0)
    move via p2p() to (position) :: robot2workspace
    set_gripper(close)
    move via p2p() to (position) :: robot2workspace :: (0, 0, -100, 0, 0, 0)
    sync
    read_all()

a = 0
b = 0

def move_disk(from_, to_):
    a = [table | from_]
    b = [table | to_]
    action([table | from_], True)
    action([table | to_], False)

#def between(a, b):
#    return to_position(interpolate(to_pose(a), to_pose(b), 0.5))

#def empty_place():
#    return get_position_left_of(get_position("white_disk"))


move_disk(red_disk, top_of(blue_disk))
