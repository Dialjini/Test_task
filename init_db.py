from random import randint

from sqlalchemy import create_engine, MetaData

from bin.db import client, limit, transfer_history, hist_count
from bin.settings import config

DSN = "postgresql://{user}:{password}@{host}:{port}/{database}"


def create_tables(engine):
    meta = MetaData()
    meta.create_all(bind=engine, tables=[client, limit, transfer_history, hist_count])


def sample_data(engine):
    conn = engine.connect()
    conn.execute(client.insert(), [
        {'name': 'Test Client', 'token': 'fhe2w7iou5oe3wh', 'password': 'test'}
    ])

    amount_array = [15000, 50000, 100000, 25000, 35000, 40000, 45000, 30000, 80000, 90000]
    country_array = ['RUS', 'ABH', 'AUS']
    cur_array = ['RUB', 'USD', 'EUR']

    country_counter = 0
    for i in range(9):  # fill limits
        conn.execute(limit.insert(), [
            {'cur': cur_array[i % 3],
             'country': country_array[country_counter],
             'amount': amount_array[randint(0, len(amount_array) - 1)],
             'client_id': 1}
        ])

        if i % 3 == 2:
            country_counter += 1


if __name__ == '__main__':
    db_url = DSN.format(**config['postgres'])
    engine = create_engine(db_url)

    create_tables(engine)
    sample_data(engine)
