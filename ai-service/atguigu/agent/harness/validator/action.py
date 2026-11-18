from typing import Any

from atguigu.agent.harness.rules.action import ACTION_CATALOG, ActionCode
from atguigu.agent.harness.validator.validator import ValidateAgentOutError
from atguigu.agent.llm.output import PageAction
from atguigu.app.models.models import AgentToolCall
from atguigu.common.utils import normalized_resource_id


def validate_page_action(successful_bs_tool_calls: list[AgentToolCall],
                         page_action: PageAction | None = None) -> dict[str, Any] | None:
    """
    检验行动页面(resource_id是否真的是合法的)
    :param successful_bs_tool_calls:
    :param page_action:
    :return:
    """
    # 1. 查询，没有不用校验
    if page_action is None:
        return None

    # 2. 用户写操作
    action_code = page_action.action_code

    # 2.1 校验页面行动码
    if action_code is None:
        raise ValidateAgentOutError("页面行动必须要有行动码")  # 纠错重试[llm自己犯错了]

    action_definition = ACTION_CATALOG.get_action_definition(action_code)

    # 2.2 校验行动对象
    if action_definition is None:
        raise ValidateAgentOutError(f"生成的行动码{action_code}，不在白明单允许范围之内")  # 纠错重试[llm自己犯错了]

    # 3. 校验 resource_id
    # 如果行动码是BROWSE_ORDERS，可以不带resource_id,直接构建前端按钮需要的信息
    resource_type = action_definition.resource_type
    if resource_type is None:
        return action_definition.build_page()

    # 如果不是BROWSE_ORDERS，必须带resource_id
    resource_id = action_definition.resource_id
    if resource_id is None:
        raise ValidateAgentOutError("{action_code} 必须提供订单编号")

    normalize_resource_id = normalized_resource_id(resource_id)
    # 4.校验resource_id 的值是不是调用get_order,因为要知道某个订单数据必须要调用get_order()
    # 4.1 校验get_order（）工具且调用成功
    order_data = _validate_get_order(normalize_resource_id, successful_bs_tool_calls)

    # 4.2 校验CANCEL_ORDER/EDIT_ADDRESS 对应的订单状态是否是终态
    _validate_order_status(order_data["status"], action_code, normalize_resource_id)
    # 5. 返回前端按钮需要的信息
    return action_definition.build_page(resource_id=normalize_resource_id)


def _validate_get_order(normalized_order_id: str, successful_bs_tool_calls: list[AgentToolCall]) -> dict[str, Any]:
    """
    校验调用过resource对应的get_order工具
    :param normalized_order_id:
    :param successful_bs_tool_calls:
    :return:
    """
    for stc in successful_bs_tool_calls:
        if stc.tool_name == "get_order" and stc.arguments["resource_id"] == normalized_order_id and stc.success == True:
            return stc.result["data"]

    raise ValidateAgentOutError(
        f"页面动作引用的订单未经get_order工具确认:{normalized_order_id}"
    )


def _validate_order_status(order_status: str, action_code: str, normalize_resource_id: str):
    """
    职责：校验CANCEL_ORDER/EDIT_ADDRESS 对应的订单状态是否是终态
    :param order_status:
    :param action_code:
    :param normalized_order_id:
    :return:
    """
    if action_code in (ActionCode.CANCEL_ORDER, ActionCode.EDIT_ADDRESS) and order_status in (
            "completed", "cancelled", "refunded"):
        raise ValidateAgentOutError(
            f"订单 {normalize_resource_id} 当前状态为 {order_status}，不支持生成 {action_code} 页面跳转动作"
        )
