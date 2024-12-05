def wandelbots_welding_unit(state):
    write(io, "do/tool/0", state)

def wait_for_button_press(key):
    wait_for_io(io, key, True)
    a = time()
    wait_for_io(io, key, False)
    return time() - a

def assert_var(var):
    pass

def schunk_gripper(action):
    sync
    write(io, "tool_out[0]", action)
    write(io, "tool_out[1]", False == action)
    wait_for_io(io, "tool_in[1]", action)
    wait_for_io(io, "tool_in[0]", False == action)

def sync_take_image():
    sync
    wait 1000
    pose = planned_pose()  # real not planned pose
    take_image(robot, pose)  # To clear the pipeline (this image might still have motion blur)
    take_image(robot, pose)  # To clear the pipeline (this image might still have motion blur)
    return take_image(robot, pose)

def sync_take_image_tcp(tcp):
    sync
    wait 1000
    sync
    pose = read(robot, tcp)
    take_image(robot, pose)  # To clear the pipeline (this image might still have motion blur)
    take_image(robot, pose)  # To clear the pipeline (this image might still have motion blur)
    return take_image(robot, pose)

def scan_object(obj2robot, cam2flange):
    move via p2p() to obj2robot :: (0, 0, 250, pi, 0, 0)
    images = []
    poses = []
    distances = [150]
    theta = [pi / 10, 2 * pi / 10]
    phi = [ 0 , pi / 3, 2 * pi / 3, pi, 4 * pi / 3, 5 * pi / 3]
    offsets = [ (60, -60, 0, 0, 0, 0), (-60, 60, 0, 0, 0, 0), (0, 0, 60, 0, 0, 0)]
    rotations = [ (0, 0, 0, 0, 0, 0), (0, 0, 0, 0, 0, -1.2), (0, 0, 0, 0, 0, 1.2)]
    for i = 0..<len(theta):
        for j = 0..<len(phi):
            for k = 0..<len(distances):
                for l = 0 .. <len(offsets):
                    rotation = (0, 0, 0, 0, 0, phi[j])
                    tilt = rotation :: (0, 0, 0, theta[i], 0, 0) :: ~rotation
                    distance = (0, 0, distances[k], 0, 0, 0)
                    do:
                        move via line() to obj2robot :: tilt :: offsets[l] :: distance :: (0, 0, 0, pi, 0, 0) :: ~cam2flange :: rotations[l]
                    sync:
                        append(images, sync_take_image())
                    except:
                        python_print("Skip image.")
    return images

def calibrate_camera(object_pose, calibration_target, cam2flange, filename):
    home = object_pose :: (0, 0, 400, pi, 0, 0)
    move via p2p() to home
    images = scan_object(object_pose, cam2flange)
    move via line() to home
    tmp = calibrate(images, calibration_target)
    flange2camera = tmp[0]
    obj2robot = tmp[1]
    flange2robot = cap_to_pose(images[1])
    cam2obj = obj2robot :: flange2robot :: ~flange2camera
    python_print(flange2camera)
    save(flange2camera, filename)
    return images

def approach(tcp2object, object, tcp2flange, flange2camera, execute):
    image1 = sync_take_image()
    obj2cam = absolute_pose(image1, object)
    flange2robot_old = read(robot, 'pose')
    flange2robot_new = flange2robot_old :: ~flange2camera :: obj2cam :: tcp2object :: ~tcp2flange
    python_print(flange2robot_old)
    python_print(flange2robot_new)
    if execute:
        move via p2p() to flange2robot_old
        move via line() to flange2robot_new :: (0, 0, -30, 0, 0, 0)
        move via line() to flange2robot_new :: (0, 0, -10, 0, 0, 0)
        image2 = sync_take_image()
        obj2cam = absolute_pose(image2, object)
        flange2robot_old = read(robot, 'pose')
        flange2robot_new = flange2robot_old :: ~flange2camera :: obj2cam :: tcp2object :: ~tcp2flange
        python_print(flange2robot_old)
        python_print(flange2robot_new)
        move via p2p() to flange2robot_new :: (0, 0, -10, 0, 0, 0)
        move via line() to flange2robot_new :: (0, 0, -5, 0, 0, 0)
        move via line() to flange2robot_new ::  (0, 0, 0, 0, 0, 0)

