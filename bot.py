from graia.broadcast import Broadcast
from graia.application import GraiaMiraiApplication, Session
from graia.application.message.chain import MessageChain
import asyncio
import time

from graia.application.message.elements.internal import Plain, Image, At, AtAll
from graia.application.group import Group, Member
from graia.application.context import enter_context

import AutoUpdate
import logging
import json

logging.basicConfig(level=logging.INFO)

loop = asyncio.get_event_loop()

with open('./config.json',encoding='utf-8') as config_file:
    config = json.load(config_file)

bcc = Broadcast(loop=loop)
app = GraiaMiraiApplication(
    broadcast=bcc,
    connect_info=Session(
        host='http://localhost:{}'.format(config['Graia']['port']),
        authKey=config['Graia']['authKey'],
        account=config['Graia']['qq'],
        websocket=True
    )
)

Bot = AutoUpdate.PCRBot()
Bot.initialize()

Global_group = config['Graia']['group']


@bcc.receiver("GroupMessage")
async def group_message_handler(app: GraiaMiraiApplication, message: MessageChain, group: Group, member: Member):
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
    global Global_group
    while True:
        await asyncio.sleep(3)
        result = Bot.need_at()
        if result is not None:
            await app.sendGroupMessage(Global_group,
                                       MessageChain.join([Plain(result[1])], [At(target=int(m[0])) for m in result[0]]))


loop.create_task(reminder())

app.launch_blocking()
