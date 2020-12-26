# Environment variables as configurations 
Environment variables are used as configuration options for things like SQL URI, RabbitMQ credentials, etc. These environment variables are stored in a `.conf` file that will be sourced by each container's respective `entrypoint.sh` or other scripts to provide a common source of truth.

Env config files follow the naming scheme: `<env>.env.conf`, where `<env>` can be `dev`, `test`, or `prod`. Production environment configurations contain sensitive credentials, so they won't be stored as plain text file in the code base.