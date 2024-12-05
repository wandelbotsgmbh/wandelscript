from typing import Any

from pyjectory import datatypes as dts
from pyriphery.opcua_v2 import OPCUA, SubscriptionConfig

from wandelscript.metamodel import register_builtin_func

# TODO: currently with every operation we open and close a opc connection
#       we can optimize this greatly but we need some infrastructure code
#       this infra can be support for 'with' keyword in wandelscript or
#       extending the execution context so it can close the connection after the run
#       or maybe other things? but definitely something


@register_builtin_func()
async def opcua_write(url: str, node_id: str, value: Any):
    """Write a value to the opcua node

    Node ids should be based on opcua standard.
    More information about how opcua node id string notation works can be found here:
    https://documentation.unified-automation.com/uasdkhp/1.4.1/html/_l2_ua_node_ids.html

    Args:
        url: the url of the opcua server
        node_id: id of the node to write the value
        value: the value to write
    """
    async with OPCUA(url) as opc:
        await opc.write_node(node_id, value)


@register_builtin_func()
async def opcua_read(url: str, node_id: str) -> Any:
    """Reads the value of a opcua node and returns the result

    Node ids should be based on opcua standard.
    More information about how opcua node id string notation works can be found here:
    https://documentation.unified-automation.com/uasdkhp/1.4.1/html/_l2_ua_node_ids.html

    Args:
        url: the url of the opcua server
        node_id: id of the node to read the value of

    Returns:
        the value of the node

    """
    async with OPCUA(url) as opc:
        return await opc.read_node(node_id)


@register_builtin_func()
async def opcua_call(url: str, object_id: str, function_id: str, *args) -> Any:
    """executes the opcua function and returns the result

    Node ids should be based on opcua standard.
    More information about how opcua node id string notation works can be found here:
    https://documentation.unified-automation.com/uasdkhp/1.4.1/html/_l2_ua_node_ids.html

    Args:
        url: url of the opcua server
        object_id: node id of the object the function belongs to
        function_id : node id of the function
        *args: the arguments to the function

    Returns:
        the value returned by the opcua function
    """
    async with OPCUA(url) as opc:
        return await opc.call_node(object_id, function_id, *args)


@register_builtin_func()
async def wait_for_opcua_value(url: str, node_id: str, value: Any, config: dts.Record | None = None):
    """watches the opcua node with the given key until it matches the given value

    Node ids should be based on opcua standard.
    More information about how opcua node id string notation works can be found here:
    https://documentation.unified-automation.com/uasdkhp/1.4.1/html/_l2_ua_node_ids.html

    Args:
        url: url of the opcua server
        node_id: id of the node to watch the value of
        value: value that the node should have
        config: configuration for the subscription
    """
    config = config or dts.Record()
    subscription_config = SubscriptionConfig(**config.to_dict())

    async with OPCUA(url) as opc:

        def condition(node_value: Any):
            return node_value == value

        await opc.watch_node_until_condition(node_id, condition, config=subscription_config)
