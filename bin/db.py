from sqlalchemy import (
    MetaData, Table, Column, ForeignKey,
    Integer, String, Date, Float
)

meta = MetaData()

client = Table(
    'client', meta,

    Column('id', Integer, primary_key=True),
    Column('name', String(200), nullable=False),
    Column('token', String(200), nullable=False)
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
