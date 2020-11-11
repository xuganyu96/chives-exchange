from sqlalchemy import create_engine

from chives.cli import parser as chives_parser
from chives.matchingengine import main as me_main
from chives.models import Base

if __name__ == "__main__":
    args = chives_parser.parse_args()

    if args.subcommand == "start_engine":
        security_symbol = args.security_symbol
        queue_host = args.queue_host
        sql_uri = args.sql_uri
        sql_engine = create_engine(sql_uri)
        me_main(queue_host, sql_engine, security_symbol)
    if args.subcommand == "initdb":
        sql_engine = create_engine(args.sql_uri, echo=args.verbose)
        Base.metadata.create_all(sql_engine)
    
