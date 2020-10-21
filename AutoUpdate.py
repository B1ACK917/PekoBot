import datetime
import os
import requests
import json
import time
import threading
import cv2
import numpy as np
from PIL import ImageFont, ImageDraw, Image
import regex


class PCRBot:
    def __init__(self):
        self.dataServer = 'https://www.bigfun.cn/api/feweb?target=gzlj-clan-day-report%2Fa&date={}&page=1&size=30'
        self.statusServer = 'https://www.bigfun.cn/api/feweb?target=gzlj-clan-day-report-collect%2Fa'
        self.worksCatalogServer = 'https://www.bigfun.cn/api/feweb?target=get-gzlj-team-war-work-list%2Fa&type=2&battle_id={}&boss_position={}&order=1&page={}'
        self.workServer = 'https://www.bigfun.cn/api/feweb?target=get-gzlj-team-war-work-detail%2Fa&work_id={}'
        self.bossServer = 'https://www.bigfun.cn/api/feweb?target=gzlj-clan-boss-report-collect%2Fa'
        self.roleIDServer = 'https://www.bigfun.cn/api/feweb?target=get-gzlj-role-list%2Fa'
        self.header = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.80 Safari/537.36',
        }
        self.statusData = None
        self.lastBossName = ''
        self.playerData = {}
        self.resourceDir = r'./Resource/'
        self.tempDir = r'./Temp/'
        self.dataDir = r'./Data/'
        self.bossName = {}
        self.__get_boss_name()
        with open('./config.json', encoding='utf-8') as config_file:
            config = json.load(config_file)
            self.cookies = config['Bot']['cookies']
            self.battle_id = config['Bot']['battle_id']
        self.bossNum = {}
        for key, value in self.bossName.items():
            self.bossNum.update({value: key})
        self.needAT = None
        for path in [self.resourceDir, self.tempDir, self.dataDir]:
            if not os.path.exists(path):
                os.mkdir(path)
        if os.path.exists(self.dataDir + 'selfMap.npy'):
            self.map = np.load(self.dataDir + 'selfMap.npy', allow_pickle=True).item()
            print('Load IDMap Success.')
            print(self.map)
        else:
            self.map = {}
        if os.path.exists(self.dataDir + 'Subscription.npy'):
            self.subscribeData = np.load(self.dataDir + 'Subscription.npy', allow_pickle=True).item()
            print('Load Subscription Data success.')
            print(self.subscribeData)
        else:
            self.subscribeData = {}
            for name in self.bossName.values():
                self.subscribeData.update({name: []})
        self.rank = {}
        self.works = {}
        self.role_id = {}
        self.__get_role_id()
        self.cycleMap = {'A': 1, 'a': 1, 'B': 2, 'b': 2, 'C': 3, 'c': 3}
        self.work_id_monitor = {}
        for i in range(1, 4):
            self.works.update({i: {'1': [], '2': [], '3': [], '4': [], '5': []}})

    def __get_team_name(self):
        return self.statusData['clan_info']['name']

    def __get_last_ranking(self):
        return self.statusData['clan_info']['last_ranking']

    def __get_last_total_ranking(self):
        return self.statusData['clan_info']['last_total_ranking']

    def __get_latest_boss_name(self):
        return self.statusData['boss_info']['name']

    def __get_latest_boss_total_life(self):
        return self.statusData['boss_info']['total_life']

    def __get_latest_boss_current_life(self):
        return self.statusData['boss_info']['current_life']

    def __get_latest_boss_lap_num(self):
        return self.statusData['boss_info']['lap_num']

    def __get_day_list(self):
        return self.statusData['day_list'].copy()[::-1]

    def __get_specified_day_information(self, date):
        return self.playerData[date].copy()

    def __get_today_player_information(self):
        return self.playerData[self.__get_today_date()].copy()

    def __get_original_information(self, date, player_name):
        if date == 'today':
            infor_dict = self.__get_today_player_information()
        else:
            infor_dict = self.__get_specified_day_information(date)
        for player in infor_dict:
            if player['name'] == player_name:
                return player
        return False

    @staticmethod
    def __get_today_date():
        a = datetime.datetime.now()
        if 0 <= a.hour < 5:
            b = a + datetime.timedelta(-1)
            return b.strftime('%Y-%m-%d')
        return a.strftime('%Y-%m-%d')

    def make_pic(self, text):
        t_list = text.split('\n')
        len_list = [len(t) for t in t_list]
        white_pic = np.zeros(((len(t_list) + 3) * 20, max(len_list) * 20 + 50, 3), np.float32)
        for i in range(white_pic.shape[0]):
            for j in range(white_pic.shape[1]):
                white_pic[i, j] = (255, 255, 255)
        cv2.imwrite(self.tempDir + '1.jpg', white_pic)
        pic = Image.open(self.tempDir + '1.jpg')
        draw = ImageDraw.Draw(pic)
        fnt = ImageFont.truetype(self.resourceDir + 'msyh.ttc', 20)
        for i in range(len(t_list)):
            draw.text((10, (i + 1) * 20), t_list[i], fill='black', font=fnt)
        pic.save(self.tempDir + 'temp.jpg')
        return self.tempDir + 'temp.jpg'

    def __ori_player_information2str(self, information, type):
        sample = '对第{}周目{}造成{}伤害{}{}\n'
        if type == 'today':
            body = ''
            for damage in information['damage_list']:
                body += sample.format(damage['lap_num'], damage['boss_name'], damage['damage'],
                                      '并击破' if damage['kill'] else '', '(剩余刀)' if damage['reimburse'] else '')
            message = '玩家{}的今日出刀记录如下:\n{}\n共造成{}伤害，获得{}分数'.format(information['name'], body, information['damage'],
                                                                  information['score'])
        elif type != 'total':
            body = ''
            for damage in information['damage_list']:
                body += sample.format(damage['lap_num'], damage['boss_name'], damage['damage'],
                                      '并击破' if damage['kill'] else '', '(剩余刀)' if damage['reimburse'] else '')
            message = '玩家{}于{}的出刀记录如下:\n{}\n共造成{}伤害，获得{}分数'.format(information['name'], type, body,
                                                                   information['damage'],
                                                                   information['score'])
        else:
            body = ''
            name, dmg, scr = '', 0, 0
            try:
                for date in information:
                    body += '\n' + date + ':\n'
                    if name == '':
                        name = information[date]['name']
                    for damage in information[date]['damage_list']:
                        body += sample.format(damage['lap_num'], damage['boss_name'], damage['damage'],
                                              '并击破' if damage['kill'] else '', '(剩余刀)' if damage['reimburse'] else '')
                    dmg += information[date]['damage']
                    scr += information[date]['score']
            except TypeError:
                pass
            message = '玩家{}本期会战至今的出刀记录如下:\n{}\n共造成{}伤害，获得{}分数'.format(name, body, dmg, scr)

            return self.make_pic(message)
        return message

    def __get_player(self, date, player_name):
        if date != 'total':
            return self.__ori_player_information2str(self.__get_original_information(date, player_name), date)
        else:
            total_dict = {}
            for day in self.__get_day_list():
                try:
                    total_dict.update({day: self.__get_original_information(day, player_name)})
                except TypeError:
                    pass
                if day == self.__get_today_date():
                    break
            return self.__ori_player_information2str(total_dict, 'total')

    def __get_status(self, date='not total'):
        if date == 'total':
            message = ''
        else:
            message = '公会{}当前排名{},等级{}\n目前进度:第{}周目{}号boss,剩余血量{}/{}'.format(
                self.__get_team_name(), self.__get_last_ranking(), self.__get_last_total_ranking(),
                self.__get_latest_boss_lap_num(), self.bossNum[self.__get_latest_boss_name()],
                self.__get_latest_boss_current_life(), self.__get_latest_boss_total_life()
            )
        return message

    def __register_member(self, member, game_id):
        if member not in self.map:
            self.map.update({member: game_id})
        else:
            self.map[member] = game_id
        np.save(self.dataDir + 'selfMap.npy', self.map, allow_pickle=True)
        return '绑定成功, {} 目前的游戏名称记为 {}'.format(member, game_id)

    def __subscribe(self, player, boss, player_name):
        if boss in self.bossName:
            if (player, player_name) in self.subscribeData[self.bossName[boss]]:
                return '您已经预约过{}号boss了'.format(boss)
            self.subscribeData[self.bossName[boss]].append((player, player_name))
            np.save(self.dataDir + 'Subscription.npy', self.subscribeData, allow_pickle=True)
            return '预约成功'

    def __monitor_boss(self):
        boss = self.__get_latest_boss_name()
        percent = self.__get_latest_boss_current_life() / self.__get_latest_boss_total_life()
        if percent <= 0.5 and boss == self.bossName['5']:
            boss = '狂暴' + boss
        data = self.subscribeData[boss]
        if data:
            self.needAT = (boss, data)
            self.subscribeData[boss] = []
            np.save(self.dataDir + 'Subscription.npy', self.subscribeData, allow_pickle=True)

    def __get_subscription(self, boss):
        boss_name = self.bossName[boss]
        message = '预约了{}的有以下玩家，他们将在轮到该boss时获得通知:\n'.format(boss_name)
        for player in self.subscribeData[boss_name]:
            message += player[1] + '\n'
        return message

    def __get_remain_pt(self, date):
        message = ''
        cnt, remain = 0, 0
        if date == 'today':
            body = '{} 还未完成今日出刀,目前已出{}刀,还剩{}刀\n'
            data = self.playerData[self.__get_today_date()]
            for member in data:
                pt = 0
                for dmg in member['damage_list']:
                    if dmg['kill'] == 0 and dmg['reimburse'] == 0:
                        pt += 1
                    else:
                        pt += 0.5
                if pt != 3:
                    cnt += 1
                    remain += 3 - pt
                    message += body.format(member['name'], pt, 3 - pt)
            message += '\n今日还有{}人未完成出刀,共剩{}刀'.format(cnt, remain)
        return message

    def __get_work(self, member_id, work_id):
        cycle, boss_id = self.work_id_monitor[member_id]
        self.work_id_monitor[member_id] = None
        message = '角色需求:\n{}\n时间轴:\n{}\n\n备注:\n{}'
        role_pattern = '{}星{}{}\n'
        role_list = ''
        this_work = self.works[cycle][boss_id][work_id - 1]
        for role in this_work['role_list']:
            role_list += role_pattern.format(role['stars'], '专武' if role['weapons'] else '', self.role_id[role['id']])
        message = message.format(role_list, this_work['work'], this_work['remark'])
        return self.make_pic(message)

    def __get_works(self, cycle, boss_id, member_id):
        message = ''
        pattern = '{}: {}    预期伤害: {}\n'
        cnt = 1
        for work in self.works[cycle][boss_id]:
            message += pattern.format(cnt, work['Title'], work['expect_injury'])
            cnt += 1
        if member_id not in self.work_id_monitor:
            self.work_id_monitor.update({member_id: (cycle, boss_id)})
        else:
            self.work_id_monitor[member_id] = (cycle, boss_id)
        return self.make_pic(message)

    def __get_today_remain_pt(self):
        return self.__get_remain_pt('today')

    def __get_boss_name(self):
        pre_boss_html = requests.get(url=self.bossServer,
                                     cookies={'session-api': 'trpphlgrc39d3lf1qni787hcgo'})
        boss_html = pre_boss_html.text.encode(pre_boss_html.encoding).decode('utf-8')
        boss_list = json.loads(boss_html)['data']['boss_list']
        for i in range(len(boss_list)):
            self.bossName.update({str(i + 1): boss_list[i]['boss_name']})
        self.bossName.update({'5.5': '狂暴{}'.format(self.bossName['5'])})

    def __get_role_id(self):
        role_id_html = requests.get(url=self.roleIDServer,
                                    cookies={'session-api': 'trpphlgrc39d3lf1qni787hcgo'})
        role_id_html = role_id_html.text.encode(role_id_html.encoding).decode('utf-8')
        role_ids = json.loads(role_id_html)['data']
        for r_i in role_ids:
            self.role_id.update({r_i['id']: r_i['name']})

    def __update_latest_status(self):
        while True:
            try:
                pre_status_html = requests.get(url=self.statusServer,
                                               cookies={'session-api': 'trpphlgrc39d3lf1qni787hcgo'})
                status_html = pre_status_html.text.encode(pre_status_html.encoding).decode('utf-8')
                self.statusData = json.loads(status_html)['data']
                self.__monitor_boss()
            except Exception:
                pass
            time.sleep(10)

    def __update_player_info(self):
        while self.statusData is None:
            pass
        while True:
            try:
                for day in self.__get_day_list():
                    if day not in self.playerData:
                        self.playerData.update({day: None})
                    pre_player_html = requests.get(url=self.dataServer.format(day),
                                                   cookies={'session-api': 'trpphlgrc39d3lf1qni787hcgo'})
                    player_html = pre_player_html.text.encode(pre_player_html.encoding).decode('utf-8')
                    self.playerData[day] = json.loads(player_html)['data']
            except Exception:
                pass
            time.sleep(10)

    def __update_works(self):
        while True:
            try:
                for boss_id in range(1, 6):
                    pre_pagination_html = requests.get(url=self.worksCatalogServer.format(self.battle_id, boss_id, 1),
                                                       cookies={'session-api': 'trpphlgrc39d3lf1qni787hcgo'})
                    pagination_html = pre_pagination_html.text.encode(pre_pagination_html.encoding).decode('utf-8')
                    total_page = json.loads(pagination_html)['pagination']['total_page']
                    for page in range(1, total_page + 1):
                        pre_works_catalog = requests.get(
                            url=self.worksCatalogServer.format(self.battle_id, boss_id, page),
                            cookies={'session-api': 'trpphlgrc39d3lf1qni787hcgo'})
                        catalog = pre_works_catalog.text.encode(pre_works_catalog.encoding).decode('utf-8')
                        pre_works = json.loads(catalog)['data']
                        for pre_work in pre_works:
                            work_html = requests.get(url=self.workServer.format(pre_work['id']),
                                                     cookies={'session-api': 'trpphlgrc39d3lf1qni787hcgo'})
                            work_html = work_html.text.encode(work_html.encoding).decode('utf-8')
                            _work = json.loads(work_html)['data']
                            new_work = {}
                            new_work.update({'Title': _work['title']})
                            new_work.update({'role_list': eval(_work['role_list'])})
                            new_work.update({'expect_injury': _work['expect_injury']})
                            new_work.update({'remark': _work['remark']})
                            new_work.update({'work': _work['work']})
                            if new_work not in self.works[_work['boss_cycle']][str(boss_id)]:
                                self.works[_work['boss_cycle']][str(boss_id)].append(new_work)
            except Exception:
                print(Exception)
            time.sleep(120)

    def initialize(self):
        threading.Thread(target=self.__update_latest_status).start()
        threading.Thread(target=self.__update_player_info).start()
        threading.Thread(target=self.__update_works).start()
        while self.statusData is None:
            pass
        while len(self.playerData) != len(self.__get_day_list()):
            pass

    def test(self):
        self.__update_works()

    def need_at(self):
        if self.needAT:
            boss, at_list = self.needAT
            self.needAT = None
            return at_list, '{}号boss到了,该出刀了\n'.format(self.bossNum[boss])
        return None

    def run(self, command):
        command = command.split(' ')
        if command[0] == '查刀':
            if command[1] in self.map:
                return self.__get_player('today', self.map[command[1]]), 'STR'
            return self.__get_player('today', command[1]), 'STR'
        elif command[0] == '总查刀':
            if command[1] in self.map:
                return self.__get_player('total', self.map[command[1]]), 'IMG'
            return self.__get_player('total', command[1]), 'IMG'
        elif command[0] == '查作业':
            cycle = self.cycleMap[command[1][0]]
            boss = command[1][1]
            return self.__get_works(cycle, boss, command[-1]), 'IMG'
        elif command[0] == '获取':
            return self.__get_work(command[-1], int(command[1])), 'IMG'
        elif command[0] == '状态':
            return self.__get_status(), 'STR'
        elif command[0] == '绑定':
            return self.__register_member(command[2], command[1]), 'STR'
        elif command[0] == '查剩余刀':
            message = self.__get_today_remain_pt()
            if len(message) > 200:
                return self.make_pic(message), 'IMG'
            else:
                return message, 'STR'
        elif command[0][:2] == '预约' and len(command) == 3:
            return self.__subscribe(command[2], command[0][2:], command[1]), 'STR'
        elif command[0][0] == '查' and len(command) == 3:
            return self.__get_subscription(command[0][1:]), 'STR'


if __name__ == '__main__':
    a = PCRBot()
    a.initialize()
    a.test()
