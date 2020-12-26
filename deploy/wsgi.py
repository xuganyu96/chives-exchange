import os
from chives.db import DEFAULT_SQLALCHEMY_URI
from chives.webserver import create_app

# If "SQL_URI" is an environment variable, then pass it into the app factory
env_sql_uri = os.getenv("SQL_URI")
sql_uri = env_sql_uri if env_sql_uri else DEFAULT_SQLALCHEMY_URI
config={"DATABASE_URI": sql_uri}
app = create_app(config)

if __name__ == "__main__":
    app.run()
