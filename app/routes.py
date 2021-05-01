# -*- coding: utf-8 -*-
from app import app
import openpyxl
from flask import render_template, request, send_from_directory, abort
from app import models, db, xlsx_creator, socketio, exchange_handler, file_handler
from flask_socketio import emit
import json
import os
from random import randint
from datetime import datetime, timedelta
import requests
from threading import Thread
import sched
import time as time0
from sqlalchemy import func

db.session.configure(autoflush=False)


class BirtixData:
    def __init__(self, arg1, arg2, arg3, arg4):
        self.token = arg1
        self.client_id = arg2
        self.r_token = arg3
        self.client_secret = arg4


f = open('app/token_last_update.txt')

token = str(f.readline()).replace(' ', '').replace('\n', '')
client_id = str(f.readline()).replace(' ', '').replace('\n', '')
r_token = str(f.readline()).replace(' ', '').replace('\n', '')
client_secret = str(f.readline()).replace(' ', '').replace('\n', '')
f.close()

bitrix = BirtixData(token, client_id, r_token, client_secret)


def recode(string):
    return string.encode('utf-8').decode('utf-8')


def time_to_string(data):
    return str(data)[:-3]


def str_to_date(date):
    arr = date.split('.')
    result = datetime(year=int(arr[2]), month=int(arr[1]), day=int(arr[0]))

    return result



def date_to_string(date):
    result = ''
    if date.day > 9:
        result += str(date.day)
    else:
        result += ('0' + str(date.day))
    result += '.'
    if date.month > 9:
        result += str(date.month)
    else:
        result += ('0' + str(date.month))
    result += ('.' + str(date.year))

    return result


def time(data):
    return timedelta(hours=int(data.split(':')[0]), minutes=int(data.split(':')[1]))


def refresh_token():
    data = json.loads(requests.get(
        'https://oauth.bitrix.info/oauth/token/?grant_type=refresh_token&client_id={0}&client_secret={1}&refresh_token={2}'.format(
            bitrix.client_id, bitrix.client_secret, bitrix.r_token)).content.decode('utf-8'))
    return data


def check_token_update():
    info = refresh_token()
    if 'access_token' in info:
        file = open('app/token_last_update.txt', 'w')
        file.writelines([info['access_token'] + '\n', client_id + '\n', info['refresh_token'] + '\n', client_secret])
        file.close()
    bitrix.token = info['access_token']


def call(method):
    data = json.loads(requests.get(
        'https://crm.terrakultur.ru/rest/{0}?access_token={1}'.format(method, bitrix.token)).content.decode('utf-8'))
    return data


def table_to_json(query):
    result = []
    for i in query:
        subres = i.__dict__
        if '_sa_instance_state' in subres:
            subres.pop('_sa_instance_state', None)
        if 'Date' in subres:
            if subres['Date'] != None:
                try:
                    subres['Date'] = subres['Date'].strftime("%d.%m.%Y")
                except Exception:
                    nothing = 'foo bar??'

        result.append(subres)
    return json.dumps(result)


if __name__ == '__main__':
    socketio.run(app)


@app.route('/', methods=['GET', 'POST'])
@app.route('/index', methods=['GET', 'POST'])
def index():
    try:
        check_token_update()
    except Exception as er:
        print("Not logged in, ", er)
    return render_template('index.html', last_updated=43308)


@app.route('/excelStat')
def excelStat():
    data = []
    if int(request.args['id']) == 0:
        return send_from_directory(directory=os.path.abspath(os.path.dirname(__file__) + '/files'), filename='cars.xls')

    if int(request.args['id']) == 1:
        team_orders = models.TeamOrders.query
        images = models.Image.query
        if '-' not in request.args['date']:
            result = json.loads(table_to_json(team_orders.filter_by(date=request.args['date']).all()))
            for i in result:
                i['photo_list'] = json.loads(table_to_json(images.filter_by(report_id=int(i['id'])).all()))
        else:
            result = []
            for date in periodHandler(request.args['date']):
                subres = json.loads(
                    table_to_json(team_orders.filter_by(date=date).all()))
                for i in subres:
                    i['photo_list'] = json.loads(table_to_json(images.filter_by(report_id=int(i['id'])).all()))
                    result.append(i)
        data = result

    if int(request.args['id']) == 2:
        if 'date' in request.args:
            if '-' in request.args['date']:
                all_tasks = models.Task.query
                Tasks = []
                for i in periodHandler(request.args['date']):
                    now_t = all_tasks.filter_by(date=i).all()
                    if now_t:
                        for t in now_t:
                            if t.transport_ids or t.replace or t.type_work != 'Сервисные':
                                Tasks.append(t)
            else:
                Tasks = []
                all_tasks = models.Task.query.filter_by(date=request.args['date']).all()
                for i in range(0, len(all_tasks)):
                    if all_tasks[i].transport_ids or all_tasks[i].replace or all_tasks[i].type_work != 'Сервисные':
                        Tasks.append(all_tasks[i])
        else:
            Tasks = models.Task.query.all()

        data = json.loads(table_to_json(Tasks))

    if int(request.args['id']) == 3:
        replace = models.ReplaceHistory.query
        plants = models.Plant.query
        if '-' in request.args['date']:
            result = []
            for i in periodHandler(request.args['date']):
                buffer = replace.filter_by(date=i).filter_by(checked=True).filter_by(type_work='Заменить').all()
                if str(buffer) != '[]':
                    for j in json.loads(table_to_json(buffer)):
                        j['plant_name'] = plants.filter_by(id=int(j['plant_id'])).first().name
                        result.append(j)
            data = result
        else:
            data = []
            buffer = replace.filter_by(date=request.args['date']).filter_by(checked=True).filter_by(
                type_work='Заменить').all()
            if buffer:
                for j in json.loads(table_to_json(buffer)):
                    j['plant_name'] = plants.filter_by(id=int(j['plant_id'])).first().name
                    data.append(j)
            else:
                data = []

    if int(request.args['id']) == 4:
        transport = models.TransportHistory.query
        plants = models.Plant.query
        teams = models.Team.query
        if '-' in request.args['date']:
            result = []
            for i in periodHandler(request.args['date']):
                buffer = transport.filter_by(date=i).all()
                if str(buffer) != '[]':
                    for j in json.loads(table_to_json(buffer)):
                        trans = json.loads(j['transport_info'])
                        j['plant_name'] = plants.filter_by(
                            id=int(trans['id'])).first().name  # {"id": 1, "done": true, "count": 1}
                        j['plant_count'] = trans['count']
                        j['team'] = teams.filter_by(id=int(j['team_id'])).first()

                        result.append(j)
            data = result
        else:
            buffer = transport.filter_by(date=request.args['date']).filter_by(checked=True).all()
            if buffer:
                data = []
                for j in json.loads(table_to_json(buffer)):
                    j['team'] = teams.filter_by(id=int(j['team_id'])).first()
                    data.append(j)
            else:
                data = []

    if int(request.args['id']) == 5:
        replace = models.ReplaceHistory.query
        reports = models.Report.query
        teams = models.Team.query
        if '-' in request.args['date']:
            result = []
            for i in periodHandler(request.args['date']):
                buffer = replace.filter(models.ReplaceHistory.date.contains(i)).filter_by(checked=True).filter(
                    models.ReplaceHistory.type_work != 'Заменить').all()
                if str(buffer) != '[]':
                    for j in json.loads(table_to_json(buffer)):
                        subres = reports.filter_by(client=j['client']).all()
                        if subres:
                            subres = subres[len(subres) - 1].phytowall_comment
                            j['comment'] = subres
                            j['team'] = teams.filter_by(id=int(j['team_id'])).first().name
                        result.append(j)
            data = result
        else:
            result = []
            buffer = replace.filter(models.ReplaceHistory.date.contains(request.args['date'])).filter_by(
                checked=True).filter(models.ReplaceHistory.type_work != 'Заменить').all()
            if buffer:
                for i in json.loads(table_to_json(buffer)):
                    subres = reports.filter_by(client=i['client']).all()
                    if subres:
                        subres = subres[len(subres) - 1].phytowall_comment
                        i['comment'] = subres
                        i['team'] = teams.filter_by(id=int(i['team_id'])).first().name
                    result.append(i)
                data = result
            else:
                data = []

    if int(request.args['id']) == 6:
        teams = models.Team.query.all()
        result = []
        team_hist = models.TeamHist.query
        clients = models.Client.query
        if '-' not in request.args['date']:
            for team in teams:
                th = team_hist.filter_by(team_id=team.id).filter_by(date=request.args['date']).first()
                if th:
                    th = json.loads(table_to_json([th]))[0]
                    client_info = models.TeamClientHistory.query.filter_by(hist_id=int(th['id'])).all()

                    planned = 0
                    performed = 0
                    on_way = timedelta()
                    real_time = timedelta()
                    formula = 0
                    planned_time = timedelta()
                    if str(client_info) != '[]':
                        client_info = json.loads(table_to_json(client_info))
                        for i in range(0, len(client_info)):
                            if clients.filter_by(name=client_info[i]['client_name']).first().quantity:
                                planned += int(clients.filter_by(name=client_info[i]['client_name']).first().quantity)
                                if client_info[i]['time_end']:
                                    performed += int(
                                        clients.filter_by(name=client_info[i]['client_name']).first().quantity)
                                    real_time += (time(client_info[i]['time_end']) - time(client_info[i]['time_start']))
                                planned_time += timedelta(minutes=2) * int(
                                    clients.filter_by(name=client_info[i]['client_name']).first().quantity)
                            if i != 0 and client_info[i - 1]['time_end']:
                                on_way += (time(client_info[i]['time_start']) - time(client_info[i - 1]['time_end']))

                        try:
                            formula = round(
                                float(60 * performed) / float(real_time.seconds * len(json.loads(team.workers))), 2)
                        except Exception:
                            formula = 0
                    if planned != 0:
                        perf_proc = str(100 * round((float(performed) / float(planned)), 3))
                    else:
                        perf_proc = '100.0'

                    result.append({'team_info': json.loads(table_to_json([team]))[0], 'team_stat':
                        {'planned_unit': planned, 'performed_unit': performed,
                         'perform_percent': perf_proc + '%',
                         'on_road': str(on_way)[:-3], 'real_time': time_to_string(real_time),
                         'planned_time': time_to_string(planned_time / len(json.loads(team.workers))),
                         'date': th['date'], 'formula': formula}})
        else:
            period = periodHandler(request.args['date'])
            for date in period:
                for team in teams:
                    th = team_hist.filter_by(team_id=team.id).filter_by(date=date).first()
                    if th:
                        th = json.loads(table_to_json([th]))[0]
                        client_info = models.TeamClientHistory.query.filter_by(hist_id=int(th['id'])).all()

                        planned = 0
                        performed = 0
                        on_way = timedelta()
                        real_time = timedelta()
                        formula = 0
                        planned_time = timedelta()
                        if str(client_info) != '[]':
                            client_info = json.loads(table_to_json(client_info))
                            for i in range(0, len(client_info)):
                                if clients.filter_by(name=client_info[i]['client_name']).first().quantity:
                                    planned += int(
                                        clients.filter_by(name=client_info[i]['client_name']).first().quantity)
                                    if client_info[i]['time_end']:
                                        performed += int(
                                            clients.filter_by(name=client_info[i]['client_name']).first().quantity)
                                        real_time += (time(client_info[i]['time_end']) - time(
                                            client_info[i]['time_start']))
                                    planned_time += timedelta(minutes=2) * int(
                                        clients.filter_by(name=client_info[i]['client_name']).first().quantity)
                                if i != 0 and client_info[i - 1]['time_end']:
                                    on_way += (time(client_info[i]['time_start']) - time(
                                        client_info[i - 1]['time_end']))
                            try:
                                formula = round(
                                    float(60 * performed) / float(real_time.seconds * len(json.loads(team.workers))), 2)
                            except Exception:
                                formula = 0

                        if planned != 0:
                            perf_proc = str(100 * round((float(performed) / float(planned)), 3))
                        else:
                            perf_proc = '100.0'
                        result.append({'team_info': json.loads(table_to_json([team]))[0], 'team_stat':
                            {'planned_unit': planned, 'performed_unit': performed,
                             'perform_percent': perf_proc + '%',
                             'on_road': str(on_way)[:-3], 'real_time': time_to_string(real_time),
                             'planned_time': time_to_string(planned_time / len(json.loads(team.workers))),
                             'date': th['date'], 'formula': formula}})

        data = result

    if int(request.args['id']) == 7:
        users = models.User.query.all()
        result = []
        user_hist = models.UserHist.query
        if '-' not in request.args['date']:
            for user in users:
                uh = user_hist.filter_by(user_id=user.id).filter_by(date=request.args['date']).first()
                if uh:
                    uh = json.loads(table_to_json([uh]))[0]
                    if not uh['performed_units']:
                        uh['performed_units'] = 0
                    if not uh['planned_units']:
                        uh['planned_units'] = 0
                    try:
                        uh['performed_percent'] = str(
                            100 * round((float(uh['performed_units']) / float(uh['planned_units'])), 3)) + '%'
                    except Exception:
                        uh['performed_percent'] = '100.0%'
                    result.append({'user_info': json.loads(table_to_json([user]))[0], 'user_stat': uh})
        else:
            for date in periodHandler(request.args['date']):
                for user in users:
                    uh = user_hist.filter_by(user_id=user.id).filter_by(date=date).first()
                    if uh:
                        uh = json.loads(table_to_json([uh]))[0]
                        if not uh['performed_units']:
                            uh['performed_units'] = 0
                        if not uh['planned_units']:
                            uh['planned_units'] = 0
                        try:
                            uh['performed_percent'] = str(
                                100 * (round(float(uh['performed_units']) / float(uh['planned_units'])), 3)) + '%'
                        except Exception:
                            uh['performed_percent'] = '100.0%'
                        result.append({'user_info': json.loads(table_to_json([user]))[0], 'user_stat': uh})

        data = result

    if int(request.args['id']) == 8:
        claims = models.Claim.query
        teams = models.Team.query
        if '-' in request.args['date']:
            period = periodHandler(request.args['date'])
            result = []
            for i in period:
                subres = claims
                subres = subres.filter_by(date=i)
                if str(subres.all()) != '[]':
                    for j in json.loads(table_to_json(subres.all())):
                        j['team'] = teams.filter_by(id=int(j['team_id'])).first().name
                        result.append(j)
            data = result
        else:
            data = json.loads(table_to_json(claims.filter_by(date=request.args['date']).all()))
            for i in range(len(data)):
                data[i]['team'] = teams.filter_by(id=int(data[i]['team_id'])).first().name

    if int(request.args['id']) == 9:
        return 'nope'

    if int(request.args['id']) == 10:
        data = []
        if 'team' in request.args:
            date = datetime.today()
            delta = timedelta(days=1)
            task_query = models.GantTask.query
            team_id = models.Team.query.filter_by(name=request.args['team']).first().id
            for i in range(0, 7):
                tasks = task_query.filter_by(date=date_to_string(date), planteam_id=team_id).all()
                for task in tasks:
                    subres = {}
                    subres['team'] = request.args['team']
                    subres['date'] = date_to_string(date)
                    subres['weekday'] = date.weekday()
                    subres['client'] = task.planclient
                    subres['time'] = task.time
                    subres['address'] = task.address
                    subres['comment'] = task.comment
                    subres['contact'] = task.contact
                    subres['type_work'] = task.plantype_work
                    subres['ce'] = task.ce
                    subres['warranty'] = task.warranty
                    subres['containers'] = task.containers
                    data.append(subres)
                date -= delta
        else:
            date = datetime.today()
            delta = timedelta(days=1)
            task_query = models.GantTask.query
            team_query = models.Team.query
            for i in range(0, 7):
                tasks = task_query.filter_by(date=date_to_string(date)).all()
                for task in tasks:
                    subres = {}
                    subres['team'] = team_query.filter_by(id=int(task.planteam_id)).first().name
                    subres['date'] = date_to_string(date)
                    subres['weekday'] = date.weekday()
                    subres['client'] = task.planclient
                    subres['time'] = task.time
                    subres['address'] = task.address
                    subres['comment'] = task.comment
                    subres['contact'] = task.contact
                    subres['type_work'] = task.plantype_work
                    subres['ce'] = task.ce
                    subres['warranty'] = task.warranty
                    subres['containers'] = task.containers
                    data.append(subres)
                date -= delta

    if int(request.args['id']) == 11:
        data = []
        if 'team' in request.args:
            date = datetime.today()
            delta = timedelta(days=1)
            task_query = models.EtalonGant.query
            team_id = models.Team.query.filter_by(name=request.args['team']).first().id
            for i in range(0, 7):
                tasks = task_query.filter_by(date=date_to_string(date), planteam_id=team_id).all()
                for task in tasks:
                    subres = {}
                    subres['team'] = request.args['team']
                    subres['date'] = date_to_string(date)
                    subres['weekday'] = date.weekday()
                    subres['client'] = task.planclient
                    subres['time'] = task.time
                    subres['address'] = task.address
                    subres['comment'] = task.comment
                    subres['contact'] = task.contact
                    subres['type_work'] = task.plantype_work
                    subres['ce'] = task.ce
                    subres['warranty'] = task.warranty
                    subres['containers'] = task.containers
                    data.append(subres)
                date -= delta
        else:
            tasks = models.EtalonGant.query.all()
            team_query = models.Team.query
            for task in tasks:
                subres = {}
                subres['team'] = team_query.filter_by(id=int(task.planteam_id)).first().name
                subres['week'] = task.week
                subres['weekday'] = task.day
                subres['client'] = task.planclient
                subres['time'] = task.time
                subres['address'] = task.address
                subres['comment'] = task.comment
                subres['contact'] = task.contact
                subres['type_work'] = task.plantype_work
                subres['ce'] = task.ce
                subres['warranty'] = task.warranty
                subres['containers'] = task.containers
                data.append(subres)

    if int(request.args['id']) == 12:
        data = []
        client = models.Client.query.filter_by(id=int(request.args['client_id'])).first()
        tasks = models.Task.query.filter_by(planclient=client.name).order_by(models.Task.id.desc()).all()
        team_query = models.Team.query
        for task in tasks:
            subres = {}
            subres['client'] = client.name
            if task.date:
                subres['date'] = task.date
            else:
                subres['date'] = 'Нет.'
            subres['type_work'] = task.type_work
            if task.planteam_id:
                subres['planteam'] = team_query.filter_by(id=int(task.planteam_id)).first().name
            else:
                subres['planteam'] = 'Нет.'
            if task.done:
                subres['done'] = 'Да.'
            else:
                subres['done'] = 'Нет.'
            data.append(subres)

    xlsx_creator.createExel(id=request.args['id'], data=data)
    return send_from_directory(directory=os.path.abspath(os.path.dirname(__file__) + '/upload'),
                               filename='last_stat.xlsx')


