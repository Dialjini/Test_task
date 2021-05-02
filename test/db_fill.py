from random import randint


def start():
    client = models.Client()
    client.name = 'Test Client'

    amount_array = [15000, 50000, 100000, 25000, 35000, 40000, 45000, 30000, 80000, 90000]
    country_array = ['RUS', 'ABH', 'AUS']
    cur_array = ['RUB', 'USD', 'EUR']

    for i in range(9):  # fill limits
        limit = models.Limit()
        limit.cur = cur_array[i % 3]
        limit.country = country_array[i % 3]
        limit.amount = amount_array[randint(0, len(amount_array))]
        client.limits.append(limit)

    db.session.add(client)
    db.session.commit()
