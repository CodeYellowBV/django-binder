from django.apps import apps
try:
    from django.test.runner import is_discoverable
except ImportError:
    # Django 4 support
    from django.test.runner import try_importing
    def is_discoverable(path):
        is_importable, _ = try_importing(path)
        return is_importable

# This prevents discoverer from loading models and views, which will
# cause all sorts of random failures.
def load_tests(loader, tests, pattern):
    for app in apps.get_app_configs():
        app_path = app.path
        test_dir = '{}/tests/'.format(app_path)
        try:
            if is_discoverable(test_dir):
                tests.addTests(loader.discover(test_dir))
        except AssertionError:
            # This is thrown if the app is loaded from the venv. These can not be tested anyway
            pass

    return tests
