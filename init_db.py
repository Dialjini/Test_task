from sqlalchemy import create_engine, MetaData
from bin.settings import config
from bin.db import client, limit, transfer_history
from random import randint


DSN = "postgresql://{user}:{password}@{host}:{port}/{database}"


def create_tables(engine):
    meta = MetaData()
    meta.create_all(bind=engine, tables=[client, limit, transfer_history])


def sample_data(engine):
    conn = engine.connect()
    conn.execute(client.insert(), [
        {'name': 'Test Client', 'token': 'fhe2w7iou5oe3wh', 'password': 'test'}
    ])

    amount_array = [15000, 50000, 100000, 25000, 35000, 40000, 45000, 30000, 80000, 90000]
    country_array = ['RUS', 'ABH', 'AUS']
    cur_array = ['RUB', 'USD', 'EUR']

    for i in range(9):  # fill limits
        conn.execute(limit.insert(), [
                {'cur': cur_array[i % 3],
                 'country': country_array[i % 3],
                 'amount': amount_array[randint(0, len(amount_array))],
                 'client_id': 1}
            ])


if __name__ == '__main__':
    db_url = DSN.format(**config['postgres'])
    engine = create_engine(db_url)

    create_tables(engine)
    sample_data(engine)
