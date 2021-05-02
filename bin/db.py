import aiopg.sa
from sqlalchemy import (
    MetaData, Table, Column, ForeignKey,
    Integer, String, Date, Float
)

meta = MetaData()


async def init_pg(app):
    conf = app['config']['postgres']
    engine = await aiopg.sa.create_engine(
        database=conf['database'],
        user=conf['user'],
        password=conf['password'],
        host=conf['host'],
        port=conf['port'],
        minsize=conf['minsize'],
        maxsize=conf['maxsize'],
    )
    app['db'] = engine


async def close_pg(app):
    app['db'].close()
    await app['db'].wait_closed()


client = Table(
    'client', meta,

    Column('id', Integer, primary_key=True),
    Column('name', String(200), nullable=False),
    Column('password', String(200), nullable=False, unique=True),
    Column('token', String(200), nullable=False, unique=True)
)

limit = Table(
    'limit', meta,

    Column('id', Integer, primary_key=True),
    Column('country', String(200), nullable=False),
    Column('amount', Float, nullable=False),
    Column('cur', String(200), nullable=False),
    Column('client_id',
           Integer,
           ForeignKey('client.id', ondelete='CASCADE'))
)


hist_count = Table(
    'hist_count', meta,

    Column('id', Integer, primary_key=True),
    Column('country', String(200), nullable=False),
    Column('amount', Float, nullable=False),
    Column('cur', String(200), nullable=False),
    Column('date_ym', String(8), nullable=False),
    Column('client_id',
           Integer,
           ForeignKey('client.id', ondelete='CASCADE'))
)


transfer_history = Table(
    'history', meta,

    Column('id', Integer, primary_key=True),
    Column('date', Date, nullable=False),
    Column('country', String(200), nullable=False),
    Column('amount', Float, nullable=False),
    Column('cur', String(200), nullable=False),
    Column('client_id',
           Integer,
           ForeignKey('client.id', ondelete='CASCADE')),
    extend_existing=True
)
