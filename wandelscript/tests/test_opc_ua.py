import asyncio
import concurrent.futures
import queue
import threading

import pytest
from asyncua import Server, ua
from loguru import logger
from nova.core.robot_cell import RobotCell

from wandelscript import ProgramRunner, ProgramRunState, run


class OPCUATestServer:
    def __init__(self):
        self.endpoint = "opc.tcp://0.0.0.0:4840/wandelbots/"
        self.uri = "http://examples.freeopcua.github.io"

        self._task_queue = queue.Queue()
        self._worker_thread = threading.Thread(target=asyncio.run, args=(self._start_server_loop(),))
        self._worker_thread.start()
        self._running = True

    async def _start_server_loop(self):
        self._server = Server()
        await self._server.init()

        self._server.set_endpoint(self.endpoint)
        self.namespace_id = await self._server.register_namespace(self.uri)

        await self._server.start()

        # its important to not block the server so it can serve request coming from wandelscript
        while self._running:
            try:
                task, future = self._task_queue.get(block=False)
                await task(self._server, self.endpoint, self.namespace_id)
                future.set_result(None)
            except queue.Empty:
                # queue is empty, wait a little
                await asyncio.sleep(1)
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error(f"error happened while executing a task: {e}")
                future.set_exception(e)

    def execute_in_serve_loop(self, callback_function):
        future = concurrent.futures.Future()
        self._task_queue.put((callback_function, future))

        return future.result()

    def shutdown(self):
        future = concurrent.futures.Future()

        async def _shutdown(server: Server, _, __):
            await server.stop()

        self._task_queue.put((_shutdown, future))
        future.result()
        self._running = False
        self._worker_thread.join()


def setup_test_resources(opcua_server, prefix):  # pylint: disable=redefined-outer-name
    ids = {}

    async def configure_nodes(server: Server, url, namespace_id: str):
        # create an object and put some variables with different types
        ids.update(
            {
                "url": url,
                "object_id": f"ns={namespace_id};s={prefix}_object",
                "float_var_id": f"ns={namespace_id};s={prefix}_float_var",
                "int_var_id": f"ns={namespace_id};s={prefix}_int_var",
                "bool_var_id": f"ns={namespace_id};s={prefix}_bool_var",
                "bool_2_var_id": f"ns={namespace_id};s={prefix}_bool_2_var",
                "bool_3_var_id": f"ns={namespace_id};s={prefix}_bool_3_var",
                "is_even_function_id": f"ns={namespace_id};s={prefix}_is_even",
            }
        )

        obj = await server.nodes.objects.add_object(ids["object_id"], f"{prefix}_my_object")

        float_var = await obj.add_variable(ids["float_var_id"], f"{prefix}_float_var", 6.7)
        await float_var.set_writable()

        bool_var = await obj.add_variable(ids["bool_var_id"], f"{prefix}_bool_var", False)
        await bool_var.set_writable()

        bool_2_var = await obj.add_variable(ids["bool_2_var_id"], f"{prefix}_bool_2_var", False)
        await bool_2_var.set_writable()

        bool_3_var = await obj.add_variable(ids["bool_3_var_id"], f"{prefix}_bool_3_var", False)
        await bool_3_var.set_writable()

        int_var = await obj.add_variable(ids["int_var_id"], f"{prefix}_int_var", 0)
        await int_var.set_writable()

        # SETUP THE FUNCTION
        def is_even(_, variant):
            if variant.Value % 2 == 0:
                return [ua.Variant(True, ua.VariantType.Boolean)]

            return [ua.Variant(False, ua.VariantType.Boolean)]

        await obj.add_method(
            ids["is_even_function_id"], f"{prefix}_is_even", is_even, [ua.VariantType.Int64], [ua.VariantType.Boolean]
        )

    opcua_server.execute_in_serve_loop(configure_nodes)
    return ids


# mypy thinks this is a generator because there is yield
@pytest.fixture(scope="module")
def node_id_map() -> dict:  # type: ignore
    test_server = OPCUATestServer()
    id_map = setup_test_resources(test_server, "test_")

    yield id_map

    test_server.shutdown()


