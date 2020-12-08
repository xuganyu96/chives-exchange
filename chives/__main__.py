from sqlalchemy import create_engine

from chives.cli import parser as chives_parser
from chives.matchingengine import start_engine
from chives.models import Base
from chives.webserver import create_app


def main():
    args = chives_parser.parse_args()

    if args.subcommand == "start_engine":
        sql_engine = create_engine(args.sql_uri, echo=args.verbose)
        start_engine(args.queue_host, sql_engine, args.dry_run)
    if args.subcommand == "initdb":
        sql_engine = create_engine(args.sql_uri, echo=args.verbose)
        Base.metadata.create_all(sql_engine)
    if args.subcommand == "webserver":
        # Obtain the agruments that form the application configuration, then 
        # pass the configuration into the app factory before running the app
        sql_uri = args.sql_uri
        config={"DATABASE_URI": sql_uri}
        
        app = create_app(config)
        app.run(port=args.webserver_port, debug=args.debug)


if __name__ == "__main__":
    main()
