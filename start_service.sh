#!/bin/bash

source .env
#uvicorn main:app --reload
uvicorn main:app --workers $WORKERS --host 0.0.0.0 --port $API_PORT