#!/usr/bin/env bash

DATASET="FB-Toutanova"
SETTINGS=$1

SCRIPT_DIR=$(dirname $(readlink -f $0))

VIRTUALENV_PATH=$SCRIPT_DIR"/venv"

TRAIN_PATH=$SCRIPT_DIR"/code/train.py"
DATASET_PATH=$SCRIPT_DIR"/data/"$DATASET
SETTINGS_PATH=$SCRIPT_DIR"/"$SETTINGS

ARGUMENT_STRING="--settings "$SETTINGS_PATH" --dataset "$DATASET_PATH

source $VIRTUALENV_PATH"/bin/activate"

pip install tensorflow==1.13.1
pip install theano

$VIRTUALENV_PATH"/bin/python3.7" -u $TRAIN_PATH $ARGUMENT_STRING

deactivate
