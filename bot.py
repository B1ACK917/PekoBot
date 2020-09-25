from graia.broadcast import Broadcast
from graia.application import GraiaMiraiApplication, Session
from graia.application.message.chain import MessageChain
import asyncio

from graia.application.message.elements.internal import Plain, Image, At, AtAll
from graia.application.group import Group, Member
from graia.application.context import enter_context

import AutoUpdate
import logging

logging.basicConfig(level=logging.INFO)

loop = asyncio.get_event_loop()

bcc = Broadcast(loop=loop)
app = GraiaMiraiApplication(
    broadcast=bcc,
    connect_info=Session(
        host="http://localhost:8080",  # 填入 httpapi 服务运行的地址
        authKey="B1ack917",  # 填入 authKey
        account=3513629853,  # 你的机器人的 qq 号
        websocket=True  # Graia 已经可以根据所配置的消息接收的方式来保证消息接收部分的正常运作.
    )
)

Bot = AutoUpdate.PCRBot()
Bot.initialize()

Global_group = None
Global_app = None


@bcc.receiver("GroupMessage")
async def group_message_handler(app: GraiaMiraiApplication, message: MessageChain, group: Group, member: Member):
    global Global_group, Global_app
    if Global_group is None or Global_app is None:
        Global_group = group
        Global_app = app
    for i in ['状态', '查', '绑定', '预约', '总查刀']:
        if message.asDisplay().startswith(i):
            result, type = Bot.run(message.asDisplay() + ' ' + str(member.name) + ' ' + str(member.id))
            if type == 'STR':
                await app.sendGroupMessage(group,
                                           MessageChain.create([At(target=member.id), Plain('\n' + result)]))
            elif type == 'IMG':
                await app.sendGroupMessage(group,
                                           MessageChain.create([At(target=member.id), Image.fromLocalFile(result)]))


async def reminder():
    global Global_group, Global_app
    while True:
        await asyncio.sleep(1)
        result = Bot.need_at()
        if result is not None:
            await app.sendGroupMessage(Global_group,
                                       MessageChain.join([Plain(result[1])], [At(target=int(m[0])) for m in result[0]]))


loop.create_task(reminder())

app.launch_blocking()
