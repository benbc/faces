import flask

from faces import application


def render(template, **kwargs):
    return flask.render_template(template, **kwargs)

def redirect(endpoint):
    return flask.redirect(flask.url_for(endpoint), 303)

def init_flask():
    app = application.Application()
    f = flask.Flask(__name__, template_folder='../templates', static_folder='../static')
    f.add_url_rule('/', view_func=app.projects)
    f.add_url_rule('/project', view_func=_dispatch_create_project(app), methods=['PUT'])
    return f

def _dispatch_create_project(app):
    def view_func():
        name = flask.request.form['name']
        return app.create_project(name)
    return view_func