@app.route('/checkLeader')
def checkLeader():
    data = request.args
    users = models.User.query
    team = models.Team.query.filter_by(id=int(data['team_id'])).first()

    if team.leader_id:
        user = users.filter_by(id=team.leader_id).first()
        if user:
            user.leader_status = False

    team.leader_id = int(data['leader_id'])
    user = users.filter_by(id=int(data['leader_id'])).first()
    user.leader_status = True

    db.session.commit()
    return 'OK'


@socketio.on('connection')
def user_connected():
    print("user connect")


@app.route('/deleteReplace')
def deleteReplace():
    replace = models.ReplaceHistory.query.filter_by(id=int(request.args['replace_id'])).first()

    db.session.delete(replace)
    db.session.commit()

    return 'OK'


@app.route('/deleteTransport')
def deleteTransport():
    transport = models.TransportHistory.query.filter_by(id=int(request.args['transport_id'])).first()

    db.session.delete(transport)
    db.session.commit()

    return 'OK'


@app.route('/addReplace')
def addReplace():
    data = request.args
    if data[
        'replace_id'] == 'new':  # [{"id": 1, "count": 1, "place":"", "done": true, "replacement": [{"id": 2, "count": 1}]}]
        replace = models.ReplaceHistory()
    elif data['replace_id']:
        replace = models.ReplaceHistory.query.filter_by(id=data['replace_id']).first()
    else:
        abort(400)

    replace.date = data['date']
    replace.team_id = int(data['team_id'])
    replace.plant_name = data['plant_name']
    replace.plant_count = int(data['plant_count'])
    replace.balance = data['balance']
    replace.replace_planned = data['replace_planned']
    replace.task_id = int(data['task_id'])
    replace.plant_id = int(data['plant_id'])
    replace.replace_count = int(data['replace_count'])

    if data['replace_id'] == 'new':
        db.session.add(replace)
    db.session.commit()

    return 'OK'


@app.route('/getLeaders')
def getLeaders():
    users = models.User.query.filter_by(leader_status=True).all()

    return table_to_json(users)


@app.route('/getCordHistory')
def getCordHistory():
    data = request.args

    teams = models.TeamHist.query.filter_by(date=data['date']).all()
    result = []
    Team = models.Team.query
    for team in teams:
        te_buf = Team.filter_by(id=team.team_id).first()
        if te_buf.city == data['city']:
            res = json.loads(team.way_list)
            while 'null' in res:
                res.remove('null')
            while None in res:
                res.remove(None)

        result.append({'city': te_buf.city, 'team_id': te_buf.id, 'data': res})

    return json.dumps(result)


@app.route('/getUserCordHistory')
def getUserCordHistory():
    data = request.args

    users = models.UserHist.query.filter_by(date=data['date']).all()
    user_query = []
    for i in users:
        us = models.User.query.filter_by(id=i.user_id).first()
        if us.city == data['city']:
            user_query.append(i)
    teams = models.Team.query
    result = []
    User = models.User.query
    for user in user_query:
        us_buf = User.filter_by(id=user.user_id).first()
        if not user.way_list:
            user.way_list = '[]'
            db.session.commit()
        if not us_buf.team_id:
            continue
        team = teams.filter_by(id=int(us_buf.team_id)).first()
        res = json.loads(user.way_list)
        while 'null' in res:
            res.remove('null')
        while None in res:
            res.remove(None)

        result.append({'city': team.city, 'user_id': us_buf.id, 'data': res, 'team_id': team.id, 'team': team.name})

    return json.dumps(result)


@app.route('/updateCords')
def updateCords():
    cords = request.args['cords']
    user = models.User.query.filter_by(token=request.headers['Authorization']).first()
    user.cords = cords
    date = datetime.today()
    team = models.Team.query.filter_by(id=int(user.team_id)).first()
    if user.id == team.leader_id:
        team_hist = models.TeamHist.query.filter_by(team_id=team.id).filter_by(date=date_to_string(date)).first()
        data = json.loads(team_hist.way_list)
        data.append(json.loads(request.args['cords']))
        team_hist.way_list = json.dumps(data)
        while 'null' in data:
            data.remove('null')

        while None in data:
            data.remove(None)

        socketio.emit('getCords', {'team_id': team.id, 'data': data}, broadcast=True)

    user_hist = models.UserHist.query.filter_by(user_id=user.id).filter_by(date=date_to_string(date)).first()
    try:
        dat = json.loads(user_hist.way_list)
    except Exception:
        dat = []

    dat.append(json.loads(request.args['cords']))
    user_hist.way_list = json.dumps(dat)

    while 'null' in dat:
        dat.remove('null')

    while None in dat:
        dat.remove(None)

    socketio.emit('getUserCords', {'team_id': team.id, 'data': dat}, broadcast=True)

    db.session.commit()
    return 'OK'


@app.route('/getReplace')
def getReplace():
    data = request.args
    replace = models.ReplaceHistory.query
    if '-' in data['date']:
        result = []
        for i in periodHandler(data['date']):
            buffer = replace.filter_by(date=i).filter_by(checked=True).filter_by(type_work='Заменить').all()
            if str(buffer) != '[]':
                for j in json.loads(table_to_json(buffer)):
                    team = models.Team.query.filter_by(id=j['team_id']).first()
                    if team.city == request.args['city']:
                        result.append(j)
        return json.dumps(result)
    else:
        buffer = replace.filter_by(date=data['date']).filter_by(checked=True).filter_by(type_work='Заменить').all()
        result = []
        if buffer:
            for j in json.loads(table_to_json(buffer)):
                team = models.Team.query.filter_by(id=j['team_id']).first()
                if team.city == request.args['city']:
                    result.append(j)
            return json.dumps(result)
        else:
            return '[]'


@app.route('/getPhytoReplace')
def getPhytoReplace():
    data = request.args
    replace = models.ReplaceHistory.query
    reports = models.Report.query
    if 'client' not in data:
        if '-' in data['date']:
            result = []
            for i in periodHandler(data['date']):
                buffer = replace.filter(models.ReplaceHistory.date.contains(i)).filter_by(checked=True).filter(
                    models.ReplaceHistory.type_work != 'Заменить').all()

                if str(buffer) != '[]':
                    for j in json.loads(table_to_json(buffer)):
                        team = models.Team.query.filter_by(id=j['team_id']).first()
                        if team.city == data['city']:
                            subres = reports.filter_by(client=j['client']).all()
                            if subres:
                                subres = subres[len(subres) - 1].phytowall_comment
                                j['comment'] = subres
                            result.append(j)
            return json.dumps(result)
        else:
            result = []
            buffer = replace.filter(models.ReplaceHistory.date.contains(data['date'])).filter_by(checked=True).filter(
                models.ReplaceHistory.type_work != 'Заменить').all()
            if buffer:
                for i in json.loads(table_to_json(buffer)):
                    team = models.Team.query.filter_by(id=i['team_id']).first()
                    if team.city == data['city']:
                        subres = reports.filter_by(client=i['client']).all()
                        if subres:
                            subres = subres[len(subres) - 1].phytowall_comment
                            i['comment'] = subres
                        result.append(i)
                return json.dumps(result)
            else:
                return '[]'
    else:
        result = []
        buffer = replace.filter_by(checked=True).filter(models.ReplaceHistory.type_work != 'Заменить').filter_by(
            client=data['client']).all()

        if buffer:
            for i in json.loads(table_to_json(buffer)):
                team = models.Team.query.filter_by(id=i['team_id']).first()
                if team.city == data['city']:
                    subres = reports.filter_by(client=i['client']).all()
                    if subres:
                        subres = subres[len(subres) - 1].phytowall_comment
                        i['comment'] = subres
                    result.append(i)
            return json.dumps(result)
        else:
            return '[]'


@app.route('/sendMail')
def sendMail():
    report = models.Report.query.filter_by(id=int(request.args['id'])).first()
    report.checked = True

    db.session.commit()
    client = models.Client.query.filter_by(name=request.args['client_name']).first()
    contact = models.Contacts.query.filter_by(client_id=client.id, name=request.args['contact']).first()
    contact_name = request.args['contact']

    if len(request.args['contact'].split(' ')) == 2:
       contact_name = request.args['contact'].split(' ')[0]

    elif len(request.args['contact'].split(' ')) == 3:
       contact_name = request.args['contact'].split(' ')[0] + ' ' + request.args['contact'].split(' ')[1]

    if contact:
        if contact.email:
            exchange_handler.send_message(email_content=render_template('mail.html',
                                                                        client_name=request.args['client_name'],
                                                                        date=request.args['date'],
                                                                        work_list=request.args['work_list'],
                                                                        replace=request.args['replace'],
                                                                        additional=request.args['additional'],
                                                                        photos=request.args['photos'],
                                                                        team=request.args['team'],
                                                                        workers=request.args['workers'],
                                                                        contact=contact_name),
                                          email=contact.email)
    return 'OK'


@app.route('/getTransport')
def getTransport():
    data = request.args
    transport = models.TransportHistory.query
    if '-' in data['date']:
        result = []
        for i in periodHandler(data['date']):
            buffer = transport.filter_by(date=i).all()
            if str(buffer) != '[]':
                for j in json.loads(table_to_json(buffer)):
                    team = models.Team.filter_by(id=j['team_id']).first()
                    if team.city == data['city']:
                        result.append(j)
        return json.dumps(result)
    else:
        buffer = transport.filter_by(date=data['date']).filter_by(checked=True).all()
        result = []
        if buffer:
            for i in json.loads(table_to_json(buffer)):
                team = models.Team.filter_by(id=i['team_id']).first()
                if team.city == data['city']:
                    result.append(i)
            return json.dumps(result)
        else:
            return '[]'


@app.route('/checkReplace')
def checkReplace():
    task = models.Task.query.filter_by(id=int(request.args['task_id'])).first()
    replace = json.loads(task.replace)
    plants = models.ServicePlant.query
    replaced_from = plants.filter_by(id=int(replace['id'])).first()
    places = models.Place.query
    user = models.User.query.filter_by(token=request.headers['Authorization']).first()
    date = date_to_string(datetime.today())

    replaced_to = replace['replacement']

    regular_plants = models.Plant.query
    for rep in replaced_to:
        service = models.Service.query.filter_by(id=replaced_from.service_id).first()
        place = places.filter_by(id=service.place_id).first()
        if place:
            service_plant = models.ServicePlant()
            service_plant.plant_name = regular_plants.filter_by(id=int(rep['id'])).first().name
            service_plant.plant_count = int(rep['count'])
            db.session.add(service_plant)
            hist = models.PlantHistory()
            hist.plant_name = service_plant.plant_name
            hist.plant_container = replaced_from.plant_container
            hist.date = date
            hist.service_id = service.id

            db.session.add(hist)
            db.session.commit()

    if replaced_from.plant_count - int(replace['count']) > 0:
        replaced_from.plant_count -= int(replace['count'])
    else:
        db.session.delete(replaced_from)

    Replace = models.ReplaceHistory.query.filter_by(task_id=int(request.args['task_id'])).first()
    Replace.checked = True

    replace['done'] = bool(request.args['done'])
    replace['count'] = int(request.args['count'])
    task.replace = json.dumps(replace)
    task.planteam_id = user.team_id
    task.date = date
    task.done = True

    db.session.commit()
    return 'OK'


@app.route('/addCityToTeam')
def addCityToTeam():
    team = models.Team.query.filter_by(id=request.args['team_id']).first()
    team.city = request.args['city']

    db.session.commit()
    return 'OK'


@app.route('/getCarInfo')
def getCarInfo():
    date = request.args['date']
    users = models.User.query.filter_by(driver_status=True, city=request.args['city'])
    if 'driver' in request.args:
        users = users.filter_by(name=request.args['driver']).all()
    elif 'car' in request.args:
        sub_us = []
        for user in users.all():
            if request.args['car'] in user.car_info:
                sub_us.append(user)
        users = sub_us
    else:
        users = users.all()

    user_hist = models.UserHist.query
    if '-' in date:
        date = periodHandler(date)
        result = []
        for i in date:
            for user in users:
                uh = user_hist.filter_by(user_id=user.id).first()
                if uh:
                    if uh.date == i:
                        result.append({'date': i, 'car_info': user.car_info, 'cords': user.cords, 'driver': user.name,
                                       'start_car': uh.start_car, 'end_car': uh.end_car, 'way_list': uh.way_list})
    else:
        result = []
        for user in users:
            uh = user_hist.filter_by(user_id=user.id).first()
            if uh:
                if uh.date == date:
                    result.append({'date': date, 'car_info': user.car_info, 'cords': user.cords, 'driver': user.name,
                                   'start_car': uh.start_car, 'end_car': uh.end_car, 'way_list': uh.way_list})
    return json.dumps(result)


@app.route('/getUserStats')
def getUserStats():
    users = models.User.query.filter_by(city=request.args['city']).all()
    result = []
    user_hist = models.UserHist.query
    if '-' not in request.args['date']:
        for user in users:
            uh = user_hist.filter_by(user_id=user.id).filter_by(date=request.args['date']).first()
            if uh:
                uh = json.loads(table_to_json([uh]))[0]
                if not uh['performed_units']:
                    uh['performed_units'] = 0
                if not uh['planned_units']:
                    uh['planned_units'] = 0
                try:
                    uh['performed_percent'] = str(
                        100 * round((float(uh['performed_units']) / float(uh['planned_units'])), 3)) + '%'
                except Exception:
                    uh['performed_percent'] = '100.0%'
                result.append({'user_info': json.loads(table_to_json([user]))[0], 'user_stat': uh})
    else:
        for date in periodHandler(request.args['date']):
            for user in users:
                uh = user_hist.filter_by(user_id=user.id).filter_by(date=date).first()
                if uh:
                    uh = json.loads(table_to_json([uh]))[0]
                    if not uh['performed_units']:
                        uh['performed_units'] = 0
                    if not uh['planned_units']:
                        uh['planned_units'] = 0
                    try:
                        uh['performed_percent'] = str(
                            100 * (round(float(uh['performed_units']) / float(uh['planned_units'])), 3)) + '%'
                    except Exception:
                        uh['performed_percent'] = '100.0%'
                    result.append({'user_info': json.loads(table_to_json([user]))[0], 'user_stat': uh})

    return json.dumps(result)


@app.route('/getTeamStats')
def getTeamStats():
    teams = models.Team.query.filter_by(city=request.args['city']).all()
    result = []
    team_hist = models.TeamHist.query
    clients = models.Client.query
    if '-' not in request.args['date']:
        for team in teams:
            th = team_hist.filter_by(team_id=team.id).filter_by(date=request.args['date']).first()
            if th:
                th = json.loads(table_to_json([th]))[0]
                client_info = models.TeamClientHistory.query.filter_by(hist_id=int(th['id'])).all()

                planned = 0
                performed = 0
                on_way = timedelta()
                real_time = timedelta()
                formula = 0
                planned_time = timedelta()
                if str(client_info) != '[]':
                    client_info = json.loads(table_to_json(client_info))
                    for i in range(0, len(client_info)):
                        if clients.filter_by(name=client_info[i]['client_name']).first().quantity:
                            try:
                                planned += int(clients.filter_by(name=client_info[i]['client_name']).first().quantity)
                                if client_info[i]['time_end']:
                                    performed += int(clients.filter_by(name=client_info[i]['client_name']).first().quantity)
                                planned_time += timedelta(minutes=2) * int(
                                    clients.filter_by(name=client_info[i]['client_name']).first().quantity)
                            except Exception:
                                print('bad time')
                        elif client_info[i]['time_end']:
                            try:
                                if time(client_info[i]['time_end']) > time(client_info[i]['time_start']):
                                    real_time += (time(client_info[i]['time_end']) - time(client_info[i]['time_start']))
                                else:
                                    real_time += (time(client_info[i]['time_start']) - time(client_info[i]['time_end']))
                            except Exception:
                                print('bad time')
                        if i != 0 and client_info[i - 1]['time_end']:
                            try:
                                if time(client_info[i]['time_start']) > time(client_info[i - 1]['time_end']):
                                    on_way += (time(client_info[i]['time_start']) - time(client_info[i - 1]['time_end']))
                                else:
                                    on_way += (time(client_info[i - 1]['time_start']) - time(client_info[i]['time_end']))
                            except Exception:
                                continue

                    try:
                        formula = round(
                            float(60 * performed) / float(real_time.seconds * len(json.loads(team.workers))), 2)
                    except Exception:
                        formula = 0
                if planned != 0:
                    perf_proc = str(100 * round((float(performed) / float(planned)), 3))
                else:
                    perf_proc = '100.0'
                if on_way < timedelta(minutes=0):
                    on_way *= -1
                result.append({'team_info': json.loads(table_to_json([team]))[0], 'team_stat':
                    {'planned_unit': planned, 'performed_unit': performed,
                     'perform_percent': perf_proc + '%',
                     'on_road': str(on_way)[:-3], 'real_time': time_to_string(real_time),
                     'planned_time': time_to_string(planned_time / len(json.loads(team.workers))),
                     'date': th['date'], 'formula': formula}})
    else:
        period = periodHandler(request.args['date'])
        for date in period:
            for team in teams:
                th = team_hist.filter_by(team_id=team.id).filter_by(date=date).first()
                if th:
                    th = json.loads(table_to_json([th]))[0]
                    client_info = models.TeamClientHistory.query.filter_by(hist_id=int(th['id'])).all()

                    planned = 0
                    performed = 0
                    on_way = timedelta()
                    real_time = timedelta()
                    formula = 0
                    planned_time = timedelta()
                    if str(client_info) != '[]':
                        client_info = json.loads(table_to_json(client_info))
                        for i in range(0, len(client_info)):
                            if clients.filter_by(name=client_info[i]['client_name']).first().quantity:
                                planned += int(clients.filter_by(name=client_info[i]['client_name']).first().quantity)
                                if client_info[i]['time_end']:
                                    performed += int(
                                        clients.filter_by(name=client_info[i]['client_name']).first().quantity)
                                    real_time += (time(client_info[i]['time_end']) - time(client_info[i]['time_start']))
                                planned_time += timedelta(minutes=2) * int(
                                    clients.filter_by(name=client_info[i]['client_name']).first().quantity)
                            if i != 0 and client_info[i - 1]['time_end']:
                                on_way += (time(client_info[i]['time_start']) - time(client_info[i - 1]['time_end']))
                        try:
                            formula = round(
                                float(60 * performed) / float(real_time.seconds * len(json.loads(team.workers))), 2)
                        except Exception:
                            formula = 0

                    if planned != 0:
                        perf_proc = str(100 * round((float(performed) / float(planned)), 3))
                    else:
                        perf_proc = '100.0'
                    result.append({'team_info': json.loads(table_to_json([team]))[0], 'team_stat':
                        {'planned_unit': planned, 'performed_unit': performed,
                         'perform_percent': perf_proc + '%',
                         'on_road': str(on_way)[:-3], 'real_time': time_to_string(real_time),
                         'planned_time': time_to_string(planned_time / len(json.loads(team.workers))),
                         'date': th['date'], 'formula': formula}})

    return json.dumps(result)


