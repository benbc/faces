from faces import domain
from faces.infrastructure import web, database


class Application:
    def __init__(self):
        self._projects = database.Projects()

    def projects(self):
        ps = self._projects.all()
        return web.render('projects.jinja', projects=ps)

    def create_project(self, name):
        p = domain.Project.create(name)
        self._projects.save(p)
        return web.redirect('projects')
