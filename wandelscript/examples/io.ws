controller = get_controller("controller")
write(controller, "digital_out[2]", False)
a = read(controller, "digital_out[2]")
write(controller, "digital_out[2]", True)
b = read(controller, "digital_out[2]")