@app.route('/getCars')
def getCars():
    cars = models.User.query.filter(models.User.car_info != None).all()
    result = []
    for i in cars:
        result.append({'name': i.car_info, 'id': i.id})

    return json.dumps(result)


@app.route('/getPhyto')
def getPhyto():
    phyto = models.Plant.query.filter_by(id=request.args['id']).first()
    return table_to_json(phyto)


@app.route('/getMe')
def getMe():
    user = models.User.query.filter_by(token=request.headers['Authorization']).first()
    if not user:
        abort(403)
    result = json.loads(table_to_json([user]))[0]
    result.pop('token')
    result.pop('password')

    return json.dumps(result)


@app.route('/getClientPhytos')
def getClientPhytos():
    phyto = models.Plant.query.filter_by(client=request.args['id']).filter_by(type='phytowall').all()
    return table_to_json(phyto)


@app.route('/getClientTasks')
def getClientTasks():
    tasks = models.Task.query.filter_by(planclient=request.args['name']).all()
    return table_to_json(tasks)


@app.route('/checkTransport')
def checkTransport():
    task = models.Task.query.filter_by(id=int(request.args['task_id'])).first()
    transport = json.loads(task.transport_ids)

    transport['done'] = bool(request.args['done'])
    task.transport_ids = json.dumps(transport)

    Transport = models.TransportHistory.query.filter_by(task_id=int(request.args['task_id'])).first()
    Transport.checked = True

    db.session.commit()
    return 'OK'


@app.route('/checkTaskList')
def checkTaskList():
    task = models.TaskList.query.filter_by(id=int(request.args['task_id'])).first()
    task.done = json.loads(request.args['done'])
    if task.description_id > 4:
        date = date_to_string(datetime.today())
        user = models.User.query.filter_by(token=request.headers['Authorization']).first()
        team = models.Team.query.filter_by(id=int(user.team_id)).first()
        big_task = models.Task.query.filter_by(id=task.task_id).first()
        replace = models.ReplaceHistory.query.filter_by(task_id=big_task.id).first()
        replace.checked = True
        big_task.done = True
        big_task.date = date
        big_task.planteam_id = team.id

    db.session.commit()
    return 'OK'


@app.route('/editReport')
def editReport():
    data = request.args
    report = models.Report.query.filter_by(id=int(data['id'])).first()
    report.grade_date = data['date']
    report.manager = data['manager']
    report.comment = data['comment']
    report.grade = data['grade']
    report.client = data['client_title']

    db.session.commit()
    return 'OK'


@app.route('/dailyRequest')
def dailyRequest():
    team = models.Team.query.filter_by(id=int(request.args['team_id'])).first()
    city = team.city
    date = datetime.today()
    try:
        client_list = []
        ClientList = models.ClientList.query.filter_by(date=date_to_string(date)).filter_by(team_id=team.id).all()
        for one in ClientList:
            if one.date == date_to_string(date):
                client_list.append(one.client)
        clients = models.Client.query.filter(models.Client.name.in_(client_list)).filter_by(city=city).all()
    except Exception as er:
        print(er)
        return '[]'
    floor_query = models.Floor.query
    row = []
    for client in clients:
        result = {}
        counting = []
        result['task_list'] = []
        result['transport'] = []
        result['replace'] = []
        plants = models.Plant.query
        taskList = models.TaskList.query
        try:
            subresult = json.loads(table_to_json([client]))[0]
            team_hist = models.TeamHist.query.filter_by(date=date_to_string(date)).filter_by(
                team_id=int(request.args['team_id'])).first()
            if team_hist:
                client_hist = models.TeamClientHistory.query.filter_by(hist_id=team_hist.id).filter_by(
                    client_name=client.name).first()
                if client_hist:
                    if client_hist.time_end:
                        subresult['status'] = 1
                    else:
                        subresult['status'] = 0
                else:
                    subresult['status'] = -1
            else:
                subresult['status'] = -1
            result['client'] = subresult
        except Exception as er:
            result['client'] = None
            print(er)
        result['plan_comment'] = None
        try:
            date_to_string(date)
            tasks = json.loads(table_to_json(
                models.Task.query.filter_by(planteam_id=int(request.args['team_id'])).filter_by(
                    planclient=client.name).filter_by(date=date_to_string(date)).all()))
            mobile_tasks = json.loads(table_to_json(
                models.Task.query.filter_by(planteam_id=None).filter_by(planclient=client.name).filter_by(date=None).filter_by(done=None).all()))
            for mobile_task in mobile_tasks:
                tasks.append(mobile_task)
            for task in tasks:
                if task['gant_id']:
                    commenter = models.GantTask.query.filter_by(id=int(task['gant_id'])).first()
                    result['plan_comment'] = commenter.comment
                    if commenter.time:
                        if '-' in commenter.time:
                            result['client']['time_start'] = commenter.time.split('-')[0]
                        else:
                            result['client']['time_start'] = commenter.time
                tl = taskList.filter_by(task_id=int(task['id'])).all()
                jstl = json.loads(table_to_json(tl))

                if task['mobile']:
                    jstl[0]['mobile'] = True
                else:
                    jstl[0]['mobile'] = False
                result['task_list'].append(jstl[0])
                if len(jstl) > 1:
                    jstl[1]['mobile'] = False
                    result['task_list'].append(jstl[1])
                if task['transport_ids']:
                    i = json.loads(task['transport_ids'])
                    result['transport'].append({'item': plants.filter_by(id=int(i['id'])).first().name,
                                                'count': int(i['count']), 'done': i['done'], 'task_id': task['id']})
                if task['replace']:
                    i = json.loads(task['replace'])
                    item_buf = plants.filter_by(id=int(i['id'])).first().name
                    item_replace = []
                    for j in i['replacement']:
                        item_replace.append(
                            {'item': plants.filter_by(id=int(j['id'])).first().name, 'count': j['count']})
                    result['replace'].append(
                        {'item': item_buf, 'count': i['count'], 'place': i['place'], 'replacement': item_replace,
                         'done': i['done'], 'task_id': task['id']})
        except Exception as er:
            print(er)
            result['task_list'] = []
        try:
            floors = floor_query.filter_by(client_id=client.id).all()
            if not client.quantity:
                quantity = 0
            else:
                quantity = client.quantity
            result['plant_service'] = {'floors': [], 'phytowall': 0, 'circle': 0, 'flower': 0, 'can': int(quantity)}
            for floor in floors:
                place_list = []
                for place in floor.place_list:
                    ser_list = []
                    for ser in place.service:
                        ser_list.append({'service_id': ser.id, 'plants': json.loads(table_to_json(ser.plants))})
                        counting.append(ser.plants)
                    place_list.append({'place': place.name, 'service': ser_list})
                result['plant_service']['floors'].append({'num': floor.num, 'place_list': place_list})

            if counting:
                for i in counting:
                    if i:
                        for j in i:
                            if j.plant_type == 'phytowall':
                                result['plant_service']['phytowall'] += j.plant_count
                            elif j.plant_type == 'circle':
                                result['plant_service']['circle'] += 1
                                result['plant_service']['flower'] += j.plant_count
                            elif j.plant_type == 'flower':
                                result['plant_service']['flower'] += j.plant_count

        except Exception as er:
            print(er)
            result['plant_service'] = None
        try:
            reports = models.Report.query.filter_by(client=client.name, team_id=int(request.args['team_id'])).all()
            report_list = models.ReportList.query
            result['reports'] = []
            counter = 0
            for i in reports:
                result['reports'].append(json.loads(table_to_json([i]))[0])
                result['reports'][counter]['report_list'] = (
                    json.loads(table_to_json(report_list.filter_by(report_id=i.id).all())))
                counter += 1

        except Exception:
            result['reports'] = []
        try:
            contacts = models.Contacts.query.filter_by(client_id=client.id).all()
            result['contacts'] = json.loads(table_to_json(contacts))
            for i in range(len(result['contacts'])):
                result['contacts'][i]['address'] = result['client']['address']
        except Exception as er:
            print(er)
            result['contacts'] = []
        row.append(result)

    db.session.commit()
    return json.dumps(row)


@app.route('/getClientInfo')
def getClientInfo():
    try:
        client = models.Client.query.filter_by(id=int(request.args['client_id'])).first()
    except Exception:
        return ''
    floor_query = models.Floor.query
    date = datetime.today()
    row = []
    result = {}
    counting = []
    result['task_list'] = []
    result['transport'] = []
    result['replace'] = []
    plants = models.Plant.query
    taskList = models.TaskList.query
    try:
        subresult = json.loads(table_to_json([client]))[0]
        team_hist = models.TeamHist.query.filter_by(date=date_to_string(date)).filter_by(
            team_id=int(request.args['team_id'])).first()
        if team_hist:
            client_hist = models.TeamClientHistory.query.filter_by(hist_id=team_hist.id).filter_by(
                client_name=client.name).first()
            if client_hist:
                if client_hist.time_end:
                    subresult['status'] = 1
                else:
                    subresult['status'] = 0
            else:
                subresult['status'] = -1
        else:
            subresult['status'] = -1
        result['client'] = subresult
    except Exception:
        result['client'] = None
    result['plan_comment'] = None
    try:
        date_to_string(date)
        tasks = json.loads(table_to_json(
            models.Task.query.filter_by(planteam_id=int(request.args['team_id'])).filter_by(
                planclient=client.name).filter_by(date=date_to_string(date)).all()))
        mobile_tasks = json.loads(table_to_json(
            models.Task.query.filter_by(planteam_id=None).filter_by(planclient=client.name).filter_by(
                date=None).filter_by(done=None).all()))
        for mobile_task in mobile_tasks:
            tasks.append(mobile_task)
        for task in tasks:
            if task['gant_id']:
                commenter = models.GantTask.query.filter_by(id=int(task['gant_id'])).first()
                result['plan_comment'] = commenter.comment
            if task['time']:
                if '-' in task['time']:
                    task['time'] = task['time'].split('-')[0]
                result['client']['time_start'] = task['time']
            tl = taskList.filter_by(task_id=int(task['id'])).all()
            tljs = json.loads(table_to_json(tl))
            if task['mobile']:
                tljs[0]['mobile'] = True
            else:
                tljs[0]['mobile'] = False
            result['task_list'].append(tljs[0])
            if len(tljs) > 1:
                tljs[1]['mobile'] = False
                result['task_list'].append(tljs[1])
            if task['transport_ids']:
                i = json.loads(task['transport_ids'])
                result['transport'].append({'item': plants.filter_by(id=int(i['id'])).first().name,
                                            'count': int(i['count']), 'done': i['done'], 'task_id': task['id']})
            if task['replace']:
                i = json.loads(task['replace'])
                item_buf = plants.filter_by(id=int(i['id'])).first().name
                item_replace = []
                for j in i['replacement']:
                    item_replace.append({'item': plants.filter_by(id=int(j['id'])).first().name, 'count': j['count']})
                result['replace'].append({'item': item_buf, 'count': i['count'], 'place': i['place'],
                                          'replacement': item_replace, 'done': i['done'], 'task_id': task['id']})
    except Exception as er:
        print(er)
        result['task_list'] = []
    try:
        floors = floor_query.filter_by(client_id=client.id).all()
        if not client.quantity:
            quantity = 0
        else:
            quantity = client.quantity
        result['plant_service'] = {'floors': [], 'phytowall': 0, 'circle': 0, 'flower': 0, 'can': int(quantity)}
        for floor in floors:
            place_list = []
            for place in floor.place_list:
                ser_list = []
                for ser in place.service:
                    ser_list.append({'service_id': ser.id, 'plants': json.loads(table_to_json(ser.plants))})
                    counting.append(ser.plants)
                place_list.append({'place': place.name, 'service': ser_list})
            result['plant_service']['floors'].append({'num': floor.num, 'place_list': place_list})

        if counting:
            for i in counting:
                if i:
                    for j in i:
                        if j.plant_type == 'phytowall':
                            result['plant_service']['phytowall'] += j.plant_count
                        elif j.plant_type == 'circle':
                            result['plant_service']['circle'] += 1
                            result['plant_service']['flower'] += j.plant_count
                        elif j.plant_type == 'flower':
                            result['plant_service']['flower'] += j.plant_count
    except Exception:
        result['plant_service'] = None
    try:
        reports = models.Report.query.filter_by(client=client.name).all()
        report_list = models.ReportList.query
        result['reports'] = []
        counter = 0
        for i in reports:
            result['reports'].append(json.loads(table_to_json([i]))[0])
            result['reports'][counter]['report_list'] = (json.loads(
                table_to_json(report_list.filter_by(report_id=i.id, team_id=int(request.args['team_id'])).all())))
            counter += 1

    except Exception:
        result['reports'] = []
    try:
        contacts = models.Contacts.query.filter_by(client_id=client.id).all()
        result['contacts'] = json.loads(table_to_json(contacts))
    except Exception:
        result['contacts'] = []
    row.append(result)

    db.session.commit()
    return json.dumps(row[0])


@app.route('/dayStatus')
def dayStatus():
    if request.headers['Authorization']:
        user = models.User.query.filter_by(token=request.headers['Authorization']).first()
        if not user:
            abort(403)
        date = datetime.today()
        user_hist = models.UserHist.query.filter_by(user_id=user.id).filter_by(date=date_to_string(date)).first()
        if not user_hist:
            return '-1'
        if user_hist.time_end:
            return '1'
        else:
            return '0'
    else:
        abort(400)


@app.route('/getService')
def getService():
    client = models.Client.query.filter_by(id=int(request.args['id'])).first()
    floor_query = models.Floor.query
    floors = floor_query.filter_by(client_id=client.id).all()
    result = {}
    result['plant_service'] = {'floors': []}
    for floor in floors:
        place_list = []
        for place in floor.place_list:
            ser_list = []
            for ser in place.service:
                ser_list.append({'service_id': ser.id, 'plants': json.loads(table_to_json(ser.plants))})
            place_list.append({'place': place.name, 'place_id': place.id, 'service': ser_list})
        result['plant_service']['floors'].append({'num': floor.num, 'floor_id': floor.id, 'place_list': place_list})
    return json.dumps(result)


@app.route('/addFloor')
def addFloor():
    floor = models.Floor()
    floor.num = request.args['floor_name']
    floor.client_id = int(request.args['client_id'])

    db.session.add(floor)
    db.session.commit()

    return 'OK'


@app.route('/getHistory')
def getHistory():
    data = request.args
    user = models.User.query.filter_by(token=request.headers['AUTHORIZATION']).first()
    client_hist = models.TeamHist.query.filter_by(date=data['date'], team_id=user.team_id).all()

    client_arr = []
    for i in client_hist:
        for j in i.client_hist:
            client_arr.append(j.client_name)
    clients_query = models.Client.query
    reports_query = models.Report.query
    clients = []
    for i in client_arr:
        clients.append({'client': json.loads(table_to_json([clients_query.filter_by(name=i).first()]))[0],
                        'reports': json.loads(
                            table_to_json(reports_query.filter_by(client=i, team_id=user.team_id).all()))})

    return json.dumps(clients)


@app.route('/deleteServicePlant')
def deleteServicePlant():
    plant = models.ServicePlant.query.filter_by(id=int(request.args['plant_id'])).first()

    db.session.delete(plant)
    db.session.commit()

    return 'OK'


@app.route('/addServicePlant')
def addServicePlant():
    data = request.args
    place = models.Place.query.filter_by(id=int(data['place_id'])).first()
    service = models.Service.query.filter_by(place_id=int(data['place_id'])).first()
    new = False
    if not service:
        service = models.Service()
        new = True

    if not new:
        plant = models.ServicePlant.query.filter_by(service_id=int(service.id)).filter_by(
            plant_id=int(data['plant_id'])).first()
        if not plant:
            plant = models.ServicePlant()

            plant.plant_name = data['plant_name']
            plant.plant_count = data['plant_count']
            plant.plant_id = int(data['plant_id'])
            plant.plant_guarantee = bool(json.loads(data['plant_guarantee']))
            plant.plant_client = bool(json.loads(data['plant_client']))
            plant.plant_container = data['plant_container']
            plant.plant_type = models.Plant.query.filter_by(id=int(data['plant_id'])).first().type
            if plant.plant_type == 'phytowall':
                client = models.Client.query.filter_by(id=int(data['client_id'])).first()
                client.phyto_flag = True
            elif plant.plant_container and plant.plant_container != 'null':
                plant.plant_type = 'circle'
            service.plants.append(plant)
        else:
            plant.plant_count = int(plant.plant_count) + int(data['plant_count'])
    if new:
        place.service = service

    db.session.commit()

    hist = models.PlantHistory()
    hist.plant_name = data['plant_name']
    hist.plant_container = data['plant_container']
    hist.date = date_to_string(datetime.today())
    hist.service_id = service.id

    db.session.add(hist)
    db.session.commit()

    return 'OK'


@app.route('/editServicePlant')
def editServicePlant():
    data = request.args
    plant = models.ServicePlant.query.filter_by(id=int(data['id'])).first()

    plant.plant_name = data['plant_name']
    plant.plant_count = data['plant_count']

    plant.plant_guarantee = bool(json.loads(data['plant_guarantee']))
    plant.plant_client = bool(json.loads(data['plant_client']))
    plant.plant_container = data['plant_container']
    if plant.plant_type == 'phytowall':
        client = models.Client.query.filter_by(id=int(data['client_id'])).first()
        client.phyto_flag = True

    if plant.plant_id != int(data['plant_id']):
        plant.plant_id = int(data['plant_id'])
        plant.plant_type = models.Plant.query.filter_by(id=int(data['plant_id'])).first().type

    hist = models.PlantHistory()
    hist.plant_name = data['plant_name']
    hist.plant_container = data['plant_container']
    hist.date = date_to_string(datetime.today())
    hist.service_id = plant.service_id

    db.session.add(hist)
    db.session.commit()

    return 'OK'


