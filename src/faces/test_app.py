from faces.application import App, Repository, Project


def test_all_project():
    projects = [Project(name='p1'), Project(name='p2')]
    repo = Repository.create_null(projects=projects)
    app = App(repo)

    assert app.all_projects() == projects

def test_create_project():
    repo = Repository.create_null()
    app = App(repo)

    app.create_project('some project')

    assert repo.output_tracker.last_output() == Project('some project')
