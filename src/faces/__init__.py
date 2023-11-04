from faces.infrastructure import web, database

flask_app = web.init_flask()
database.init_db(flask_app)