@app.route('/addPlace')
def addPlace():
    data = request.args
    place = models.Place()
    service = models.Service()
    floor = models.Floor.query.filter_by(id=int(data['floor_id'])).first()
    place.name = data['room_name']
    place.service.append(service)
    floor.place_list.append(place)

    db.session.commit()
    return 'OK'


@app.route('/startDay')
def startDay():
    if request.headers['Authorization']:
        users = models.User.query
        user = users.filter_by(token=request.headers['Authorization']).first()

        if not user:
            abort(403)
        clients = models.Client.query.filter_by(team_id=int(user.team_id)).all()

        for client in clients:
            client.status = -1

        if not user:
            abort(403)

        date = datetime.now()
        team = models.Team.query.filter_by(id=int(user.team_id)).first()

        if user.id == team.leader_id:
            team_hist = models.TeamHist()

        else:
            team_hist = models.TeamHist.query.filter_by(team_id=team.id).first()

        hist = models.UserHist()
        user.cords = request.args['cords']

        if team_hist:
            if json.loads(request.args['cords']):
                data = [json.loads(request.args['cords'])]
                team_hist.way_list = json.dumps([json.loads(request.args['cords'])])

                while 'null' in data:
                    data.remove('null')

                while None in data:
                    data.remove(None)

                socketio.emit('getCords', {'team_id': team.id, 'data': data}, broadcast=True)
            else:
                team_hist.way_list = '[]'

            team_hist.way_list = json.dumps([json.loads(request.args['cords'])])
            team_hist.date = date_to_string(date)
            team.team_hist.append(team_hist)

        hist.cords = request.args['cords']
        hist.date = date_to_string(date)
        hist.time_start = str(date.hour) + ':' + str(date.minute)
        if json.loads(request.args['cords']):
            hist.way_list = json.dumps([json.loads(request.args['cords'])])
        user.user_hist.append(hist)

        db.session.commit()
        return 'OK'
    else:
        abort(400)


@app.route('/endDay')
def endDay():
    if request.headers['Authorization']:
        user = models.User.query.filter_by(token=request.headers['Authorization']).first()
        if not user:
            abort(403)
        user.cords = request.args['cords']

        date = datetime.now()

        hist = models.UserHist.query.filter_by(date=date_to_string(date)).filter_by(user_id=user.id).first()
        try:
            buffer = json.loads(hist.way_list)
            buffer.append(json.loads(request.args['cords']))
            hist.way_list = json.dumps(buffer)
        except Exception as er:
            print('Last cord was not saved', er)

        hist.time_end = str(date.hour) + ':' + str(date.minute)

        db.session.commit()
        return 'OK'
    else:
        abort(400)


@app.route('/startClient')
def startClient():
    team = models.Team.query.filter_by(id=int(request.args['team_id'])).first()
    team.cords = request.args['cords']
    date = datetime.now()
    client = models.Client.query.filter_by(id=int(request.args['client_id'])).first()

    tasks = models.GantTask.query.filter_by(planclient=client.name).filter_by(
        planteam_id=int(request.args['team_id'])).filter_by(date=date_to_string(date)).all()
    for i in range(0, len(tasks)):
        tasks[i].in_process = True

    client.status = 0
    client_hist = models.TeamClientHistory()

    client_hist.time_start = str(date.hour) + ':' + str(date.minute)
    workers = models.UserHist.query

    if client.quantity:
        for i in json.loads(team.workers):
            worker = workers.filter_by(user_id=int(i)).filter_by(date=date_to_string(date)).first()
            if not worker.time_planned:
                worker.time_planned = time_to_string(timedelta())
            if not worker.planned_units:
                worker.planned_units = 0
            buffer = time(worker.time_planned)
            buffer += (timedelta(minutes=2) * int(client.quantity)) / len(json.loads(team.workers))
            worker.time_planned = time_to_string(buffer)
            worker.planned_units += int(client.quantity)

    client_hist.client_name = client.name
    team_hist = models.TeamHist.query.filter_by(team_id=team.id).filter_by(date=date_to_string(date)).first()

    if not team_hist:
        team_hist = models.TeamHist()
        team_hist.date = date_to_string(date)
        team_hist.client_hist.append(client_hist)
        team_hist.way_list = '[]'

        buffer = json.loads(team_hist.way_list)
        buffer.append(json.loads(request.args['cords']))
        team_hist.way_list = json.dumps(buffer)
        while None in buffer:
            buffer.remove(None)
        while 'null' in buffer:
            buffer.remove('null')
        socketio.emit('getCords', {'team_id': team.id, 'data': buffer}, broadcast=True)

        team_hist.team_id = team.id
        db.session.add(team_hist)
    else:
        if not models.TeamClientHistory.query.filter_by(hist_id=team_hist.id, client_name=client_hist.client_name).first():
            team_hist.client_hist.append(client_hist)
        buffer = json.loads(team_hist.way_list)
        buffer.append(json.loads(request.args['cords']))
        team_hist.way_list = json.dumps(buffer)
        while None in buffer:
            buffer.remove(None)
        while 'null' in buffer:
            buffer.remove('null')
        socketio.emit('getCords', {'team_id': team.id, 'data': buffer}, broadcast=True)

    db.session.commit()
    return 'OK'


@app.route('/endClient')
def endClient():
    check_token_update()
    team = models.Team.query.filter_by(id=int(request.args['team_id'])).first()
    team.cords = request.args['cords']
    client = models.Client.query.filter_by(id=int(request.args['client_id'])).first()
    date = datetime.now()
    tasks = models.Task.query.filter_by(planclient=client.name).filter_by(
        planteam_id=int(request.args['team_id'])).filter_by(date=date_to_string(date)).all()
    gant = models.GantTask.query

    gant_tasks = models.GantTask.query.filter_by(date=date_to_string(date), planteam_id=int(request.args['team_id'])).filter_by(
        planclient=client.name).all()

    for i in range(0, len(gant_tasks)):
        gant_tasks[i].done = True

    workers = json.loads(team.workers)
    worker_hist = models.UserHist.query

    if 'service' in request.args:
        if request.args['service'] != '"Передать"':
            report = models.Report()
            report.client = client.name
            report.comment = request.args['comment']
            team_orders = models.TeamOrders.query.filter_by(date=date_to_string(date)).filter_by(
                client=client.name).all()
            report.replace = table_to_json(team_orders)
            report.checked = False
            report.date = date_to_string(date) + ' ' + str(date.hour) + ':' + str(date.minute)
            report.team_id = team.id
            report.additional = request.args['comment']
            if 'phytowall_comment' in request.args:
                report.phytowall_comment = request.args['phytowall_comment']
            last_report = models.Report.query.filter_by(client=client.name).all()
            if last_report:
                report.comment_last = last_report[len(last_report) - 1].comment

            contact = models.Contacts.query.filter_by(client_id=client.id).first()
            if contact:
                report.contact = contact.name
            report.service = request.args['service']
            db.session.add(report)
            db.session.commit()
            for i in range(0, len(tasks)):
                tasks[i].done = True
                processing = gant.filter_by(task_id=tasks[i].id).first()
                if processing:
                    processing.in_process = False

                task_list = models.TaskList.query.filter_by(task_id=tasks[i].id).first()
                report_list = models.ReportList()
                report_list.report_id = report.id
                report_list.description = task_list.description_id
                report_list.sub_tasks = task_list.sub_tasks
                report_list.comment = task_list.comment
                report_list.done = task_list.done

                db.session.add(report_list)

            photos = models.Image.query.filter_by(client=client.name, directory_id=client.report_directory_id,
                                                  date=date_to_string(date)).all()

            for i in range(len(photos)):
                if not photos[i].report_id:
                    photos[i].report_id = report.id
            photos1 = models.Image.query.filter_by(client=client.name, directory_id=client.replace_directory_id,
                                                   date=date_to_string(date)).all()

            for i in range(len(photos1)):
                if not photos1[i].report_id:
                    photos1[i].report_id = report.id
                photos1[i].report_id = report.id

            db.session.commit()
            if client.autoreport:
                photos = models.Image.query.filter_by(report_id=report.id).all()
                photo_arr = []
                for i in photos:
                    photo_arr.append(i.file_url)
                if photo_arr:
                    photos = join(photo_arr, ', ')
                else:
                    photos = ''
                workers_id = json.loads(team.workers)
                workers = []
                users = models.User.query
                for i in workers_id:
                    workers.append(users.filter_by(id=i).first().name)
                contacts = models.Contacts.query.filter_by(client_id=client.id).all()

                for i in contacts:
                    if i.email:
                        w_list = ''
                        try:
                            for k in json.loads(report.service):
                                w_list += (k + ', ')
                            w_list = w_list[:-2]
                        except Exception:
                            w_list = report.service

                        contact_name = report.contact

                        exchange_handler.send_message(email_content=render_template('mail.html',
                                                                                    client_name=client.name,
                                                                                    date=report.date,
                                                                                    work_list=w_list,
                                                                                    replace=report.replace,
                                                                                    additional=report.additional,
                                                                                    photos=photos,
                                                                                    team=team.name,
                                                                                    workers=join(workers, ', '),
                                                                                    contact=contact_name),
                                                      email=i.email)
                        break

    team_hist = models.TeamHist.query.filter_by(team_id=team.id).filter_by(date=date_to_string(date)).first()
    client.status = 1
    client.comment_last = request.args['comment']
    client.service = request.args['service']

    client_hist = None

    for i in team_hist.client_hist:
        if i.client_name == client.name:
            client_hist = models.TeamClientHistory.query.filter_by(id=i.id).first()

    if client_hist:
        client_hist.time_end = str(date.hour) + ':' + str(date.minute)

        for i in range(0, len(workers)):
            worker = worker_hist.filter_by(user_id=int(workers[i])).filter_by(date=date_to_string(date)).first()
            if worker:
                if not worker.performed_units:
                    worker.performed_units = 0
                if client.quantity:
                    worker.performed_units += int(client.quantity)
                worker.time_fact = time_to_string(time(str(date.hour) + ':' +
                                                       str(date.minute)) - time(client_hist.time_start))
            db.session.commit()
        return 'OK'
    else:
        db.session.commit()
        return 'something went wrong'


@app.route('/startCar')
def startCar():
    if request.headers['Authorization']:
        user = models.User.query.filter_by(token=request.headers['Authorization']).first()
        if not user:
            abort(403)
        user.start_car = request.args['start_car']
        user.end_car = None
        user.cords = request.args['cords']
        date = datetime.today()
        user_hist = models.UserHist.query.filter_by(user_id=user.id).filter_by(date=date_to_string(date)).first()
        if user_hist:
            user_hist.start_car = request.args['start_car']
            user_hist.end_car = None

        db.session.commit()
        return 'OK'
    else:
        abort(400)


@app.route('/endCar')
def endCar():
    if request.headers['Authorization']:
        user = models.User.query.filter_by(token=request.headers['Authorization']).first()
        if not user:
            abort(403)
        user.start_car = request.args['end_car']
        user.cords = request.args['cords']
        date = datetime.today()
        user_hist = models.UserHist.query.filter_by(user_id=user.id).filter_by(
            date=date_to_string(date)).first()
        if user_hist:
            user_hist.end_car = request.args['end_car']

        db.session.commit()
        return 'OK'
    else:
        abort(400)


@app.route('/sendReport')
def sendReport():
    report = models.Report()
    data = request.args
    date = datetime.now()
    report.client = data['client']
    report.date = date_to_string(date) + ' ' + str(date.hour) + ':' + str(date.minute)
    report.replace = data['replace']
    report.additional = data['additional']
    last_report = models.Report.query.filter_by(client=data['client']).all()
    if last_report:
        report.comment_last = last_report[len(last_report) - 1].comment

    db.session.add(report)
    db.session.commit()

    return 'OK'


@app.route('/editWebReport')
def editWebReport():
    data = request.args
    report = models.Report.query.filter_by(id=data['report_id']).first()
    report.replace = data['replace']
    report.additional = data['additional']

    db.session.commit()
    return 'OK'


@app.route('/deletePlace')
def deletePlace():
    place = models.Place.query.filter_by(id=request.args['room_id']).first()

    db.session.delete(place)
    db.session.commit()
    return 'OK'


@app.route('/deleteFloor')
def deleteFloor():
    floor = models.Floor.query.filter_by(id=request.args['floor_id']).first()

    db.session.delete(floor)
    db.session.commit()
    return 'OK'


@app.route('/attachItemToPlace')
def attachItemToPlace():
    data = request.args
    service = models.Service.query.filter_by(place_id=data['place_id']).first()
    plant = models.ServicePlant()

    plant.plant_count = data['count']
    plant.plant_type = data['type']
    plant.plant_guarantee = data['guarantee']
    plant.plant_dh = data['dh']
    plant.plant_name = data['name']
    plant.plant_id = data['id']
    service.plants.append(plant)

    db.session.commit()
    return 'OK'


@app.route('/attachTask')
def attachTask():
    Task = models.TaskList.query.filter_by(id=int(request.args['task_id'])).first()
    if Task:
        repTask = models.ReportList()
        repTask.comment = Task.comment
        repTask.description = Task.description_id
        repTask.sub_tasks = Task.sub_tasks
        report = models.Report.query.filter_by(id=int(request.args['report_id'])).first()
        report.report_list = repTask
        db.session.commit()
    else:
        return 'Wrong task_id or report_id'


@app.route('/deleteTask')
def deleteTask():
    Task = models.Task.query.filter_by(id=int(request.args['id'])).first()
    if Task:
        Client = models.Client.query.filter_by(name=Task.planclient).first()
        Client.team_id = None
        if Task.transport_ids:
            db.session.delete(models.TransportHistory.query.filter_by(task_id=Task.id).first())
        if Task.replace:
            db.session.delete(models.ReplaceHistory.query.filter_by(task_id=Task.id).first())
        db.session.delete(Task)
        db.session.commit()
    return 'OK'


@app.route('/deleteGantTask')
def deleteGantTask():
    Task = models.GantTask.query.filter_by(id=int(request.args['id'])).first()
    task = models.Task.query.filter_by(gant_id=int(request.args['id'])).all()
    if task:
        team = models.Team.query.filter_by(id=int(task[0].planteam_id)).first()
        if len(task) > 1:
            db.session.delete(task[1])

        client_list = models.ClientList.query.filter_by(team_id=team.id).filter_by(date=Task.date).filter_by(
            client=task[0].planclient).first()

        if Task:
            db.session.delete(client_list)
            db.session.delete(task[0])
    if Task:
        db.session.delete(Task)
    db.session.commit()
    return 'OK'


@app.route('/deleteEtalonGant')
def deleteEtalonGant():
    Task = models.EtalonGant.query.filter_by(id=int(request.args['id'])).first()
    gant = models.GantTask.query.filter_by(etalon_id=Task.id).all()
    task_query = models.Task.query

    if Task:
        db.session.delete(Task)
        if gant:
            for i in range(len(gant)):
                task = task_query.filter_by(gant_id=gant[i].id).all()
                if task:
                    team = models.Team.query.filter_by(id=int(task[0].planteam_id)).first()
                    if gant:
                        client_list = models.ClientList.query.filter_by(team_id=team.id).filter_by(
                            date=gant[0].date).filter_by(
                            client=task[0].planclient).first()
                        if client_list:
                            db.session.delete(client_list)
                    for j in range(len(task)):
                        db.session.delete(task[j])
                db.session.delete(gant[i])
        db.session.commit()
    return 'OK'


@app.route('/getPeopleInfo')
def getPeopleInfo():
    team = models.Team.query.filter_by(id=int(request.args['team_id'])).first()
    workers = json.loads(team.workers)
    users = models.User.query
    result = []
    for worker_id in workers:
        result.append(json.loads(table_to_json(users.filter_by(id=worker_id).first())))
    return json.dumps(result)


@app.route('/dragEtalonTask')
def dragEtalonTask():
    Task = models.EtalonGant.query.filter_by(id=int(request.args['id'])).first()
    task = models.GantTask.query.filter_by(etalon_id=Task.id).all()
    date = date_to_string(datetime.today())
    if task:
        for i in range(len(task)):
            task[i].time = request.args['time']
            if task[i].planteam_id != int(request.args['planteam_id']):
                prev_id = task.planteam_id
                task[i].planteam_id = int(request.args['planteam_id'])
                prev_list = models.ClientList.query.filter_by(date=date).filter_by(client=Task.planclient).filter_by(
                    team_id=prev_id).first()

                db.session.delete(prev_list)

                client_list = models.ClientList()
                client_list.client = task[i].planclient
                client_list.date = task[i].date
                client_list.team_id = int(request.args['planteam_id'])
                db.session.add(client_list)

    if Task:
        Task.time = request.args['time']
        if Task.planteam_id != int(request.args['planteam_id']):
            Task.planteam_id = int(request.args['planteam_id'])

    db.session.commit()
    return 'OK'


@app.route('/dragTask')
def dragTask():
    Task = models.GantTask.query.filter_by(id=int(request.args['id'])).first()
    date = date_to_string(datetime.today())
    task = models.Task.query.filter_by(gant_id=Task.id).all()

    if Task:
        if Task.planteam_id != int(request.args['planteam_id']):
            if len(task) > 1:
                task[1].planteam_id = int(request.args['planteam_id'])

            task[0].planteam_id = int(request.args['planteam_id'])
            prev_id = Task.planteam_id
            Task.planteam_id = int(request.args['planteam_id'])
            prev_list = models.ClientList.query.filter_by(date=date).filter_by(client=Task.planclient).filter_by(
                team_id=prev_id).first()

            db.session.delete(prev_list)

            client_list = models.ClientList()
            client_list.client = Task.planclient
            client_list.date = Task.date
            client_list.team_id = int(request.args['planteam_id'])

            db.session.add(client_list)

        Task.time = request.args['time']
        db.session.commit()
    return 'OK'


@app.route('/addTransport')
def addTransport():
    data = request.args

    if data['transport_id'] == 'new':
        transport = models.TransportHistory()
    elif data['transport_id']:
        transport = models.TransportHistory.query.filter_by(id=data['transport_id']).first()
    else:
        abort(400)

    transport.plant_name = data['plant_name']
    transport.team_id = data['team_id']
    transport.date = data['date']
    transport.client_name = data['client_name']
    transport.count = data['count']
    transport.plant_id = data['plant_id']
    transport.task_id = data['task_id']

    if data['transport_id'] == 'new':
        db.session.add(transport)
    db.session.commit()

    return 'OK'