def gosper_curve():
    rotation = (0, 0, 0, 0, 0, -pi / 3)
    def gosper_curve_a(start, step, k):
        if k < 0:
            move via line() to start + step
            return start + step
        else:
            step = step / sqrt(7)
            start = gosper_curve_a(start, step, k - 1)
            step = rotation :: step
            start = gosper_curve_b(start, step)
            step = rotation :: rotation :: step
            start = gosper_curve_b(start, step)
            step = ~rotation :: step
            start = gosper_curve_a(start, step, k - 1)
            step = ~rotation :: ~rotation :: step
            start = gosper_curve_a(start, step, k - 1)
            start = gosper_curve_a(start, step, k - 1)
            step = ~rotation :: step
            start = gosper_curve_b(start, step)
            step = rotation :: step
        return start
    def gosper_curve_b(start, step, k):
        if k < 0:
            move via line() to start + step
            return start + step
        else:
            step = step / sqrt(7)
            step = ~rotation :: step
            start = gosper_curve_a(start, step, k - 1)
            step = rotation :: step
            start = gosper_curve_b(start, step)
            start = gosper_curve_b(start, step)
            step = rotation :: rotation :: step
            start = gosper_curve_b(start, step)
            step = rotation :: step
            start = gosper_curve_a(start, step, k - 1)
            step = ~rotation :: ~rotation :: step
            start = gosper_curve_a(start, step, k - 1)
            step = ~rotation :: step
            start = gosper_curve_b(start, step)
        return start
    move via p2p() to (0, 0, 0, pi, 0, 0)
    gosper_curve_a((0, 0, 0), (1, 0, 0), 2)

def koch_flake(start, home):
    rotation = (0, 0, 0, 0, 0, 2 * pi / 3)
    rotation2 = (0, 0, 0, 0, 0, -pi / 3)
    def fractal(start, end, k):
        if k < 0:
            move via line() to end
        else:
            a = 2 * start / 3 + end / 3
            c = start / 3 + 2 * end / 3
            b = a  + (rotation2 :: (c - a))
            fractal(start, a, k - 1)
            fractal(a, b, k - 1)
            fractal(b, c, k - 1)
            fractal(c, end, k - 1)
    move via line() to start
    for i = 0..<3:
        end = (rotation :: (start - home)) + home
        fractal(start, end, 2)
        start = end


def calibrate_tcp(flange2camera, calibration_target, tcp2obj):
    flange2robot = read(robot, 'pose')
    image = sync_take_image()
    obj2cam = absolute_pose(image, calibration_target)
    tcp2flange = ~flange2camera  :: obj2cam :: tcp2obj
    return tcp2flange

def move_along_outer_corners(calibration_target, object2base, tool2flange):
    object_points = board_to_corner_points(calibration_target)
    for i = 0..<4:
        tool2obj = to_pose(object_points[i]) :: (0, 0, 0, 0, 0, 0)
        flange2base = object2base :: tool2obj :: ~tool2flange
        move via line() to (0, 0, 10, 0, 0, 0) :: flange2base
        move via line() to  (0, 0, 0, 0, 0, 0) :: flange2base
        move via line() to  (0, 0, 10, 0, 0, 0) :: flange2base
        sync

def approach_plane(pose, distance):
    move via line() to a :: (0, 0, -distance, 0, 0, 0)
    offset = -distance
    while True:
        sync
        z = read(sensor, 'z')
        offset = offset + z
        if offset > distance:
            break
        move via line() to pose :: (0, 0, offset, 0, 0, 0)
        if (z > -1) * (z < 1):
            break
