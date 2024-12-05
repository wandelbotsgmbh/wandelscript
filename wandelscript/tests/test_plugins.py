from wandelscript.plugins_addons import check_tcp_name


def test_check_tcp_name():
    assert check_tcp_name(3.0) == "3"