@app.route('/getEtalonGant')
def getEtalonGant():
    team = False
    if 'team' in request.args:
        team = int(request.args['team'])
    if 'day' in request.args:
        if 'team' in request.args:
            Tasks = models.EtalonGant.query.filter_by(planteam_id=team).filter_by(
                week=int(request.args['week'])).filter_by(day=request.args['day']).all()
        else:
            Tasks_buf = models.EtalonGant.query.filter_by(week=int(request.args['week'])).filter_by(
                day=request.args['day']).all()
            Tasks = []
            for t in Tasks_buf:
                team = models.Team.query.filter_by(id=t.planteam_id).first()
                if team:
                    if team.city == request.args['city']:
                        Tasks.append(t)
    else:
        if not team:
            Tasks_buf = models.EtalonGant.query.filter_by(week=int(request.args['week'])).all()
            Tasks = []
            for t in Tasks_buf:
                team = models.Team.query.filter_by(id=t.planteam_id).first()
                if team:
                    if team.city == request.args['city']:
                        Tasks.append(t)
        else:
            Tasks = models.EtalonGant.query.filter_by(planteam_id=request.args['team']).filter_by(
                week=int(request.args['week'])).all()
    return table_to_json(Tasks)


def changePeriodTasks(etalon_id, data):
    gants = models.GantTask.query.filter_by(etalon_id=etalon_id).all()
    task_query = models.Task.query

    for i in range(len(gants)):
        gants[i].time = data['time']
        gants[i].planclient = data['planclient']
        gants[i].planteam_id = data['planteam_id']
        if 'contact' in data:
            gants[i].contact = data['contact']
        if 'address' in data:
            gants[i].address = data['address']
        if 'comment' in data:
            gants[i].comment = data['comment']
        if 'ce' in data:
            gants[i].ce = data['ce']
        if 'warranty' in data:
            gants[i].warranty = data['warranty']
        if 'containers' in data:
            gants[i].containers = data['containers']

        tasks = task_query.filter_by(gant_id=gants[i].id).all()
        for j in range(len(tasks)):
            tasks[j].planclient = data['planclient']
            tasks[j].planteam_id = data['planteam_id']
            tasks[j].time = data['time']
            tasks[j].done = False
            tasks[j].planclient = data['planclient']
            tasks[j].planteam_id = data['planteam_id']
            tasks[j].time = data['time']

    db.session.commit()


def setPeriodTasks(gant, data):
    year = timedelta(days=365)
    date_now = str_to_date(date=data['date'])
    date_end = str_to_date(date=date_to_string(str_to_date(data['date']) + year))
    two_weeks = timedelta(days=14)

    while date_now <= date_end:
        date_now += two_weeks
        task = models.GantTask()
        task.plantype_work = gant.plantype_work
        task.done = gant.done
        task.planclient = gant.planclient
        task.planteam_id = gant.planteam_id
        task.contact = gant.contact
        task.address = gant.address
        task.comment = gant.comment
        task.ce = gant.ce
        task.warranty = gant.warranty
        task.containers = gant.containers
        task.date = date_to_string(date_now)
        task.time = gant.time
        task.etalon_id = gant.etalon_id


        Task = models.Task()
        Task_list = models.TaskList()
        if data['plantype_work'] == 'phytowall':
            Task_list.description_id = 4
        elif data['plantype_work'] == 'service':
            Task_list.description_id = 3
        elif data['plantype_work'] == 'all':
            Task_list.description_id = 3
            Task1 = models.Task()
            Task_list2 = models.TaskList()
            Task_list2.description_id = 4
            if 'comment' in data:
                Task1.task_list.comment = data['comment']
            Task1.task_list = [Task_list2]

        if 'comment' in data:
            Task_list.comment = data['comment']
        Task.task_list.append(Task_list)
        Task.planclient = data['planclient']
        Task.planteam_id = data['planteam_id']
        Task.date = date_to_string(date_now)
        Task.time = data['time']
        Task.done = False
        Task.type_work = 'Сервисные'

        if data['plantype_work'] == 'all':
            Task1.planclient = data['planclient']
            Task1.planteam_id = data['planteam_id']
            Task1.date = date_to_string(date_now)
            Task1.time = data['time']
            Task1.done = False
            Task1.type_work = 'Сервисные'
            db.session.add(Task1)

        db.session.add(task)
        db.session.add(Task)
        db.session.commit()

        Task.gant_id = task.id
        if data['plantype_work'] == 'all':
            Task1.gant_id = task.id

    db.session.commit()


@app.route('/addEtalonGant')
def addEtalonGant():
    data = request.args
    if data['id'] == 'new':
        task = models.EtalonGant()
        gant = models.GantTask()
        gant.phyto_status = False

    else:
        task = models.EtalonGant.query.filter_by(id=int(data['id'])).first()
        gant = models.GantTask.query.filter_by(etalon_id=task.id).first()

    if 'plantype_work' in data:
        task.plantype_work = data['plantype_work']
        gant.plantype_work = data['plantype_work']
    team = models.Team.query.filter_by(id=int(data['planteam_id'])).first()
    client_list = models.ClientList.query.filter_by(team_id=team.id).filter_by(date=data['date']).filter_by(
        client=task.planclient).first()
    if not client_list:
        client_list = models.ClientList()
        client_list.date = data['date']
        client_list.client = data['planclient']
        client_list.team_id = team.id
        db.session.add(client_list)

    Task = models.Task.query.filter_by(planclient=data['planclient']).filter_by(
        planteam_id=int(data['planteam_id'])).filter_by(date=data['date']).all()
    sec_flag = False
    if len(Task) > 1:
        sec_flag = True
        Task1 = Task[1]

    if Task:
        Task = Task[0]

    if not Task:
        Task = models.Task()
        Task_list = models.TaskList()
        if data['plantype_work'] == 'phytowall':
            Task_list.description_id = 4
        elif data['plantype_work'] == 'service':
            Task_list.description_id = 3
        elif data['plantype_work'] == 'all':
            Task_list.description_id = 3
            Task1 = models.Task()
            Task_list2 = models.TaskList()
            Task_list2.description_id = 4
            if 'comment' in data:
                Task1.task_list.comment = data['comment']
            Task1.task_list = [Task_list2]

        if 'comment' in data:
            Task_list.comment = data['comment']
        Task.task_list.append(Task_list)
        Task.mobile = False
        Task.approved = True
        Task.planclient = data['planclient']
        Task.planteam_id = data['planteam_id']
        Task.date = data['date']
        Task.time = data['time']
        Task.done = False
        Task.type_work = 'Сервисные'

        if data['plantype_work'] == 'all':
            Task1.mobile = False
            Task1.approved = True
            Task1.planclient = data['planclient']
            Task1.planteam_id = data['planteam_id']
            Task1.date = data['date']
            Task1.time = data['time']
            Task1.done = False
            Task1.type_work = 'Сервисные'
            db.session.add(Task1)

        db.session.add(Task)

    Task.planclient = data['planclient']
    Task.planteam_id = data['planteam_id']
    Task.date = data['date']
    Task.time = data['time']

    if sec_flag:
        Task1.planclient = data['planclient']
        Task1.planteam_id = data['planteam_id']
        Task1.date = data['date']
        Task1.time = data['time']

    task.date = data['date']
    task.time = data['time']
    task.day = data['day']
    task.week = int(data['week'])
    task.planclient = data['planclient']
    task.planteam_id = data['planteam_id']
    if 'contact' in data:
        task.contact = data['contact']
    if 'address' in data:
        task.address = data['address']
    if 'comment' in data:
        task.comment = data['comment']
    if 'ce' in data:
        task.ce = data['ce']
    if 'warranty' in data:
        task.warranty = data['warranty']
    if 'containers' in data:
        task.containers = data['containers']
    task.done = False
    task.in_process = False

    gant.done = False
    gant.date = data['date']
    gant.time = data['time']
    gant.planclient = data['planclient']
    gant.planteam_id = data['planteam_id']
    if 'contact' in data:
        gant.contact = data['contact']
    if 'address' in data:
        gant.address = data['address']
    if 'comment' in data:
        gant.comment = data['comment']
    if 'ce' in data:
        gant.ce = data['ce']
    if 'warranty' in data:
        gant.warranty = data['warranty']
    if 'containers' in data:
        gant.containers = data['containers']

    if data['id'] == 'new':
        db.session.add(task)
        db.session.commit()
        gant.etalon_id = task.id
        db.session.add(gant)
        setPeriodTasks(gant=gant, data=data)
    else:
        changePeriodTasks(etalon_id=task.id, data=data)

    client = models.Client.query.filter_by(name=data['planclient']).first()
    client.team_id = int(data['planteam_id'])
    client.start_service = data['date']
    year = timedelta(days=365)
    client.end_service = date_to_string(str_to_date(data['date']) + year)
    Task.gant_id = gant.id

    if data['plantype_work'] == 'all':
        Task1.gant_id = gant.id

    db.session.commit()
    return 'OK'


@app.route('/addGantTask')
def addGantTask():
    data = request.args
    if data['id'] == 'new':
        task = models.GantTask()
    else:
        task = models.GantTask.query.filter_by(id=int(data['id'])).first()

    if 'plantype_work' in data:
        task.plantype_work = data['plantype_work']

    team = models.Team.query.filter_by(id=int(data['planteam_id'])).first()

    client_list = models.ClientList.query.filter_by(team_id=team.id).filter_by(date=data['date']).filter_by(
        client=task.planclient).first()
    if not client_list:
        client_list = models.ClientList()
        client_list.date = data['date']
        client_list.client = data['planclient']
        client_list.team_id = team.id
        db.session.add(client_list)

    task.date = data['date']
    task.time = data['time']
    task.planclient = data['planclient']
    task.planteam_id = data['planteam_id']
    if 'contact' in data:
        task.contact = data['contact']
    if 'address' in data:
        task.address = data['address']
    if 'comment' in data:
        task.comment = data['comment']
    if 'ce' in data:
        task.ce = data['ce']
    if 'warranty' in data:
        task.warranty = data['warranty']
    if 'containers' in data:
        task.containers = data['containers']
    task.done = False
    task.in_process = False

    if data['id'] == 'new':
        db.session.add(task)
        db.session.commit()

    Task = models.Task.query.filter_by(planclient=data['planclient']).filter_by(
        planteam_id=int(data['planteam_id'])).filter_by(date=data['date']).filter_by(gant_id=task.id).all()
    sec_flag = False
    if len(Task) > 1:
        sec_flag = True
        Task1 = Task[1]

    if Task:
        Task = Task[0]

    if not Task:
        Task = models.Task()
        Task_list = models.TaskList()
        if data['plantype_work'] == 'phytowall':
            Task_list.description_id = 4
        elif data['plantype_work'] == 'service':
            Task_list.description_id = 3
        elif data['plantype_work'] == 'all':
            Task_list.description_id = 3
            Task1 = models.Task()
            Task_list2 = models.TaskList()
            Task_list2.description_id = 4
            if 'comment' in data:
                Task1.task_list.comment = data['comment']
            Task1.task_list = [Task_list2]

        if 'comment' in data:
            Task_list.comment = data['comment']

        Task.task_list = [Task_list]
        Task.planclient = data['planclient']
        Task.planteam_id = data['planteam_id']
        Task.date = data['date']
        Task.time = data['time']
        Task.done = False
        Task.mobile = False
        Task.approved = True
        Task.type_work = 'Сервисные'

        if data['plantype_work'] == 'all':
            Task1.mobile = False
            Task1.approved = True
            Task1.planclient = data['planclient']
            Task1.planteam_id = data['planteam_id']
            Task1.date = data['date']
            Task1.time = data['time']
            Task1.done = False
            Task1.type_work = 'Сервисные'
            db.session.add(Task1)
            db.session.commit()

        client = models.Client.query.filter_by(name=data['planclient']).first()
        client.team_id = int(data['planteam_id'])

        db.session.add(Task)

    Task.planclient = data['planclient']
    Task.planteam_id = data['planteam_id']
    Task.date = data['date']
    Task.time = data['time']

    if sec_flag:
        Task1.planclient = data['planclient']
        Task1.planteam_id = data['planteam_id']
        Task1.date = data['date']
        Task1.time = data['time']

    if data['id'] == 'new':
        task.task_id = Task.id

    Task.gant_id = task.id
    if data['plantype_work'] == 'all':
        Task1.gant_id = task.id

    db.session.commit()
    return 'OK'


def periodHandler(period):
    date_end = datetime(day=int(period.split('-')[1].split('.')[0]), month=int(period.split('-')[1].split('.')[1]),
                        year=int(period.split('-')[1].split('.')[2]))
    result = []
    iteration = timedelta(days=1)
    date_now = datetime(day=int(period.split('-')[0].split('.')[0]), month=int(period.split('-')[0].split('.')[1]),
                        year=int(period.split('-')[0].split('.')[2]))
    while date_end >= date_now:
        write_day = str(date_now.day)
        write_month = str(date_now.month)
        if int(date_now.day) < 10:
            write_day = '0' + str(date_now.day)
        if int(date_now.month) < 10:
            write_month = '0' + str(date_now.month)
        result.append('{0}.{1}.{2}'.format(write_day, write_month, date_now.year))
        date_now = date_now + iteration
    return result


@app.route('/deleteUserFromTeam')
def deleteUserFromTeam():
    user = models.User.query.filter_by(id=int(request.args['id'])).first()
    user.team_id = None
    team = models.Team.query.filter_by(id=int(request.args['team_id'])).first()
    workers = json.loads(team.workers)
    workers.remove(int(request.args['id']))
    team.workers = json.dumps(workers)

    db.session.commit()
    return 'OK'


@app.route('/deleteBadUsers')
def deleteBadUsers():
    users = models.User.query.filter_by(city=None).all()
    bad_buffer = []
    for i in users:
        bad_buffer.append(i.login)
        db.session.delete(i)
    db.session.commit()
    return json.dumps(bad_buffer)


@app.route('/getTasks')
def getTasks():
    if 'date' in request.args:
        if '-' in request.args['date']:
            all_tasks = models.Task.query
            Tasks = []
            for i in periodHandler(request.args['date']):
                now_t = all_tasks.filter_by(date=i).all()
                mobile = all_tasks.filter_by(date=None).all()
                for j in mobile:
                    now_t.append(j)
                if now_t:
                    for t in now_t:
                        team = models.Team.query.filter_by(id=t['planteam_id']).first()
                        if team.city == request.args['city']:
                            if t.transport_ids or t.replace or t.type_work != 'Сервисные':
                                Tasks.append(t)
        else:
            Tasks = []
            all_tasks = models.Task.query.filter_by(date=request.args['date']).all()
            mobile = models.Task.query.filter_by(date=None).all()
            for j in mobile:
                all_tasks.append(j)
            for i in range(0, len(all_tasks)):
                team = models.Team.query.filter_by(id=all_tasks[i].planteam_id).first()
                if team:
                    if team.city == request.args['city']:
                        if all_tasks[i].transport_ids or all_tasks[i].replace or all_tasks[i].type_work != 'Сервисные':
                            Tasks.append(all_tasks[i])
                else:
                    client = models.Client.query.filter_by(name=all_tasks[i].planclient).first()
                    if client:
                        if client.city == request.args['city']:
                            if all_tasks[i].transport_ids or all_tasks[i].replace or all_tasks[i].type_work != 'Сервисные':
                                Tasks.append(all_tasks[i])
                    else:
                        continue
    else:
        Tasks = models.Task.query.all()
    return table_to_json(Tasks)


@app.route('/getGantTasks')
def getGantTasks():
    team = False
    if 'team' in request.args:
        team = int(request.args['team'])
    if 'date' in request.args:
        if 'team' in request.args:
            if '-' in request.args['date']:
                all_tasks = models.GantTask.query
                Tasks = []
                for i in periodHandler(request.args['date']):
                    now_t = all_tasks.filter_by(planteam_id=request.args['team']).filter_by(date=i).all()
                    if now_t:
                        for t in now_t:
                            team = models.Team.query.filter_by(id=t.planteam_id).first()
                            if team:
                                if team.city == request.args['city']:
                                    Tasks.append(t)

            else:
                Tasks = models.GantTask.query.filter_by(planteam_id=team).filter_by(date=request.args['date']).all()
        else:
            if '-' in request.args['date']:
                all_tasks = models.GantTask.query
                Tasks = []
                print(periodHandler(request.args['date']))
                for i in periodHandler(request.args['date']):
                    now_t = all_tasks.filter_by(date=i).all()
                    if now_t:
                        for t in now_t:
                            team = models.Team.query.filter_by(id=t.planteam_id).first()
                            if team:
                                if team.city == request.args['city']:
                                    Tasks.append(t)
            else:
                Tasks_buf = models.GantTask.query.filter_by(date=request.args['date']).all()
                Tasks = []
                for t in Tasks_buf:
                    team = models.Team.query.filter_by(id=t.planteam_id).first()
                    if team:
                        if team.city == request.args['city']:
                            Tasks.append(t)
    else:
        if not team:
            Tasks_buf = models.GantTask.query.all()
            Tasks = []
            for t in Tasks_buf:
                team = models.Team.query.filter_by(id=t.planteam_id).first()
                if team:
                    if team.city == request.args['city']:
                        Tasks.append(t)
        else:
            Tasks_buf = models.GantTask.query.filter_by(planteam_id=request.args['team']).all()
            Tasks = []
            for t in Tasks_buf:
                team = models.Team.query.filter_by(id=t.planteam_id).first()
                if team:
                    if team.city == request.args['city']:
                        Tasks.append(t)

    return table_to_json(Tasks)


@app.route('/getTeam')
def getTeam():
    if request.headers['Authorization']:
        result = []
        try:
            user = models.User.query.filter_by(token=request.headers['Authorization']).first()
            team = models.Team.query.filter_by(id=user.team_id).first()
            subres = json.loads(table_to_json([team]))[0]
            try:
                id_buf = json.loads(subres['workers'])
                subres['workers'] = []
                workers = json.loads(table_to_json(models.User.query.filter(models.User.id.in_(id_buf)).all()))
                for i in workers:
                    i.pop('password', None)
                    i.pop('login', None)
                    i.pop('token', None)
                    subres['workers'].append(i)
            except Exception:
                foo = 'bar'
            result.append(subres)
        except Exception:
            abort(403)
        return json.dumps(result)
    else:
        abort(400)


@app.route('/getAllTasks', methods=['GET'])
def getAllTasks():
    return table_to_json(models.Task.query.all())


@app.route('/getAllTeams', methods=['GET'])
def getAllTeams():
    Teams = models.Team.query.all()
    result = []
    for team in Teams:
        subres = json.loads(table_to_json([team]))[0]
        try:
            id_buf = json.loads(subres['workers'])
            subres['workers'] = []
            workers = json.loads(table_to_json(models.User.query.filter(models.User.id.in_(id_buf)).all()))
            for i in workers:
                i.pop('password', None)
                i.pop('login', None)
                i.pop('token', None)
                subres['workers'].append(i)
        except Exception as er:
            foo = 'bar'
        result.append(subres)
    return json.dumps(result)


