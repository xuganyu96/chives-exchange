from sqlalchemy import create_engine

from chives.cli import parser as chives_parser
from chives.matchingengine.matchingengine import main as me_main
from chives.models import Base
from chives.webserver import create_app


def main():
    args = chives_parser.parse_args()

    if args.subcommand == "start_engine":
        sql_engine = create_engine(args.sql_uri, echo=args.verbose)
        me_main(args.queue_host, sql_engine)
    if args.subcommand == "initdb":
        sql_engine = create_engine(args.sql_uri, echo=args.verbose)
        Base.metadata.create_all(sql_engine)
    if args.subcommand == "webserver":
        app = create_app()
        app.run(port=args.webserver_port, debug=args.debug)


if __name__ == "__main__":
    main()
