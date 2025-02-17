from app import db  # Flaskアプリで db を定義しているはず

db.drop_all()
db.create_all()

db.session.commit()

