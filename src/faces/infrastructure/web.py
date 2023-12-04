import jinja2
import werkzeug
import werkzeug.middleware.shared_data
import werkzeug.routing
import werkzeug.utils


class HttpServer:
    def __init__(self, lifecycle, template_dir, routes, statics):
        self._lifecycle = lifecycle

        rules, self._functions = _convert_routes(routes)
        self._map = werkzeug.routing.Map(rules)
        self._urls = self._map.bind('127.0.0.1')

        self._templates = jinja2.Environment(
            loader=jinja2.FileSystemLoader(template_dir),
            autoescape=True
        )
        self._statics = statics

    def render(self, template, **context):
        t = self._templates.get_template(f'{template}.jinja')
        return werkzeug.Response(t.render(context), mimetype='text/html')

    def redirect(self, endpoint):
        redirect = werkzeug.utils.redirect(self._urls.build(endpoint))
        print(redirect)
        return redirect

    def run(self):
        app = self._app

        for url_path, file_path in self._statics.items():
            app = werkzeug.middleware.shared_data.SharedDataMiddleware(
                app, {url_path: str(file_path)}
            )

        werkzeug.run_simple(
            '127.0.0.1', 5000,
            app,
            use_debugger=True, use_reloader=True
        )

    def _app(self, environ, start_response):
        request = werkzeug.Request(environ)
        try:
            response = self._dispatch(request)
        except werkzeug.exceptions.HTTPException as e:
            self._lifecycle.request_failure()
            response = e
        except Exception:
            self._lifecycle.request_failure()
            raise
        else:
            self._lifecycle.request_success()
        return response(environ, start_response)

    def _dispatch(self, request):
        endpoint, values = self._map.bind_to_environ(request).match()
        return self._functions[endpoint](request, **values)


def _convert_routes(routes):
    rules = []
    functions = {}

    for route in routes:
        if len(route) == 2:
            path, function = route
            methods = None
        elif len(route) == 3:
            path, function, methods = route
        else:
            assert False

        endpoint = function.__name__
        assert endpoint not in functions
        functions[endpoint] = function

        rules.append(werkzeug.routing.Rule(path, endpoint=endpoint, methods=methods))

    return rules, functions