@app.route('/auth', methods=['GET'])
def auth():
    if models.User.query.filter_by(login=request.args['login']).first():
        user = models.User.query.filter_by(login=request.args['login']).first()
    else:
        return json.dumps({'message': 'Неверный логин', 'success': False})
    if user.password != request.args['password']:
        return json.dumps({'message': 'Неверный пароль', 'success': False})
    if not user.token:
        alphabet = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'g', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r',
                    's', 't', 'u', 'v', 'w', 'x', 'v', 'z', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'G',
                    'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'V', 'Z', '-', '0',
                    '1', '2', '3', '4', '5', '6', '7', '8', '9']
        token = ''
        for i in range(0, 50):
            token += alphabet[randint(0, len(alphabet)) - 1]
        user.token = token
        db.session.commit()
        return json.dumps({'message': token, 'name': user.name, 'driver': user.driver_status, 'success': True})
    else:
        return json.dumps({'message': user.token, 'name': user.name, 'driver': user.driver_status, 'success': True})


@app.route('/getUsers')
def getUsers():
    return table_to_json(models.User.query.filter_by(city=request.args['city']).all())


@app.route('/getUsersHist')
def getUsersHist():
    users = models.User.query.filter_by(city=request.args['city']).all()
    hist = models.UserHist.query
    result = []
    for i in range(len(users)):
        result.append(json.loads(table_to_json(hist.filter_by(user_id=users[i].id).all())))

    return json.dumps(result)


@app.route('/getTeams')
def getTeams():
    result = json.loads(table_to_json(models.Team.query.filter_by(city=request.args['city']).all()))
    for i in range(0, len(result)):
        result[i]['workers'] = json.loads(result[i]['workers'])
        team_hist = models.TeamHist.query.filter_by(team_id=result[i]['id'], date=date_to_string(datetime.today())).first()
        if team_hist:
            client_hist = models.TeamClientHistory.query.filter_by(hist_id=team_hist.id).order_by(models.TeamClientHistory.id.desc()).first()
            if client_hist:
                if client_hist.time_end:
                    result[i]['started'] = False
                    result[i]['ended'] = True
                else:
                    result[i]['started'] = True
                    result[i]['ended'] = False
            else:
                result[i]['started'] = True
                result[i]['ended'] = False
        else:
            result[i]['started'] = False
            result[i]['ended'] = False
    return json.dumps(result)


@app.route('/addTeam')
def addTeam():
    data = request.args
    Team = models.Team.query.filter_by(id=int(data['id'])).first()
    Users = models.User.query.all()

    new = False
    if not Team:
        Team = models.Team()
        db.session.add(Team)
        db.session.commit()
        new = True
    Team.name = data['name']
    Team.city = data['city']
    if not Team.workers == str(data['workers']) and not new:
        for user in json.loads(str(data['workers'])):
            if Team.workers:
                try:
                    if user not in json.loads(str(Team.workers)):
                        for i in range(0, len(Users)):
                            if int(Users[i].id) == int(user):
                                Users[i].team_id = str(Team.id)
                except Exception as er:
                    print(er)
            else:
                for i in range(0, len(Users)):
                    if int(Users[i].id) == int(user):
                        Users[i].team_id = str(Team.id)
    Team.workers = str(data['workers'])
    if new:
        db.session.add(Team)
    db.session.commit()

    return 'OK'


@app.route('/getAllReplaces')
def getAllReplaces():
    return table_to_json(models.ReplaceHistory.query.all())


@app.route('/getClientPlants')
def getClientPlants():
    client = models.Client.query.filter_by(name=request.args['client']).first()
    floors = models.Floor.query.filter_by(client_id=client.id).all()
    result = []
    for floor in floors:
        places = models.Place.query.filter_by(floor_id=floor.id).all()
        for place in places:
            service = models.Service.query.filter_by(place_id=place.id).first()
            plants = models.ServicePlant.query.filter_by(service_id=service.id).all()
            for i in range(len(plants)):
                if not plants[i].plant_id:
                    checker = models.Plant()
                    checker.name = plants[i].plant_name
                    db.session.add(checker)
                    db.session.commit()
                    plants[i].plant_id = checker.id

            db.session.commit()
            plants = models.ServicePlant.query.filter_by(service_id=service.id).all()
            for plant in json.loads(table_to_json(plants)):
                plant['place'] = floor.num + ', ' + place.name
                result.append(plant)
    return json.dumps(result)


@app.route('/addTask')
def addTask():
    data = request.args
    team = models.Team.query.filter_by(id=int(data['planteam_id'])).first()

    client_list = models.ClientList.query.filter_by(team_id=team.id).filter_by(date=data['date']).filter_by(
        client=data['planclient']).first()
    if not client_list:
        if not team.workers:
            return 'Client error'
        if len(json.loads(team.workers)) == 1:
            user = models.User.query.filter_by(id=json.loads(team.workers)[0]).first()
            if not user.driver_status:
                return 'Client error'
            else:
                client_list = models.ClientList()
                client_list.date = data['date']
                client_list.client = data['planclient']
                team.client_list.append(client_list)
        else:
            return 'Client error'

    client = models.Client.query.filter_by(name=data['planclient']).first()
    if client:
        client.team_id = int(data['planteam_id'])
    if data['id'] == 'new':
        task = models.Task()
    else:
        task = models.Task.query.filter_by(id=int(data['id'])).first()
    task.date = data['date']
    task.planclient = data['planclient']
    task.planteam_id = data['planteam_id']
    task.done = False
    task.mobile = False
    task.approved = True
    task.type_work = data['type_work']
    if 'approved' in data:
        task.approved = json.loads(data['approved'])
    task.in_process = False
    task_list = models.TaskList()
    task_list.description_id = 3

    db.session.add(task)
    db.session.commit()

    if data['transport_ids']:
        task_list.description_id = 1
        if task.replace:
            task.replace = None
            replace = models.ReplaceHistory.query.filter_by(task_id=int(data['id'])).first()
            if replace:
                db.session.delete(replace)
        new = False
        if not task.transport_ids:
            new = True
            transport = models.TransportHistory()
        else:
            transport = models.TransportHistory.query.filter_by(task_id=int(data['id'])).first()

        task.transport_ids = data['transport_ids']
        transport_info = json.loads(data['transport_ids'])
        transport.date = data['date']
        transport.team_id = int(data['planteam_id'])  # {"id": 1, "done": true, "count": 1}
        transport.client = data['planclient']
        transport.task_id = task.id
        transport.transport_info = json.dumps(transport_info)

        if new:
            transport.checked = False
            db.session.add(transport)

    if data['type_work'] == u'Замена батареек фитостены':
        task_list.description_id = 5
    if data['type_work'] == u'Чистка лотка фитостены':
        task_list.description_id = 6
    if data['type_work'] == u'Профчистка автополива фитостены':
        task_list.description_id = 7

    if task_list.description_id > 4:
        if data['id'] == 'new':
            replace = models.ReplaceHistory()
            replace.task_id = task.id
            replace.type_work = data['type_work']
            replace.client = data['planclient']
            replace.date = data['date']
            replace.team_id = int(data['planteam_id'])
            db.session.add(replace)
        else:
            replace = models.ReplaceHistory.query.filter_by(task_id=task.id).first()
            replace.type_work = data['type_work']
            replace.client = data['planclient']
            replace.date = data['date']
            replace.team_id = int(data['planteam_id'])

        db.session.commit()

    if data['replace'] or data['type_work'] == u'Заменить на фитостене' in data:
        task_list.description_id = 2

        if task.transport_ids:
            task.transport_ids = None
            transport = models.TransportHistory.query.filter_by(task_id=int(data['id'])).first()
            if transport:
                db.session.delete(transport)

        new = False

        if not task.replace:
            new = True
            replace = models.ReplaceHistory()
        else:
            replace = models.ReplaceHistory.query.filter_by(task_id=int(data['id'])).first()

        rep_info = json.loads(data['replace'])
        task.replace = data['replace']
        replace.client = data['planclient']
        replace.date = data['date']
        replace.team_id = int(data[
                                  'planteam_id'])  # {"id": 1, "count": 1, "place":"", "done": true, "replacement": [{"id": 2, "count": 1}]}
        replace.plant_id = int(rep_info['id'])
        replace.plant_count = int(rep_info['count'])
        replace.task_id = task.id
        replace.replace_info = json.dumps(rep_info['replacement'])
        replace.type_work = data['type_work']

        if new:
            replace.checked = False
            db.session.add(replace)

    if data['id'] == 'new':
        db.session.add(task)
        db.session.commit()

    task.task_list = [task_list]

    db.session.commit()
    return 'OK'


@app.route('/addMoreInfoUser')
def addMoreInfoUser():
    user = models.User.query.filter_by(id=request.args['id']).first()
    user.driver_status = bool(json.loads(request.args['driver_status']))
    user.phone = request.args['phone']
    if 'car_info' in request.args:
        user.car_info = request.args['car_info']
    db.session.commit()
    return 'OK'


@app.route('/addUser')
def addUser():
    data = request.args
    team = models.Team.query.filter_by(id=int(data['team_id'])).first()
    User = models.User.query.filter_by(id=int(data['id'])).first()
    new = False
    if not User:
        User = models.User()
        new = True
    User.name = data['name']
    User.role = data['role']
    User.login = data['login']
    User.password = data['password']
    User.city = data['city']
    if team:
        User.team_id = str(data['team_id'])
        if team.workers:
            if not data['id'] in str(team.workers):
                try:
                    buf_array = json.loads(str(team.workers))
                    buf_array.append(int(data['id']))
                    team.workers = json.dumps(buf_array)
                except Exception:
                    team.workers = str(team.workers).replace(']', ', {0}]'.format(int(data['id'])))
        else:
            team.workers = '[{0}]'.format(int(data['id']))
    if 'phone' in data.keys():
        User.phone = data['phone']
    if 'address' in data.keys():
        User.address = data['address']

    if new:
        db.session.add(User)
    db.session.commit()

    return 'OK'


@app.route('/deleteTeam')
def deleteTeam():
    Team = models.Team.query.filter_by(id=int(request.args['id'])).first()
    users = models.User.query

    if Team:
        if Team.leader_id:
            lead = users.filter_by(id=Team.leader_id).first()
            lead.leader_status = False

        users = users.all()

        if Team.workers:
            for i in json.loads(str(Team.workers)):
                for j in range(0, len(users)):
                    if int(users[j].id) == int(i):
                        users[j].team_id = None

        db.session.delete(Team)
        db.session.commit()

    return 'OK'


@app.route('/deleteUser')
def deleteUser():
    User = models.User.query.filter_by(id=int(request.args['id'])).first()
    teams = models.Team.query.all()
    user_stats = models.UserHist.query.filter_by(user_id=User.id).all()
    if User:
        for i in range(0, len(user_stats)):
            db.session.delete(user_stats[i])
        for i in teams:
            if i.workers:
                if str(User.id) in str(i.workers):
                    buf_ar = str(i.workers)
                    buf_ar = json.loads(buf_ar)
                    try:
                        buf_ar.remove(User.id)
                    except Exception:
                        buf_ar.remove(u'{0}'.format(str(User.id)))
                    i.workers = str(buf_ar)
        db.session.delete(User)
        db.session.commit()
    return 'OK'


@app.route('/getClients')
def getClients():
    total = 0
    if 'client' in request.args:
        Clients = models.Client.query.filter_by(name=int(request.args['client'])).all()
        no_city = models.Client.query.filter(models.Client.city.notin_(['Санкт-Петербург', 'Москва'])).filter_by(removed=None).all()
        for i in no_city:
            Clients.append(i)
    elif 'pagination' in request.args:
        Clients = models.Client.query.filter_by(removed=None, city=request.args['city']).all()
        no_city = models.Client.query.filter(models.Client.city.notin_(['Санкт-Петербург', 'Москва'])).filter_by(removed=None).all()
        for i in no_city:
            Clients.append(i)
        return table_to_json(Clients)
    else:
        Clients = models.Client.query.filter_by(removed=None, city=request.args['city']).paginate(page=int(request.args['page']), per_page=100, error_out=True)
        total = Clients.total
        Clients = Clients.items

    Floors = models.Floor.query
    Places = models.Place.query
    Service = models.Service.query
    Plants = models.ServicePlant.query
    clients = json.loads(table_to_json(Clients))
    contacts = models.Contacts.query

    for i in range(0, len(clients)):
        clients[i]['plants'] = []
        floors = Floors.filter_by(client_id=clients[i]['id']).all()
        for floor in floors:
            places = Places.filter_by(floor_id=floor.id).all()
            for place in places:
                service = Service.filter_by(place_id=place.id).first()
                plants = Plants.filter_by(service_id=service.id).all()
                for plant in json.loads(table_to_json(plants)):
                    clients[i]['plants'].append(plant)

        clients[i]['contacts'] = json.loads(table_to_json(contacts.filter_by(client_id=int(clients[i]['id'])).all()))
    return json.dumps({'clients': clients, 'total': total})


@app.route('/checkAutoreport')
def checkAutoreport():
    data = request.args
    client = models.Client.query.filter_by(id=data['id']).first()
    client.autoreport = bool(json.loads(data['status']))

    db.session.commit()
    return 'OK'


@app.route('/getClient')
def getClient():
    Client = models.Client.query.filter_by(id=int(request.args['id'])).first()
    Floors = models.Floor.query
    Places = models.Place.query
    Service = models.Service.query
    Plants = models.ServicePlant.query
    if Client:
        client = json.loads(table_to_json([Client]))[0]
        client['plants'] = []
        client['contacts'] = json.loads(table_to_json(models.Contacts.query.filter_by(client_id=Client.id).all()))
        floors = Floors.filter_by(client_id=client['id']).all()
        for floor in floors:
            places = Places.filter_by(floor_id=floor.id).all()
            for place in places:
                service = Service.filter_by(place_id=place.id).first()
                plants = Plants.filter_by(service_id=service.id).all()
                for i in json.loads(table_to_json(plants)):
                    client['plants'].append(i)

        return json.dumps(client)
    else:
        return 'Bad id'


@app.route('/editClientCords')
def editClientCords():
    client = models.Client.query.filter_by(id=int(request.args['id'])).first()
    if client:
        client.location = request.args['location']
        client.city = request.args['city']
        db.session.commit()
    return 'OK'


@app.route('/updateClientStatus')
def updateClientStatus():
    data = request.args

    client = models.Client.query.filter_by(id=int(data['client_id'])).first()
    client.site_active = data['site_active']
    db.session.commit()

    return 'OK'


@app.route('/addClient')
def addClient():
    data = request.args
    client = models.Client()

    client.name = data['name']
    client.address = data['address']
    client.city = data['city']

    db.session.add(client)
    db.session.commit()

    return 'OK'


@app.route('/addClientComment')
def addClientComment():
    data = request.args
    client = models.Client.query.filter_by(id=data['id']).first()
    if not client:
        return 'bad client id'
    client.comment = data['comment']
    db.session.commit()

    return 'OK'


@app.route('/getClientReports')
def getClientReports():
    client = request.args['id']
    reports = models.Report.query.filter_by(client=client).all()

    return table_to_json(reports)


@app.route('/getClientReport')
def getClientReport():
    client = request.args['client']
    report_id = request.args['id']
    report = models.Report.query.filter_by(client=client, id=report_id).first()
    client = models.Client.query.filter_by(name=client).first()
    contacts = models.Contacts.query.filter_by(client_id=client.id).all()
    images = models.Image.query.filter_by(report_id=report_id).all()
    if report:
        result = json.loads(table_to_json([report]))[0]
        result['report_list'] = json.loads(table_to_json(models.ReportList.query.filter_by(report_id=report.id).all()))
        result['contact'] = []
        result['photos'] = []
        for i in contacts:
            result['contact'].append(i.name)
        for i in images:
            result['photos'].append(i.file_url)
        return json.dumps(result)
    else:
        return 'bad client or id'


@app.route('/getClientReplacements')
def getClientReplacements():
    client = models.Client.query.filter_by(id=int(request.args['id'])).first()
    replacements = models.ReplaceHistory.query.filter_by(client=client.name).filter_by(checked=True).filter_by(
        type_work='Заменить').all()

    return table_to_json(replacements)


@app.route('/addClientReplacement')
def addClientReplacement():
    data = request.args
    if data['id'] != 'new':
        new = False
        replacement = models.TeamReplacement.query.filter_by(id=int(data['id'])).first()
    else:
        replacement = models.TeamReplacement()
        new = True
    replacement.name = data['name']
    replacement.replaced_by = data['replaced_by']
    replacement.client = data['client']
    replacement.date_order = data['date_order']
    replacement.replacement = data['replacement']

    if 'balance' in data.keys():
        replacement.balance = data['balance']
    if 'planned' in data.keys():
        replacement.planned = data['planned']

    if new:
        db.session.add(replacement)
    db.session.commit()

    return 'OK'


@app.route('/getPlants')
def getPlants():
    data = request.args
    plants = models.Plant.query

    if 'filter' in data:
        if 'start' in data:
            result = plants.filter(models.Plant.name.contains(data['filter'])).paginate(page=int(data['start']) / 50,
                                                                                        per_page=50, error_out=True,
                                                                                        max_per_page=50).items
        else:
            result = plants.filter(models.Plant.name.contains(data['filter'])).all()

    else:
        if 'start' in data:
            result = plants.paginate(page=int(data['start']) / 50, per_page=50, error_out=True, max_per_page=50).items
        else:
            result = models.Plant.query.all()

    return table_to_json(result)


@app.route('/getImages')
def getImages():
    return table_to_json(models.Image.query.all())


@app.route('/getOrdersFromTeams')
def getOrdersFromTeams():
    team_orders = models.TeamOrders.query
    images = models.Image.query
    clients = models.Client.query
    result = []
    if '-' not in request.args['date']:
        subresult = json.loads(table_to_json(team_orders.filter_by(date=request.args['date']).all()))
        for i in subresult:
            client = clients.filter_by(name=i['client']).first()
            if client.city == request.args['city']:
                i['photo_list'] = json.loads(table_to_json(images.filter_by(client=i['client'],
                                                                        directory_id=client.report_directory_id,
                                                                        date=request.args['date'],
                                                                        report_id=int(i['id'])).all()))
                result.append(i)

    else:
        result = []
        for date in periodHandler(request.args['date']):
            subres = json.loads(
                table_to_json(team_orders.filter_by(date=date).all()))
            for i in subres:
                client = clients.filter_by(name=i['client']).first()
                if client.city == request.args['city']:
                    i['photo_list'] = json.loads(table_to_json(images.filter_by(client=i['client'],
                                                                            directory_id=client.report_directory_id,
                                                                            date=date, report_id=int(i['id'])).all()))
                    result.append(i)

    return json.dumps(result)


