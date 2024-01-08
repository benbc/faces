import jinja2


class FakeServer:
    def configure(self, routes, statics, templates):
        self._routes = routes
        self._templates = jinja2.Environment(
            loader=jinja2.FileSystemLoader(templates),
            autoescape=True
        )

    def run(self):
        pass

    def render(self, template, **context):
        return self._templates.get_template(f'{template}.jinja').render(context)

    def get(self, path):
        for a_path, endpoint, methods in self._routes:
            if a_path == path and 'GET' in methods:
                return 200, endpoint(None)
        return 404, ''