@pytest.mark.parametrize("test_case", [("float_var_id", 66.7), ("bool_var_id", True), ("int_var_id", 10)])
def test_read_write_value(node_id_map, test_case):  # pylint: disable=redefined-outer-name
    wandelscript_template = """
url="{server_url}"
opcua_write(url, "{node_id}", {node_value})
result = opcua_read(url, "{node_id}")
"""

    empty_cell = RobotCell()

    id_lookup_key, node_value = test_case
    code = wandelscript_template.format(
        server_url=node_id_map["url"], node_id=node_id_map[id_lookup_key], node_value=node_value
    )

    result = run(code, empty_cell)
    assert result.state == ProgramRunState.COMPLETED
    assert result.execution_context.store["result"] == node_value


@pytest.mark.parametrize(
    "test_case", [("object_id", "is_even_function_id", 2, True), ("object_id", "is_even_function_id", 3, False)]
)
def test_call_function(node_id_map, test_case):  # pylint: disable=redefined-outer-name
    wandelscript_template = """
url="{url}"
result=opcua_call(url, "{object_node_id}", "{function_node_id}", {input})
"""

    object_lookup_key, function_lookup_key, function_input, expected_output = test_case
    code = wandelscript_template.format(
        url=node_id_map["url"],
        object_node_id=node_id_map[object_lookup_key],
        function_node_id=node_id_map[function_lookup_key],
        input=function_input,
    )

    program_runner = run(code, RobotCell())

    assert program_runner.state == ProgramRunState.COMPLETED
    assert program_runner.execution_context.store["result"] == expected_output


@pytest.mark.asyncio
async def test_stop_program_while_watching_opcua_node(node_id_map):  # pylint: disable=redefined-outer-name
    wandelscript = f"""
url="{node_id_map["url"]}"
wait_for_opcua_value(url, "{node_id_map["int_var_id"]}", 100)
"""

    program_runner = ProgramRunner(wandelscript, RobotCell())
    program_runner.start()

    await asyncio.wait_for(wait_until_program_state(program_runner, ProgramRunState.RUNNING), 60)

    program_runner.stop(sync=True)
    assert program_runner.state == ProgramRunState.STOPPED


@pytest.mark.asyncio
async def test_wait_for_opcua_value(node_id_map):  # pylint: disable=redefined-outer-name
    watch_script = f"""
url="{node_id_map["url"]}"
wait_for_opcua_value(url, "{node_id_map["bool_2_var_id"]}", True)
"""

    watch_program = ProgramRunner(watch_script, RobotCell())
    watch_program.start()

    await asyncio.wait_for(wait_until_program_state(watch_program, ProgramRunState.RUNNING), 60)
    assert watch_program.state == ProgramRunState.RUNNING

    update_script = f"""
url="{node_id_map["url"]}"
opcua_write(url, "{node_id_map["bool_2_var_id"]}", True)
"""

    update_program = run(update_script, RobotCell())
    assert update_program.state == ProgramRunState.COMPLETED

    await asyncio.wait_for(wait_until_program_state(watch_program, ProgramRunState.COMPLETED), 10)
    assert watch_program.state == ProgramRunState.COMPLETED


@pytest.mark.asyncio
async def test_wait_for_opcua_value_with_config(node_id_map):  # pylint: disable=redefined-outer-name
    config_definition = """
config = {
    requested_publishing_interval: 1000,
    requested_lifetime_count: 10000,
    max_notifications_per_publish: 1000,
    priority: 0,
    queue_size: 1,
    sampling_interval: 0.0,
    print_received_messages: True,
}
"""

    watch_script = f"""
{config_definition}
url="{node_id_map["url"]}"
wait_for_opcua_value(url, "{node_id_map["bool_3_var_id"]}", True, config)
"""

    watch_program = ProgramRunner(watch_script, RobotCell())
    watch_program.start()

    await asyncio.wait_for(wait_until_program_state(watch_program, ProgramRunState.RUNNING), 60)
    assert watch_program.state == ProgramRunState.RUNNING

    update_script = f"""
url="{node_id_map["url"]}"
opcua_write(url, "{node_id_map["bool_3_var_id"]}", True)
"""

    update_program = run(update_script, RobotCell())
    assert update_program.state == ProgramRunState.COMPLETED

    await asyncio.wait_for(wait_until_program_state(watch_program, ProgramRunState.COMPLETED), 3)
    assert watch_program.state == ProgramRunState.COMPLETED


async def wait_until_program_state(program_runner: ProgramRunner, state: ProgramRunState):
    while program_runner.state not in (state, ProgramRunState.FAILED):
        await asyncio.sleep(1)