@app.route('/addOrderFromTeam')
def addOrderFromTeam():
    order = models.TeamOrders()
    date = datetime.today()
    data = request.args
    order.date = date_to_string(date)
    order.name = data['name']
    order.count = data['from_count']
    client = models.Client.query.filter_by(id=int(data['client'])).first()
    order.client = client.name
    order.reason = data['reason']
    order.city = data['city']
    if 'comment' in data:
        order.comment = data['comment']
    order.team_id = data['team_id']

    db.session.add(order)

    task = models.Task()
    task.approved = True
    task.mobile = True
    task.planclient = client.name
    task.done = False
    rep_info = {'id': int(data['from_id']), 'count': int(data['from_count']),
                               'place': data['place'], 'done': False,
                               'replacement': [{'id': int(data['to_id']), 'count': int(data['to_count'])}]}
    task.replace = json.dumps(rep_info)
    task.type_work = 'Заменить'
    task.in_process = False
    task_list = models.TaskList()
    task_list.description_id = 2
    task.task_list = [task_list]

    db.session.add(task)
    db.session.commit()
    replace = models.ReplaceHistory()

    replace.client = client.name
    replace.plant_id = int(rep_info['id'])
    replace.plant_count = int(rep_info['count'])
    replace.task_id = task.id
    replace.checked = True
    replace.replace_info = json.dumps(rep_info['replacement'])

    db.session.add(replace)
    db.session.commit()

    return str(order.id)


@app.route('/deleteClientReplacement')
def deleteClientReplacement():
    replacement = models.TeamReplacement.query.filter_by(id=request.args['id']).first()
    db.session.delete(replacement)
    db.session.commit()

    return 'OK'


@app.route('/getClientPhyto')
def getClientPhyto():
    client = request.args['client']
    phytowall_id = request.args['id']
    phytowall = models.Phytowall.query.filter_by(client=client, id=phytowall_id).first()
    if phytowall:
        return table_to_json([phytowall])
    else:
        return 'bad client or id'


@app.route('/getAllClaims')
def getAllClaims():
    claims = models.Claim.query
    if '-' in request.args['date']:
        period = periodHandler(request.args['date'])
        result = []
        for i in period:
            subres = claims
            subres = subres.filter_by(date=i)
            if 'team' in request.args:
                subres = subres.filter_by(team_id=request.args['team'])
            if 'sender' in request.args:
                subres = subres.filter_by(sender=request.args['sender'])
            if 'character' in request.args:
                subres = subres.filter(models.Claim.character.contains(request.args['character']))
            if str(subres.all()) != '[]':
                for j in json.loads(table_to_json(subres.all())):
                    client = models.Client.query.filter_by(id=j['client']).first()
                    if client.city == request.args['city']:
                        result.append(j)
        return json.dumps(result)
    else:
        if 'date' in request.args:
            claims = claims.filter_by(date=request.args['date'])
        if 'team' in request.args:
            claims = claims.filter_by(team_id=request.args['team'])
        if 'sender' in request.args:
            claims = claims.filter_by(sender=request.args['sender'])
        if 'character' in request.args:
            claims = claims.filter(models.Claim.character.contains(request.args['character']))

        result = []
        for j in json.loads(table_to_json(claims.all())):
            client = models.Client.query.filter_by(id=j['client']).first()
            if client.city == request.args['city']:
                result.append(j)

        return json.dumps(result)


@app.route('/getClientClaims')
def getClientClaims():
    claims = models.Claim.query.filter_by(client=int(request.args['id']))
    if '-' in request.args['date']:
        period = periodHandler(request.args['date'])
        result = []
        for i in period:
            subres = claims
            subres = subres.filter_by(date=i)
            if 'sender' in request.args:
                subres = subres.filter_by(sender=request.args['sender'])
            if 'character' in request.args:
                subres = subres.filter(models.Claim.character.contains(request.args['character']))
            if str(subres.all()) != '[]':
                for j in json.loads(table_to_json(subres.all())):
                    result.append(j)
        return json.dumps(result)
    else:
        if 'date' in request.args:
            claims = claims.filter_by(date=request.args['date'])
        if 'sender' in request.args:
            claims = claims.filter_by(sender=request.args['sender'])
        if 'character' in request.args:
            claims = claims.filter(models.Claim.character.contains(request.args['character']))
        return table_to_json(claims.all())


@app.route('/getClientClaim')
def getClientClaim():
    claim = models.Claim.query.filter_by(client=int(request.args['client'])).first()
    if claim:
        return table_to_json([claim])
    else:
        return 'bad client or id'


@app.route('/removeReports')
def removeReports():
    data = json.loads(request.args["ids"])
    for i in data:
        report = models.Report.query.filter_by(id=i).first()
        db.session.delete(report)

    db.session.commit()
    return 'OK'


@app.route('/getTaskLists')
def getTaskLists():
    return table_to_json(models.TaskList.query.all())


@app.route('/sendPhotoReplace', methods=['POST'])
def sendPhotoReplace():
    check_token_update()
    date = date_to_string(datetime.today())
    file = request.data.decode('utf-8')

    counter = len(models.Image.query.filter_by(date=date).all())
    id_client = request.headers['Client']
    client = models.Client.query.filter_by(id=int(id_client)).first()
    client_name = client.name
    replace_directory_id = client.replace_directory_id

    if not replace_directory_id:
        client.replace_directory_id = file_handler.createDirectory(directory_id=47211, client_name=client.id,
                                                                   token=bitrix.token)

    image = models.Image()
    image.date = date
    image.filename = date.replace('.', '') + '_' + str(client.replace_directory_id) + str(counter) + '.jpg'
    image.directory_id = client.replace_directory_id
    image.client = client_name
    image.file_url = file_handler.sendPhoto(token=bitrix.token, file=file, filename=image.filename,
                                            directory_id=client.replace_directory_id)
    db.session.add(image)

    db.session.commit()
    return 'OK'


@app.route('/removeClient', methods=['DELETE'])
def removeClient():
    client_id = int(request.args['id'])
    client = models.Client.query.filter_by(id=client_id).first()
    client.removed = 'true'
    reg_tasks = models.Task.query.filter_by(planclient=client.name).all()
    for i in reg_tasks:
        db.session.delete(i)

    etalon_tasks = models.EtalonGant.query.filter_by(planclient=client.name).all()
    for i in etalon_tasks:
        db.session.delete(i)

    gant_tasks = models.GantTask.query.filter_by(planclient=client.name).all()
    for i in gant_tasks:
        db.session.delete(i)

    db.session.commit()

    return 'OK'


@app.route('/sendPhotoReport', methods=['POST'])
def sendPhotoReport():
    check_token_update()
    date = date_to_string(datetime.today())
    file = request.data.decode('utf-8')

    counter = len(models.Image.query.filter_by(date=date).all())
    id_client = int(request.headers['Client'])
    report_id = request.headers['Report_id']
    client = models.Client.query.filter_by(id=id_client).first()
    client_name = client.name
    report_directory_id = client.report_directory_id

    if not report_directory_id:
        client.report_directory_id = file_handler.createDirectory(directory_id=47214, client_name=client.id,
                                                                  token=bitrix.token)

    image = models.Image()
    image.date = date
    image.report_id = int(report_id)
    image.type = 'Причина замены'
    image.filename = date.replace('.', '') + '_' + str(client.report_directory_id) + str(counter) + '.jpg'
    image.directory_id = client.report_directory_id
    image.client = client_name
    image.file_url = file_handler.sendPhoto(token=bitrix.token, file=file, filename=image.filename,
                                            directory_id=client.report_directory_id)
    db.session.add(image)

    db.session.commit()
    return 'OK'


def loadFromExcel():
    wb = openpyxl.load_workbook(os.path.abspath(os.path.dirname(__file__) + '/files/buffer.xlsx'), read_only=True,
                                data_only=True)
    sheet = wb['Plant Location Scheme']

    column_counter = 4
    service_plant_query = models.ServicePlant.query
    floor_query = models.Floor.query
    place_query = models.Place.query

    place_buffer = ''
    floor_buffer = ''
    client_buffer = '<3 свою работу'
    client_query = models.Client.query
    cid = 0
    while sheet['A' + str(column_counter)].value != 'Итого':
        if client_buffer != sheet['A' + str(column_counter)].value:
            client_buffer = sheet['A' + str(column_counter)].value
            client = client_query.filter_by(name=sheet['A' + str(column_counter)].value).first()
            if client:
                client.verification = True
                cid = client.id
            else:
                client = models.Client()
                client.name = client_buffer = sheet['A' + str(column_counter)].value
                client.verification = True
                db.session.add(client)
                db.session.commit()

                cid = client.id

        if place_buffer != sheet['C' + str(column_counter)].value:
            place_buffer = sheet['C' + str(column_counter)].value
        if floor_buffer != sheet['B' + str(column_counter)].value:
            floor_buffer = sheet['B' + str(column_counter)].value
        container_buffer = sheet['E' + str(column_counter)].value
        plant_buffer = sheet['G' + str(column_counter)].value
        floor = floor_query.filter_by(client_id=cid, num=floor_buffer).first()
        if floor:
            place = place_query.filter_by(floor_id=floor.id, name=place_buffer).first()
            if place:
                service = models.Service.query.filter_by(place_id=place.id).first()
                if plant_buffer:
                    plant = service_plant_query.filter_by(plant_name=plant_buffer, service_id=service.id).first()
                    if plant:
                        plant.plant_count = int(sheet['F' + str(column_counter)].value)
                        plant.plant_type = 'flower'
                        if 'гарантией' in sheet['H' + str(column_counter)].value:
                            plant.plant_guarantee = True
                        else:
                            plant.plant_guarantee = False
                    else:
                        plant = models.ServicePlant()
                        plant.plant_name = plant_buffer
                        plant.plant_count = int(sheet['F' + str(column_counter)].value)
                        plant.plant_type = 'flower'
                        service.plants.append(plant)
                        if 'гарантией' in sheet['H' + str(column_counter)].value:
                            plant.plant_guarantee = True
                        else:
                            plant.plant_guarantee = False
                if container_buffer:
                    plant1 = service_plant_query.filter_by(plant_name=container_buffer.replace('Композиция', ''), service_id=service.id).first()
                    if plant1:
                        plant1.plant_count = 1
                        plant1.plant_type = 'circle'
                        if 'гарантией' in sheet['H' + str(column_counter)].value:
                            plant1.plant_guarantee = True
                        else:
                            plant1.plant_guarantee = False
                    else:
                        plant1 = models.ServicePlant()
                        plant1.plant_name = container_buffer.replace('Композиция', '')
                        plant1.plant_count = 1
                        plant1.plant_type = 'circle'
                        if 'гарантией' in sheet['H' + str(column_counter)].value:
                            plant1.plant_guarantee = True
                        else:
                            plant1.plant_guarantee = False
                        service.plants.append(plant1)

            else:
                place = models.Place()
                place.name = place_buffer

                service = models.Service()
                if plant_buffer:
                    plant = models.ServicePlant()
                    plant.plant_name = plant_buffer
                    plant.plant_count = int(sheet['F' + str(column_counter)].value)
                    plant.plant_type = 'flower'
                    if 'гарантией' in sheet['H' + str(column_counter)].value:
                        plant.plant_guarantee = True
                    else:
                        plant.plant_guarantee = False
                    service.plants.append(plant)

                if container_buffer:
                    plant1 = models.ServicePlant()
                    plant1.plant_name = container_buffer.replace('Композиция', '')
                    plant1.plant_count = 1
                    plant1.plant_type = 'circle'
                    if 'гарантией' in sheet['H' + str(column_counter)].value:
                        plant1.plant_guarantee = True
                    else:
                        plant1.plant_guarantee = False
                    service.plants.append(plant1)

                place.service.append(service)
                floor.place_list.append(place)

        else:
            floor = models.Floor()
            floor.num = floor_buffer
            floor.client_id = cid

            place = models.Place()
            place.name = place_buffer

            service = models.Service()
            if plant_buffer:
                plant = models.ServicePlant()
                plant.plant_name = plant_buffer
                plant.plant_count = int(sheet['F' + str(column_counter)].value)
                plant.plant_type = 'flower'
                if 'гарантией' in sheet['H' + str(column_counter)].value:
                    plant.plant_guarantee = True
                else:
                    plant.plant_guarantee = False
                service.plants.append(plant)

            if container_buffer:
                plant1 = models.ServicePlant()
                plant1.plant_name = container_buffer.replace('Композиция', '')
                plant1.plant_count = 1
                plant1.plant_type = 'circle'
                if 'гарантией' in sheet['H' + str(column_counter)].value:
                    plant1.plant_guarantee = True
                else:
                    plant1.plant_guarantee = False
                service.plants.append(plant1)

            place.service.append(service)
            floor.place_list.append(place)

            db.session.add(floor)

        column_counter += 1
        db.session.commit()


@app.route('/sendMobilePhoto', methods=['POST'])
def sendMobilePhoto():
    check_token_update()
    date = date_to_string(datetime.today())
    file = request.data.decode('utf-8')

    counter = len(models.Image.query.filter_by(date=date).all())
    id_client = int(request.headers['Client'])
    client = models.Client.query.filter_by(id=id_client).first()
    client_name = client.name
    photofix_directory_id = client.photofix_directory_id

    if not photofix_directory_id:
        client.photofix_directory_id = file_handler.createDirectory(directory_id=47212, client_name=client.id,
                                                                    token=bitrix.token)

    image = models.Image()
    image.date = date
    image.filename = date.replace('.', '') + '_' + str(client.photofix_directory_id) + str(counter) + '.jpg'
    image.directory_id = client.photofix_directory_id
    image.client = client_name
    image.file_url = file_handler.sendPhoto(token=bitrix.token, file=file, filename=image.filename,
                                            directory_id=client.photofix_directory_id)
    db.session.add(image)

    db.session.commit()
    return 'OK'


@app.route('/sendExcel', methods=['POST'])
def sendExcel():
    file = request.files['file']
    file.save(os.path.abspath(os.path.dirname(__file__) + '/files/buffer.xlsx'))

    loadFromExcel()

    return 'OK'


@app.route('/sendWebPhoto', methods=['POST'])
def sendWebPhoto():
    check_token_update()
    date = date_to_string(datetime.today())
    counter = len(models.Image.query.filter_by(date=date).all())
    client = models.Client.query.filter_by(name=recode(request.form['client_name'])).first()
    phytowall_directory_id = client.phytowall_directory_id

    if not phytowall_directory_id:
        client.phytowall_directory_id = file_handler.createDirectory(directory_id=47213, client_name=client.id,
                                                                     token=bitrix.token)

    for i in request.files:
        image = models.Image()
        image.date = date
        file = request.files[i]
        image.filename = date.replace('.', '') + '_' + str(client.phytowall_directory_id) + str(counter) + '.' + \
                         file.filename.split('.')[len(file.filename.split('.')) - 1]
        image.directory_id = client.phytowall_directory_id
        image.client = request.form['client_name']
        image.file_url = file_handler.sendPhoto(token=bitrix.token, file=file_handler.bitrixBinary(file),
                                                filename=image.filename, directory_id=client.phytowall_directory_id)
        db.session.add(image)
        counter += 1

    db.session.commit()
    return 'OK'


@app.route('/getClientPhoto')
def getClientPhoto():
    photos = models.Image.query.filter_by(client=request.args['client']).all()
    return table_to_json(photos)


@app.route('/addClientClaim')
def addClientClaim():
    data = request.args

    if data['id'] != 'new':
        new = False
        claim = models.Claim.query.filter_by(id=int(data['id'])).first()
    else:
        claim = models.Claim()
        new = True

    claim.client = int(data['client'])
    claim.character = data['character']
    claim.client_title = data['client_title']
    claim.description = data['description']
    claim.sender = data['sender']
    claim.done = data['done']
    claim.date = data['date']

    if 'comment' in data.keys():
        claim.comment = data['comment']

    claim.team_id = data['team_id']

    if new:
        db.session.add(claim)
    db.session.commit()

    return 'OK'


@app.route('/deleteClientClaim')
def deleteClientClaim():
    claim = models.Claim.query.filter_by(id=int(request.args['id'])).first()
    if claim:
        db.session.delete(claim)
        db.session.commit()
    return 'OK'


@app.route('/getReports')
def getReports():
    checked = models.Report.query.filter_by(checked=True).all()
    unchecked = models.Report.query.filter_by(checked=False).all()

    check_res = []
    uncheck_res = []
    teams = models.Team.query
    for i in checked:
        team = teams.filter_by(id=i.team_id).first()
        if team:
            if team.city == request.args['city']:
                check_res.append(i)
        else:
            client = models.Client.query.filter_by(name=i.client).first()
            if client.city == request.args['city']:
                check_res.append(i)
    for i in unchecked:
        team = teams.filter_by(id=i.team_id).first()
        if team:
            if team.city == request.args['city']:
                uncheck_res.append(i)
        else:
            client = models.Client.query.filter_by(name=i.client).first()
            if client.city == request.args['city']:
                uncheck_res.append(i)
    result = {'checked': json.loads(table_to_json(check_res)), 'unchecked': json.loads(table_to_json(uncheck_res))}
    return json.dumps(result)


@app.route('/commentReport')
def commentReport():
    data = request.args
    report = models.Report.query.filter_by(id=int(data['id'])).first()

    report.comment = data['comment']
    report.date = data['date']

    db.session.commit()
    return 'OK'


def join(arr, sep):
    result = str(arr[0])

    for i in range(1, len(arr)):
        result += (sep + str(arr[i]))

    return result


@app.route('/getPlantHistory')
def getPlantHistory():
    history = models.PlantHistory.query.filter_by(service_id=int(request.args['service_id'])).all()
    return table_to_json(history)


