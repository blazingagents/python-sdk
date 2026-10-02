from pydantic import BaseModel

from blazing_agents import FunctionContext, define_function


class Order(BaseModel):
    order_id: str


def execute(order_id: int, context: FunctionContext) -> None:
    return None


define_function(description="d", input_schema=Order, execute=execute)
