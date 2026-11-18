from fastapi import APIRouter, Depends, HTTPException, status

from atguigu.app.dependencies import AdminServiceDep, AdminRoleDep, StaffRoleDep
from atguigu.app.schemas import ReplyMessageRequest

router = APIRouter(prefix="/api/v1", tags=["管理端路由接口"])



@router.get("/handoffs", description="获取工单列表")
async def get_handoffs_endpoint(
        service: AdminServiceDep,
        _: StaffRoleDep
):
    return await service.get_handoffs()



@router.get("/handoffs/{handoff_id}/messages", description="获取工单对应的会话信息")
async def get_handoffs_messages_endpoint(
        service: AdminServiceDep,
        handoff_id: str,
        _: StaffRoleDep
):
    return await service.get_handoffs_messages(handoff_id)


@router.post("/handoffs/{handoff_id}/accept", description="接入会话")
async def accept_handoff_endpoint(
        service: AdminServiceDep,
        handoff_id: str,
        staff_role_dep: StaffRoleDep
):
    await service.accept_handoff(handoff_id,staff_role_dep.user_id)

@router.post("/handoffs/{handoff_id}/messages", description="客服发送消息接口")
async def reply_messages_endpoint(
        service: AdminServiceDep,
        handoff_id: str,
        reply_message:ReplyMessageRequest,
        _: StaffRoleDep
):
    await service.post_messages(handoff_id,reply_message)

@router.post("/handoffs/{handoff_id}/resolve", description="客服结束人工客服")
async def resolve_handoff_endpoint(
        service: AdminServiceDep,
        handoff_id: str,
        _: StaffRoleDep
):
    await service.resolve_handoff(handoff_id)

@router.get("/admin/metrics", description="管理端获取相关指标")
async def get_metrics_endpoint(
        service: AdminServiceDep,
        _: AdminRoleDep
):
    return await service.get_metrics()