@app.route('/checkReport')
def checkReport():
    reports = models.Report.query
    ids = json.loads(request.args['ids'])

    for i in ids:
        reports.filter_by(id=int(i)).first().checked = True
        report = models.Report.query.filter_by(id=i).first()
        if report:
            result = json.loads(table_to_json([report]))[0]

            if not result['service']:
                result['service'] = 'Ничего не найдено!'
            else:
                result['service'] = ''
                try:
                    for k in json.loads(report.service):
                        result['service'] += (k + ', ')
                    result['service'] = result['service'][:-2]

                except Exception:
                    result['service'] = report.service
            if not result['additional']:
                result['additional'] = 'Ничего не указано!'
            if json.loads(result['replace']):
                result['replace'] = join(json.loads(result['replace']), ', ')
            else:
                result['replace'] = ''
            team = models.Team.query.filter_by(id=result['team_id']).first()
            workers_id = json.loads(team.workers)
            workers = []
            users = models.User.query
            for j in workers_id:
                workers.append(users.filter_by(id=j).first().name)
            photos = models.Image.query.filter_by(report_id=report.id).all()
            photo_arr = []
            for i in photos:
                photo_arr.append(i.file_url)
            if photo_arr:
                photos = join(photo_arr, ', ')
            else:
                photos = ''

            client = models.Client.query.filter_by(name=result['client']).first()
            contact = models.Contacts.query.filter_by(client_id=client.id).filter(models.Contacts.name.id_(result['contact'])).first()
            if contact:
                if contact.email:
                    contact_name = contact.name
                    if len(contact.name.split(' ')) == 2:
                        contact_name = contact.name.split(' ')[0]

                    elif len(contact.name.split(' ')) == 3:
                        contact_name = contact.name.split(' ')[0] + ' ' + \
                                       contact.name.split(' ')[1]
                    exchange_handler.send_message(email_content=render_template('mail.html',
                                                                                client_name=result['client'],
                                                                                date=result['date'],
                                                                                work_list=result['service'],
                                                                                replace=result['replace'],
                                                                                additional=result['additional'],
                                                                                photos=photos,
                                                                                team=team.name,
                                                                                workers=join(workers, ', '),
                                                                                contact=contact_name),
                                                  email=contact.email)

    db.session.commit()
    return 'OK'


@app.route('/changeService')
def changeService():
    client = models.Client.query.filter_by(id=int(request.args['id'])).first()
    if not client:
        return 'bad client id'

    prev_date = client.end_service
    client.end_service = request.args['date']

    etalon = models.EtalonGant.query.filter_by(planclient=client.name).all()
    if str_to_date(prev_date) > str_to_date(request.args['date']):
        for i in etalon:
            gant = models.GantTask.query.filter_by(etalon_id=i.id).all()
            for j in range(len(gant)):
                if str_to_date(gant[j].date) > str_to_date(request.args['date']):
                    task = models.Task.query.filter_by(gant_id=gant[j].id).all()
                    for k in range(len(task)):
                        db.session.delete(task[k])
                    db.session.delete(gant[j])
        db.session.commit()

    elif str_to_date(prev_date) < str_to_date(request.args['date']):
        two_weeks = timedelta(weeks=2)
        for i in etalon:
            gant = models.GantTask.query.filter_by(etalon_id=i.id).all()
            task_flag = False
            for j in range(len(gant)):
                if not task_flag:
                    task_flag = True
                    task_array = models.Task.query.filter_by(gant_id=gant[j].id).all()
                date_now = str_to_date(gant.date)
            date_end = str_to_date(request.args['date'])
            while date_now <= date_end:
                date_now += two_weeks
                for j in task_array:
                    j.date = date_now
                    db.session.add(j)

        db.session.commit()

    return 'OK'


@app.route('/getWeek')
def getWeek():
    week = models.Week.query.first()
    if not week:
        week = models.Week()
        week.week = '1'
        db.session.add(week)
        db.session.commit()
        return '1'
    else:
        print(table_to_json([week]))
        return str(week.week)


@app.route('/getReport')
def getReport():
    report = models.Report.query.filter_by(id=int(request.args['id'])).first()
    result = json.loads(table_to_json([report]))[0]

    result['report_list'] = json.loads(table_to_json(models.ReportList.query.filter_by(report_id=report.id).all()))

    return json.dumps(result)


def getContact(deal_id):
    url = 'https://crm.terrakultur.ru/rest/{0}?access_token={1}&id={2}'.format('crm.deal.contact.items.get',
                                                                               bitrix.token, deal_id)
    r = requests.get(url)
    result = []
    r = json.loads(r.content.decode('utf-8'))
    if 'error' not in r:
        for i in r['result']:
            url = 'https://crm.terrakultur.ru/rest/{0}?access_token={1}&id={2}'.format('crm.contact.get', bitrix.token,
                                                                                       i['CONTACT_ID'])
            req = requests.get(url)
            result.append(json.loads(req.content.decode('utf-8'))['result'])
    return result


def load_client_service(file_id, cid):
    url = 'https://crm.terrakultur.ru/rest/{0}?access_token={1}&id={2}'.format('disk.file.get', token, file_id)
    r = requests.get(url)
    try:
        url = r.json()['result']['DOWNLOAD_URL']
    except Exception:
        return 0
    r = requests.get(url)
    with open(os.path.abspath(os.path.dirname(__file__) + '/files/{0}.xlsm'.format(cid)), 'wb') as file:
        file.write(r.content)

    try:
        wb = openpyxl.load_workbook(os.path.abspath(os.path.dirname(__file__) + '/files/{0}.xlsm'.format(cid)), read_only=True,
                                    data_only=True)
    except Exception:
        return -1

    try:
        if 'For service' in wb:
            sheet = wb['For service']
        elif 'Plant Location Scheme' in wb:
            sheet = wb['Plant Location Scheme']
        else:
            print('bad sheet')
            return -1

    except Exception:
        print('bad sheet with error')
        return -1

    column_counter = 4
    service_plant_query = models.ServicePlant.query
    floor_query = models.Floor.query
    place_query = models.Place.query

    place_buffer = ''
    floor_buffer = ''
    while sheet['A' + str(column_counter)].value.lower() != 'итого':
        if place_buffer != sheet['C' + str(column_counter)].value:
            place_buffer = sheet['C' + str(column_counter)].value
        if floor_buffer != sheet['B' + str(column_counter)].value:
            floor_buffer = sheet['B' + str(column_counter)].value
        container_buffer = sheet['E' + str(column_counter)].value
        plant_buffer = sheet['G' + str(column_counter)].value
        floor = floor_query.filter_by(client_id=cid, num=floor_buffer).first()
        if floor:
            place = place_query.filter_by(floor_id=floor.id, name=place_buffer).first()
            if place:
                service = models.Service.query.filter_by(place_id=place.id).first()
                if plant_buffer:
                    plant = service_plant_query.filter_by(plant_name=plant_buffer, service_id=service.id).first()
                    if plant:
                        plant.plant_count = int(sheet['F' + str(column_counter)].value)
                        plant.plant_type = 'flower'
                        if 'гарантией' in sheet['H' + str(column_counter)].value:
                            plant.plant_guarantee = True
                        else:
                            plant.plant_guarantee = False
                    else:
                        plant = models.ServicePlant()
                        plant.plant_name = plant_buffer
                        plant.plant_count = int(sheet['F' + str(column_counter)].value)
                        plant.plant_type = 'flower'
                        if sheet['I' + str(column_counter)].value.lower() == 'да':
                            plant.plant_client = True
                        else:
                            plant.plant_client = False

                        service.plants.append(plant)
                        if 'гарантией' in sheet['H' + str(column_counter)].value:
                            plant.plant_guarantee = True
                        else:
                            plant.plant_guarantee = False
                if container_buffer:
                    plant1 = service_plant_query.filter_by(plant_name=container_buffer.replace('Композиция', ''),
                                                           service_id=service.id).first()
                    if plant1:
                        plant1.plant_count = 1
                        plant1.plant_type = 'circle'
                        if 'гарантией' in sheet['H' + str(column_counter)].value:
                            plant1.plant_guarantee = True
                        else:
                            plant1.plant_guarantee = False
                    else:
                        plant1 = models.ServicePlant()
                        plant1.plant_name = container_buffer.replace('Композиция', '')
                        plant1.plant_count = 1
                        plant1.plant_type = 'circle'
                        if sheet['I' + str(column_counter)].value.lower() == 'да':
                            plant1.plant_client = True
                        else:
                            plant1.plant_client = False
                        if 'гарантией' in sheet['H' + str(column_counter)].value:
                            plant1.plant_guarantee = True
                        else:
                            plant1.plant_guarantee = False
                        service.plants.append(plant1)

            else:
                place = models.Place()
                place.name = place_buffer

                service = models.Service()
                if plant_buffer:
                    plant = models.ServicePlant()
                    plant.plant_name = plant_buffer
                    plant.plant_count = int(sheet['F' + str(column_counter)].value)
                    plant.plant_type = 'flower'
                    if sheet['I' + str(column_counter)].value.lower() == 'да':
                        plant.plant_client = True
                    else:
                        plant.plant_client = False
                    if 'гарантией' in sheet['H' + str(column_counter)].value:
                        plant.plant_guarantee = True
                    else:
                        plant.plant_guarantee = False
                    service.plants.append(plant)

                if container_buffer:
                    plant1 = models.ServicePlant()
                    plant1.plant_name = container_buffer.replace('Композиция', '')
                    plant1.plant_count = 1
                    plant1.plant_type = 'circle'
                    if sheet['I' + str(column_counter)].value.lower() == 'да':
                        plant1.plant_client = True
                    else:
                        plant1.plant_client = False
                    if 'гарантией' in sheet['H' + str(column_counter)].value:
                        plant1.plant_guarantee = True
                    else:
                        plant1.plant_guarantee = False
                    service.plants.append(plant1)

                place.service.append(service)
                floor.place_list.append(place)

        else:
            floor = models.Floor()
            floor.num = floor_buffer
            floor.client_id = cid

            place = models.Place()
            place.name = place_buffer

            service = models.Service()
            if plant_buffer:
                plant = models.ServicePlant()
                plant.plant_name = plant_buffer
                plant.plant_count = int(sheet['F' + str(column_counter)].value)
                plant.plant_type = 'flower'
                if sheet['I' + str(column_counter)].value.lower() == 'да':
                    plant.plant_client = True
                else:
                    plant.plant_client = False
                if 'гарантией' in sheet['H' + str(column_counter)].value:
                    plant.plant_guarantee = True
                else:
                    plant.plant_guarantee = False
                service.plants.append(plant)

            if container_buffer:
                plant1 = models.ServicePlant()
                plant1.plant_name = container_buffer.replace('Композиция', '')
                plant1.plant_count = 1
                plant1.plant_type = 'circle'
                if sheet['I' + str(column_counter)].value.lower() == 'да':
                    plant1.plant_client = True
                else:
                    plant1.plant_client = False
                if 'гарантией' in sheet['H' + str(column_counter)].value:
                    plant1.plant_guarantee = True
                else:
                    plant1.plant_guarantee = False
                service.plants.append(plant1)

            place.service.append(service)
            floor.place_list.append(place)

            db.session.add(floor)

        column_counter += 1
        db.session.commit()


@app.route('/bitrixSync')
def bitrixSync():
    check_token_update()
    refreshBitrix()
    return 'OK'


def getContactsByID(id_array):
    result = []
    if id_array:
        for i in id_array:
            if i.isdigit():
                url = 'https://crm.terrakultur.ru/rest/{0}?access_token={1}&id={2}'.format('crm.contact.get', bitrix.token, i)
                req = requests.get(url)
                result.append(json.loads(req.content.decode('utf-8'))['result'])
            else:
                result.append({'NAME': i, 'SECOND_NAME': None, 'ADDRESS': None, 'HAS_EMAIL': 'N', 'HAS_PHONE': 'N'})
    return result


def refreshBitrix():
    client_info = []
    client_buffer = []
    headers = {
        'Content-Type': 'application/json'
    }

    method_folder = 'crm.deal.list'

    next = 0
    clients = models.Client.query
    while True:
        filt = json.dumps({'filter': {'=CATEGORY_ID': '1', '=STATUS_ID': 'C3:PREPAYMENT_INVOICE'},
                           'select': ['COMPANY_ID', 'UF_CRM_1593170402072', 'UF_CRM_1564388438556', 'UF_CRM_1560069180',
                                      'UF_CRM_1560068886', 'TITLE', 'COMMENTS', 'ID', 'UF_CRM_1596974594368', 'UF_CRM_1564388771',
                                      'UF_CRM_1564388294551'], 'start': next})
        url = 'https://crm.terrakultur.ru/rest/{0}?access_token={1}'.format(method_folder, bitrix.token)
        r = requests.post(url, headers=headers, data=filt)
        client_buffer.append(json.loads(r.content.decode('utf-8'))['result'])
        if 'next' in json.loads(r.content.decode('utf-8')):
            next = json.loads(r.content.decode('utf-8'))['next']
        else:
            break
    for row in client_buffer:
        for client in row:
            client_info.append(client)
    for i in client_info:
        if i['UF_CRM_1596974594368'] and i['UF_CRM_1596974594368'] != 'None':
            load_client_service(file_id=i['UF_CRM_1596974594368'], cid=i['ID'])
        new_client = False
        client = clients.filter_by(id=int(i['ID'])).first()
        if not client:
            new_client = True
            client = models.Client()
            client.id = int(i['ID'])
        client.name = i['TITLE'].replace('&', '-')

        if i['UF_CRM_1560069180']:
            if client.address != i['UF_CRM_1560069180'].split('|')[0]:
                client.location = None
            client.address = i['UF_CRM_1560069180'].split('|')[0]
            if 'москва' in i['UF_CRM_1560069180'].lower():
                client.city = 'Москва'
            elif 'санкт-петербург' in i['UF_CRM_1560069180'].lower():
                client.city = 'Санкт-Петербург'

        client.quantity = i['UF_CRM_1593170402072']
        client.comment = i['COMMENTS']
        client.containers = i['UF_CRM_1560068886']
        client.status = -1
        if i['UF_CRM_1564388294551']:
            if int(i['UF_CRM_1564388294551']) == 750:
                client.service_area = 'Сервис с гарантией'

            if int(i['UF_CRM_1564388294551']) == 751:
                client.service_area = 'Сервис без гарантии'

            if int(i['UF_CRM_1564388294551']) == 752:
                client.service_area = 'Сервис с частичной гарантией'

            if int(i['UF_CRM_1564388294551']) == 1326:
                client.service_area = 'Сервиса нет'
        else:
            client.service_area = 'Сервиса нет'

        client.link = 'https://crm.terrakultur.ru/crm/deal/details/' + str(i['ID'] + '/')
        if not new_client:
            del_contacts = models.Contacts.query.filter_by(client_id=client.id).all()
            for j in range(len(del_contacts)):
                db.session.delete(del_contacts[j])
        for j in getContactsByID(i['UF_CRM_1564388771']):
            contacts = models.Contacts()
            if j['NAME'] and j['SECOND_NAME']:
                contacts.name = j['NAME'] + ' ' + j['SECOND_NAME']
            elif j['NAME']:
                contacts.name = j['NAME']
            else:
                contacts.name = 'Без имени'

            contacts.address = j['ADDRESS']
            if j['HAS_EMAIL'] == 'Y':
                contacts.email = j['EMAIL'][0]['VALUE']
            if j['HAS_PHONE'] == 'Y':
                contacts.phone = j['PHONE'][0]['VALUE']

            contacts.client_id = client.id

            db.session.add(contacts)
        if new_client:
            db.session.add(client)
    db.session.commit()
    print('commited')


def getMonday(date):
    delta = timedelta(days=1)
    if date.weekday() == 0:
        return date_to_string(date)

    else:
        while date.weekday() != 0:
            date -= delta
    return date_to_string(date)


def buildGant():
    date = datetime.today()
    week = models.Week.query.first()
    if not week:
        week = models.Week()
        week.week = 1
        db.session.add(week)
        db.session.commit()

    if week.last_date != getMonday(date):
        if week.week == 1:
            week.week = 2
        else:
            week.week = 1
        week.last_date = getMonday(date)
        db.session.commit()


s = sched.scheduler(time0.time, time0.sleep)


def updater():
    check_token_update()
    refreshBitrix()
    buildGant()
    print('update succeed')

    now = datetime.now()
    secs = ((now + timedelta(days=1) - timedelta(hours=now.hour, minutes=now.minute)) - now).seconds
    s.enter((60 * 60 * 24) + secs, 0, updater)
    s.run()


thread = Thread(target=updater)
thread.start()


def addCities():
    for i in models.Team.query.all():
        if 'СПб' in i.name:
            i.city = 'Санкт-Петербург'
            if i.workers:
                for j in json.loads(i.workers):
                    user = models.User.query.filter_by(id=int(j)).first()
                    user.city = 'Санкт-Петербург'
        else:
            i.city = 'Москва'
            if i.workers:
                for j in json.loads(i.workers):
                    user = models.User.query.filter_by(id=int(j)).first()
                    user.city = 'Москва'


def delete_copy():
    contacts = models.Contacts.query.all()
    copy_list = []
    print('delete start')
    for i in range(len(contacts)):
        if {'name': contacts[i].name, 'client_id': contacts[i].client_id} not in copy_list:
            copy_list.append({'name': contacts[i].name, 'client_id': contacts[i].client_id})
        else:
            db.session.delete(contacts[i])
    db.session.commit()
    print('delete end')


def delete_contacts():
    contacts = models.Contacts.query.all()
    for i in range(len(contacts)):
        db.session.delete(contacts[i])
    db.session.commit()
    print('READY')


@app.route('/getClientLists')
def getClientLists():
    return table_to_json(models.ClientList.query.all())


@app.route('/addNovosibirsk')
def addNovosibirsk():
    client0 = models.Client()
    client1 = models.Client()
    client0.city = "Новосибирск"
    client1.city = "Новосибирск"
    client0.name = "Новосибирск тест 1"
    client1.name = "Новосибирск тест 2"
    client0.address = "улица Восход, 20, Новосибирск"
    client1.address = "улица Тимирязева, 97, Новосибирск"

    db.session.add(client0)
    db.session.add(client1)
    db.session.commit()

    return 'OK'


@app.route('/getClientHist')
def getClientHist():
    data = request.args

    db.session.commit()
    team_hist = models.TeamHist.query.filter_by(team_id=int(data['team_id'])).filter_by(date=data['date']).first()
    client_hist = models.TeamClientHistory.query.filter_by(hist_id=team_hist.id).filter_by(client_name=data['client_name']).all()

    return table_to_json(client_hist)


@app.route('/deleteClient')
def deleteClient():
    id = int(request.args['id'])
    client = models.Client.query.filter_by(id=id).first()

    db.session.delete(client)
    db.session.commit()


@app.route('/fixNotDoneTasks')
def fixNotDoneTasks():
    tasks = models.GantTask.query.all()
    now = datetime.today()
    for i in range(len(tasks)):
        if str_to_date(tasks[i].date) > now:
            tasks[i].done = False
    db.session.commit()
    return 'OK'
