# Using the test project

Binder comes with a test-project that allows developers to play with
the API, try things out, etc. To get it running:

 - `cd django-binder`
 - Ensure you have a virtualenv (`virtualenv --python=python3 venv`).
 - Ensure the dependencies are installed (`pip install -Ur project/packages.pip`, note `psycopg2`!).
 - `cd project`
 - Create a postgres DB for the project (`createdb binder`)
 - The testapp doesn't have migrations, you'll need to make them (`./manage.py makemigrations testapp`)
 - And apply them (`./manage.py migrate`)
 - You'll need a user (`./manage.py createsuperuser`)
 - And then you can play with the project (`./manage.py runserver localhost:8010`)

A note about migrations: when the models in `tests/testapp` have changed, you are responsible for making and applying the migrations.
We don't commit the migrations to the repo.
If you're in a mess, `dropdb binder; createdb binder` and recreate the migrations.
