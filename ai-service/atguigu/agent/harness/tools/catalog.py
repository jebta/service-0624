from enum import StrEnum

from langchain_core.tools import BaseTool

from atguigu.agent.harness.tools.definitions import search_products, get_product, list_orders, get_order, get_logistics, \
    list_after_sales


class ToolCategory(StrEnum):
    """
        工具的类别
    """

    BUSINESS = "BUSINESS"  # 业务类型工具
    KNOWLEDGE = "KNOWLEDGE"  # 知识检索类型工具
    GUIDANCE = "GUIDANCE"  # 引导类型工具(load_skill)


class ToolCatalog:
    """
    工具目录：主要管理工具信息
    """

    def __init__(self, tools: list[tuple[BaseTool, ToolCategory]]):
        self.tools = tools
        self.tool_categories = {tool.name: category for tool, category in tools}

    def get_agent_tools(self):
        """
        返回所有的工具对象
        """
        return [tool for tool, _ in self.tools]

    def get_tool_category(self, tool_name: str) -> ToolCategory:
        """
        返回工具名对应的工具类别
        """
        return self.tool_categories[tool_name]


TOOL_CATALOG = ToolCatalog(
    [
        (search_products, ToolCategory.BUSINESS),
        (get_product, ToolCategory.BUSINESS),
        (list_orders, ToolCategory.BUSINESS),
        (get_order, ToolCategory.BUSINESS),
        (get_logistics, ToolCategory.BUSINESS),
        (list_after_sales, ToolCategory.BUSINESS)
    ]
)
