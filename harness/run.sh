#!/bin/sh
# usage: ./run.sh module:function [--path DIR]... [--env NAME] [--json out.json]
cd "$(dirname "$0")" && exec python3 -I navital_qa/conformance.py --grader "$@"
