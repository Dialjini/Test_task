from app import db


class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    limits = db.relationship('Limit', backref='client', lazy='dynamic')
    transfer_history = db.relationship('TransferHistory', backref='client', lazy='dynamic')
    token = db.Column(db.String)


class Limit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    country = db.Column(db.String)
    amount = db.Column(db.Float)
    cur = db.Column(db.String)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'))


class TransferHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime)
    amount = db.Column(db.Float)
    cur = db.Column(db.String)
    country = db.Column(db.String)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'))

