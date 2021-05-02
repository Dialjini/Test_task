from aiohttp import web
from sqlalchemy import create_engine
import db
from datetime import datetime


async def index(request):
    async with request.app['db'].acquire() as conn:
        cursor = await conn.execute(db.client.select())
        records = await cursor.fetchall()
        questions = [dict(q) for q in records]
        return web.Response(text=str(questions))


async def get_limits(request):
    async with request.app['db'].acquire() as conn:
        cursor = await conn.execute(db.limit.select(db.limit.c.client_id == int(request.query['id'])))
        records = await cursor.fetchall()
        limits = [dict(q) for q in records]

        return web.json_response({'success': True, 'data': {'query': str(limits)}})


async def add_limit(request):
    req = await request.post()
    async with request.app['db'].acquire() as conn:
        cursor = await conn.execute(db.limit.insert().values(country=req['country'],
                                                             amount=req['amount'],
                                                             cur=req['cur'],
                                                             client_id=req['client_id']))
        record = await cursor.fetchone()

    return web.json_response({'success': True, 'data': dict(record)})


async def delete_limit(request):
    query = 'todo'


async def update_limit(request):
    query = 'todo'


async def get_history(request):
    async with request.app['db'].acquire() as conn:
        cursor = await conn.execute(db.limit.select(db.transfer_history.c.client_id == int(request.query['id'])))
        records = await cursor.fetchall()
        history = [dict(q) for q in records]
        return web.Response(text=str(history))


async def add_transfer(request):
    req = await request.post()
    async with request.app['db'].acquire() as conn:
        cursor = await conn.execute(db.transfer_history.insert().values(country=req['country'],
                                                                        amount=req['amount'],
                                                                        cur=req['cur'],
                                                                        client_id=req['client_id'],
                                                                        date=datetime.now()))
        record = await cursor.fetchone()

    return web.json_response({'success': True, 'data': dict(record)})
