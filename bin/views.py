from datetime import datetime

from aiohttp import web
from sqlalchemy.exc import IntegrityError

import db


async def get_limits(request):
    async with request.app['db'].acquire() as conn:
        cursor = await conn.execute(db.limit.select(db.limit.c.client_id == int(request.query['id'])))
        records = await cursor.fetchall()
        limits = [dict(q) for q in records]

        return web.json_response({'success': True, 'data': limits})


async def add_limit(request):
    req = await request.post()
    async with request.app['db'].acquire() as conn:
        exception = await conn.execute(db.limit.select(
            db.limit.c.country == req['country'] and db.limit.c.cur == req['cur']))
        record = await exception.fetchone()
        # check if limit for this country and currency already exists
        if record:
            return web.json_response({'success': False, 'data': 'Limit exists. Please use PUT method for update.'},
                                     status=400)

        cursor = await conn.execute(db.limit.insert().values(country=req['country'],
                                                             amount=float(req['amount']),
                                                             cur=req['cur'],
                                                             client_id=req['client_id']))
        record = await cursor.fetchone()

    return web.json_response({'success': True, 'data': dict(record)})


async def delete_limit(request):
    limit_id = int(request.query['id'])
    async with request.app['db'].acquire() as conn:
        await conn.execute(db.limit.delete().where(db.limit.c.id == limit_id))

        return web.json_response({'success': True, 'data': 'delete limit with id={0}'.format(str(limit_id))})


async def update_limit(request):
    req = await request.post()
    async with request.app['db'].acquire() as conn:
        await conn.execute(db.limit.update().where(
            db.limit.c.client_id == req['client_id'] and db.limit.c.cur == req['cur'] and db.limit.c.country == req[
                'country']).values(
            amount=float(req['amount'])))

        return web.json_response({'success': True, 'data': 'update limit'})


async def get_history(request):
    async with request.app['db'].acquire() as conn:
        cursor = await conn.execute(db.transfer_history.select(
            db.transfer_history.c.client_id == int(request.query['id'])))
        records = await cursor.fetchall()
        history = []
        for i in records:
            q = dict(i)
            q['date'] = str(q['date'])
            history.append(q)
        return web.json_response({'success': True, 'data': history})


async def add_transfer(request):
    req = await request.post()

    async with request.app['db'].acquire() as conn:  # get limit table for exact country and currency
        limit_conn = await conn.execute(db.limit.select(
            db.limit.c.cur == req['cur'] and db.limit.c.country == req['country']))
        limit = await limit_conn.fetchone()
        if limit.amount < float(req['amount']):  # compare limit and transfer
            return web.json_response({'success': False, 'data': 'Limit exceeded.'}, status=406)

        date = datetime.now()
        count_conn = await conn.execute(db.hist_count.select(  # get month counter table county and currency
            db.hist_count.c.cur == req['cur'] and db.hist_count.c.country == req[
                'country'] and db.hist_count.c.date_ym == '{0}.{1}'.format(date.year, date.month)))
        count_table = await count_conn.fetchone()

        if not count_table:  # if table not exist create it
            await conn.execute(db.hist_count.insert().values(country=req['country'],
                                                             amount=float(req['amount']),
                                                             cur=req['cur'],
                                                             client_id=req['client_id'],
                                                             date_ym='{0}.{1}'.format(date.year, date.month)))

        elif (count_table.amount + float(req['amount'])) > limit.amount:  # compare counted amount with transfer
            return web.json_response({'success': False, 'data': 'Limit exceeded.'}, status=406)

        # create transfer after all comparisons
        cursor = await conn.execute(db.transfer_history.insert().values(country=req['country'],
                                                                        amount=float(req['amount']),
                                                                        cur=req['cur'],
                                                                        client_id=req['client_id'],
                                                                        date=date))
        record = await cursor.fetchone()
        if count_table:
            await conn.execute(db.hist_count.update().where(db.hist_count.c.id == count_table.id).values(
                amount=(count_table.amount + float(req['amount']))))

    return web.json_response({'success': True, 'data': dict(record)})


async def delete_history(request):
    hist_id = int(request.query['id'])
    async with request.app['db'].acquire() as conn:
        await conn.execute(db.transfer_history.delete().where(db.transfer_history.c.id == hist_id))

        return web.json_response({'success': True, 'data': 'delete history with id={0}'.format(str(hist_id))})


async def update_transfer(request):
    req = await request.post()
    async with request.app['db'].acquire() as conn:
        await conn.execute(db.transfer_history.update().where(db.transfer_history.c.id == req['id']).values(
            country=req['country'],
            amount=float(req['amount']),
            cur=req['cur'],
            client_id=req['client_id']))

        return web.json_response({'success': True, 'data': 'update transfer with id={0}'.format(str(req['id']))})


async def add_client(request):
    req = await request.post()
    async with request.app['db'].acquire() as conn:
        try:
            cursor = await conn.execute(db.client.insert().values(name=str(req['name']),
                                                                  password=str(req['password']),
                                                                  token='test_token_fudsk21'))
        except Exception:
            return web.json_response({'success': False, 'data': 'Not unique username'}, status=400)
        record = await cursor.fetchone()

    return web.json_response({'success': True, 'data': dict(record)})


async def update_client(request):
    req = await request.post()
    async with request.app['db'].acquire() as conn:
        try:
            await conn.execute(db.client.update().where(db.client.c.id == req['id']).values(
                name=str(req['name']),
                password=str(req['password']),
                token='test_token_fudsk2'))

        except Exception:
            return web.json_response({'success': False, 'data': 'Not unique username'}, status=400)

        return web.json_response({'success': True, 'data': 'update client with id={0}'.format(str(req['id']))})


async def delete_client(request):
    client_id = int(request.query['id'])
    async with request.app['db'].acquire() as conn:
        await conn.execute(db.client.delete().where(db.client.c.id == client_id))

        return web.json_response({'success': True, 'data': 'delete client with id={0}'.format(str(client_id))})


async def get_client(request):
    async with request.app['db'].acquire() as conn:
        cursor = await conn.execute(db.client.select())
        records = await cursor.fetchall()
        limits = [dict(q) for q in records]

        return web.json_response({'success': True, 'data': limits})
