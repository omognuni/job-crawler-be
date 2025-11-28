#!/bin/bash

docker exec -it app sh -c 'uv run python manage.py spectacular --file schema.json --format openapi-json'
